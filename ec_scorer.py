# ec_scorer.py
# Scores student EC text and written supplementals via Ollama llama3.2.
# Returns a profile multiplier applied on top of the base probability.
#
# Three modes only (Mode 2 — combined EC + essay — has been removed):
#   Mode 0: neither text provided → multiplier=1.0, no Ollama call
#   Mode 1: ec_text provided      → score ECs on 4 dimensions
#   Mode 3: supplemental_text     → score essay/AIF on 4 dimensions
#
# Caller is responsible for passing the right combination.
# score_profile() never needs to decide between Mode 1 and Mode 3 in
# the same call — they are always called separately.

import json
import ollama

# ── Prompts ───────────────────────────────────────────────────────────────────

_MODE_1_PROMPT = """\
You are an expert Canadian university admissions evaluator.
Score this student's extracurricular activities on four dimensions, each 0-10:
1. Leadership - did they lead, not just participate?
2. Sustained commitment - multi-year involvement, not one-off?
3. Community impact - did their work meaningfully affect others?
4. Program relevance - does it connect to their intended field of study?

Return ONLY a JSON object, nothing else, no markdown fences:
{{"leadership": 7, "commitment": 8, "impact": 6, "relevance": 9, "reasoning": "one sentence"}}

Student extracurricular activities:
{ec_text}"""

_MODE_3_PROMPT = """\
You are an expert Canadian university admissions evaluator.
The student has provided a supplemental application question and their answer.
The question is included for context only. Score the student's ANSWER only.

Score on four dimensions, each 0-10:
1. Clarity - is the answer specific and concrete, not vague or generic?
2. Self-awareness - do they understand why they want this program?
3. Curiosity - do they show genuine intellectual interest beyond grades?
4. Fit - does the answer reflect real understanding of this program?

Return ONLY a JSON object, nothing else, no markdown fences:
{{"clarity": 8, "self_awareness": 7, "curiosity": 6, "fit": 9, "reasoning": "one sentence"}}

Supplemental question and answer:
{supplemental_text}"""


# ── Multiplier lookup tables ──────────────────────────────────────────────────

def _mode1_multiplier(avg: float) -> float:
    if avg >= 8.5:   return 1.375
    elif avg >= 7.0: return 1.20
    elif avg >= 5.0: return 1.025
    elif avg >= 3.0: return 0.90
    else:            return 0.80


def _mode3_multiplier(avg: float) -> float:
    if avg >= 8.5:   return 1.15
    elif avg >= 7.0: return 1.08
    elif avg >= 5.0: return 1.00
    elif avg >= 3.0: return 0.88
    else:            return 0.80


# ── Internal Ollama caller ────────────────────────────────────────────────────

def _call_ollama(prompt: str) -> dict | None:
    """
    Calls Ollama llama3.2. Returns parsed JSON dict or None on any failure.
    Strips markdown fences before parsing. Logs raw response on parse error.
    Matches the exact pattern from pipeline/reddit_agent.py.
    """
    try:
        response = ollama.chat(
            model="llama3.2",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0},
        )
        raw = response["message"]["content"].strip()

        # Strip markdown code fences if model adds them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        return json.loads(raw)

    except json.JSONDecodeError:
        print(f"    [ec_scorer] JSON parse failed. Raw response:\n{raw}\n")
        return None
    except Exception as e:
        print(f"    [ec_scorer] Ollama error: {e}")
        return None


# ── Public function ───────────────────────────────────────────────────────────

def score_profile(
    ec_text: str = "",
    supplemental_text: str = "",
    program_category: str = "",
) -> dict:
    """
    Selects mode based on which text fields are non-empty.

    Mode 0: neither text provided → multiplier=1.0, no Ollama call
    Mode 1: ec_text provided, no supplemental_text → score ECs
    Mode 3: supplemental_text provided, no ec_text → score essay/AIF

    Caller is responsible for passing only one text at a time.
    If both are passed, Mode 1 takes priority (ec_text scored; supplemental ignored).
    Mode 2 does not exist — each component is always scored independently.

    Returns:
        multiplier    float   adjustment factor
        mode          int     0 | 1 | 3
        scores        dict    raw dimension scores from Ollama (empty in Mode 0)
        reasoning     str     one sentence from Ollama (empty string in Mode 0)
        raw_avg       float   average of dimension scores (0.0 in Mode 0)

    Returns multiplier=1.0 on any Ollama failure — never crashes.
    """
    has_ec   = bool(ec_text.strip())
    has_supp = bool(supplemental_text.strip())

    # Mode 0 — nothing provided
    if not has_ec and not has_supp:
        return {
            "multiplier": 1.0,
            "mode":       0,
            "scores":     {},
            "reasoning":  "",
            "raw_avg":    0.0,
        }

    # Mode 1 — EC text (takes priority if both somehow provided)
    if has_ec:
        prompt = _MODE_1_PROMPT.format(ec_text=ec_text.strip())
        data   = _call_ollama(prompt)

        if data is None:
            return {"multiplier": 1.0, "mode": 1, "scores": {}, "reasoning": "", "raw_avg": 0.0}

        try:
            scores = {
                "leadership": float(data["leadership"]),
                "commitment": float(data["commitment"]),
                "impact":     float(data["impact"]),
                "relevance":  float(data["relevance"]),
            }
            avg        = sum(scores.values()) / 4.0
            multiplier = _mode1_multiplier(avg)
            reasoning  = str(data.get("reasoning", ""))
        except (KeyError, TypeError, ValueError):
            return {"multiplier": 1.0, "mode": 1, "scores": {}, "reasoning": "", "raw_avg": 0.0}

        return {
            "multiplier": multiplier,
            "mode":       1,
            "scores":     scores,
            "reasoning":  reasoning,
            "raw_avg":    round(avg, 2),
        }

    # Mode 3 — written supplemental (essay or AIF)
    prompt = _MODE_3_PROMPT.format(supplemental_text=supplemental_text.strip())
    data   = _call_ollama(prompt)

    if data is None:
        return {"multiplier": 1.0, "mode": 3, "scores": {}, "reasoning": "", "raw_avg": 0.0}

    try:
        scores = {
            "clarity":        float(data["clarity"]),
            "self_awareness": float(data["self_awareness"]),
            "curiosity":      float(data["curiosity"]),
            "fit":            float(data["fit"]),
        }
        avg        = sum(scores.values()) / 4.0
        multiplier = _mode3_multiplier(avg)
        reasoning  = str(data.get("reasoning", ""))
    except (KeyError, TypeError, ValueError):
        return {"multiplier": 1.0, "mode": 3, "scores": {}, "reasoning": "", "raw_avg": 0.0}

    return {
        "multiplier": multiplier,
        "mode":       3,
        "scores":     scores,
        "reasoning":  reasoning,
        "raw_avg":    round(avg, 2),
    }
