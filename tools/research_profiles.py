"""
tools/research_profiles.py

Standalone research utility. Run manually to draft ADMITTED_PROFILES and
supplemental_flags.py entries for school+program combos.

Never imported by main.py or any pipeline file.
Output is draft only — human must verify before adding to calibrate.py.

Usage:
    python tools/research_profiles.py \
        "UBC Vancouver,ENGINEERING" \
        "UBC Vancouver,SCIENCE" \
        "University of Waterloo,COMPUTER_SCIENCE"
"""

import json
import sys
import time
import ollama


RESEARCH_PROMPT = """\
You are researching Canadian university admissions for a data pipeline.
For {school} — {program} program, find and extract:

1. GRADE STATS (search the university's official admissions page):
   - Average or median admitted grade (percentage, e.g. 93.5%)
   - Middle 50% grade range if published (e.g. "25th percentile: 90%, 75th: 96%")
   - If only a range is given (e.g. "88-92%"), use the midpoint as the mean

2. ADMISSIONS PROCESS (search the program's specific admissions requirements):
   - Does this program formally consider extracurricular activities or a
     personal profile in the admission decision? (true/false)
   - What supplemental application does this program require, if any?
     Classify as exactly one of:
     "none"      — no supplemental required beyond the main application
     "essay"     — written personal statement or response questions
     "aif"       — Admission Information Form (Waterloo-style structured form)
     "interview" — in-person or video interview required
     "casper"    — CASPer situational judgment test required
   - One sentence describing the supplemental to show the user

Return ONLY a JSON object, nothing else, no markdown fences:
{{
  "mean_admitted": 93.5,
  "std_from_range": 2.2,
  "range_p25": 90.0,
  "range_p75": 96.0,
  "considers_ecs": true,
  "ec_note": "UBC requires a personal profile covering ECs and achievements",
  "supplemental_type": "essay",
  "supplemental_description": "UBC requires a personal profile with written responses",
  "supplemental_penalty": 0.92,
  "source": "ubc.ca/admissions — direct URL",
  "confidence": "high"
}}

If you cannot find reliable data for a field, set it to null.
If you cannot find any data for this combo, return {{"error": "no data found"}}.\
"""

# Default supplemental penalties when model doesn't override
PENALTY_DEFAULTS = {
    "none":      1.00,
    "essay":     0.92,
    "aif":       0.90,
    "interview": 0.85,
    "casper":    0.88,
}

INTER_COMBO_DELAY = 2  # seconds between Ollama calls


def call_ollama(school: str, program: str) -> dict | None:
    """Calls Ollama llama3.2 with the research prompt. Returns parsed dict or None."""
    prompt = RESEARCH_PROMPT.format(school=school, program=program)

    try:
        response = ollama.chat(
            model="llama3.2",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0},
        )
        raw = response["message"]["content"].strip()

        # Strip markdown code fences if model adds them (matches reddit_agent.py pattern)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        return json.loads(raw)

    except json.JSONDecodeError:
        print(f"    [JSON parse failed] Raw response was:\n{raw}\n")
        return None
    except Exception as e:
        print(f"    [Ollama error] {e}")
        return None


def derive_std(data: dict) -> tuple[float, str]:
    """
    Returns (std_admitted, derivation_note).
    Uses published p25/p75 range if available: std = (p75 - p25) / 1.35
    Falls back to std_from_range if present.
    Defaults to 2.5 when only a mean is available.
    """
    p25 = data.get("range_p25")
    p75 = data.get("range_p75")
    if p25 is not None and p75 is not None:
        std = round((p75 - p25) / 1.35, 2)
        return std, f"derived from range {p25}–{p75}: ({p75}-{p25})/1.35"

    std_from_range = data.get("std_from_range")
    if std_from_range is not None:
        return round(float(std_from_range), 2), "provided by model"

    return 2.5, "default — only mean available, no range published"


def resolve_penalty(data: dict) -> float:
    """Uses model-provided penalty if present and valid, else applies default."""
    supp_type = data.get("supplemental_type") or "none"
    model_penalty = data.get("supplemental_penalty")
    if model_penalty is not None:
        try:
            p = float(model_penalty)
            if 0.5 <= p <= 1.0:
                return p
        except (TypeError, ValueError):
            pass
    return PENALTY_DEFAULTS.get(supp_type, 1.0)


def format_admitted_profile_entry(school: str, program: str, data: dict) -> str:
    """Formats the ADMITTED_PROFILES dict entry as ready-to-paste Python."""
    mean = data.get("mean_admitted")
    std, std_note = derive_std(data)
    source = data.get("source") or "not found"
    confidence = data.get("confidence") or "low"
    p25 = data.get("range_p25")
    p75 = data.get("range_p75")

    range_str = f"{p25}–{p75}" if p25 is not None and p75 is not None else "not published"

    lines = [
        f'# ── ADMITTED_PROFILES entry ──────────────────────────────────────',
        f'# Source:    {source}',
        f'# Range:     {range_str}',
        f'# Std note:  {std_note}',
        f'# Confidence: {confidence} (flip verified=True after confirming)',
        f'    ("{school}", "{program}"): {{',
        f'        "mean_admitted": {mean},',
        f'        "std_admitted":  {std},    # {std_note}',
        f'        "verified":      False,',
        f'        "source":        "{source}",',
        f'    }},',
    ]
    return "\n".join(lines)


def format_admission_profile_entry(school: str, program: str, data: dict) -> str:
    """Formats the supplemental_flags.py AdmissionProfile entry as ready-to-paste Python."""
    considers_ecs = data.get("considers_ecs")
    ec_note = data.get("ec_note") or ""
    supp_type = data.get("supplemental_type") or "none"
    supp_desc = data.get("supplemental_description") or ""
    penalty = resolve_penalty(data)

    # Normalize booleans
    considers_ecs_str = "True" if considers_ecs else "False"

    lines = [
        f'# ── supplemental_flags.py entry ─────────────────────────────────',
        f'    ("{school}", "{program}"): AdmissionProfile(',
        f'        considers_ecs={considers_ecs_str},',
        f'        ec_note="{ec_note}",',
        f'        supplemental_type="{supp_type}",',
        f'        supplemental_description="{supp_desc}",',
        f'        supplemental_penalty={penalty},',
        f'    ),',
    ]
    return "\n".join(lines)


def research_combo(school: str, program: str) -> None:
    """Researches one school+program combo and prints both ready-to-paste entries."""
    print(f"\n{'=' * 70}")
    print(f"RESEARCHING: {school} — {program}")
    print(f"{'=' * 70}")

    data = call_ollama(school, program)

    if data is None:
        print(f"  [FAILED] Ollama returned no parseable response. Skipping.")
        return

    if "error" in data:
        print(f"  [NO DATA] Model reported: {data['error']}")
        return

    # Print raw response for transparency
    print(f"\n  Raw model output:")
    print(f"  {json.dumps(data, indent=4)}")

    # Check for critical nulls
    if data.get("mean_admitted") is None:
        print(f"\n  [WARNING] mean_admitted is null — ADMITTED_PROFILES entry will be incomplete.")

    if data.get("supplemental_type") is None:
        print(f"\n  [WARNING] supplemental_type is null — defaulting to 'none'.")

    print(f"\n{format_admitted_profile_entry(school, program, data)}")
    print(f"\n{format_admission_profile_entry(school, program, data)}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python tools/research_profiles.py \"School,PROGRAM\" ...")
        print('Example: python tools/research_profiles.py "UBC Vancouver,ENGINEERING"')
        sys.exit(1)

    combos = []
    for arg in sys.argv[1:]:
        parts = arg.split(",", 1)
        if len(parts) != 2:
            print(f"  [SKIP] Invalid format '{arg}' — expected 'School,PROGRAM'")
            continue
        school = parts[0].strip()
        program = parts[1].strip().upper()
        combos.append((school, program))

    print(f"Researching {len(combos)} combo(s) via Ollama llama3.2...")
    print("Output is DRAFT — verify all entries before adding to calibrate.py.\n")

    for i, (school, program) in enumerate(combos):
        research_combo(school, program)
        if i < len(combos) - 1:
            time.sleep(INTER_COMBO_DELAY)

    print(f"\n{'=' * 70}")
    print("Research complete. Review all entries above before use.")
    print("verified=False on every entry — flip to True after confirming.")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
