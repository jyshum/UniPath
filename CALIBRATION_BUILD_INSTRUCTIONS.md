# UniPath AI — Calibration + EC Scoring Build Instructions
# Hand this file to Claude Code. Read PROJECT_STATE.md and calibrate.py first.

---

## Model Instructions

Use claude-opus-4-5 for this task. Do not compress your thinking or skip steps.
This is a complex multi-phase build with interdependent logic. Take as many tokens
as needed at each phase. Think out loud before writing any code.

---

## IMPORTANT — Architecture Has Changed. Read This Carefully.

The previous Bayesian approach (accepted vs rejected DB rows) has been abandoned.
Phase 1 validation confirmed only 4 combos could produce output due to insufficient
rejection data — a structural problem with Reddit data that cannot be fixed by
scraping more rows.

The new architecture replaces calibrated_probability() with a grade-distribution
formula anchored to published admission statistics. The supplemental and EC
scoring are user-driven — the student tells us what their application process
involved rather than us looking it up per school.

supplemental_flags.py is NOT being built. It has been eliminated entirely.

Read this entire document before touching any file.

---

## What Is Being Kept (Unchanged)

- recommend.py — do not touch
- main.py — do not touch
- All pipeline files — do not touch
- tools/research_profiles.py — keep as built, will be improved later
- Ollama integration pattern from pipeline/reddit_agent.py — reference this
- The 3%–92% output clamp — unchanged

---

## What Is Changing

- calibrate.py fully rewritten around the new grade-distribution formula
- supplemental_flags.py eliminated — do not build it
- ec_scorer.py built with Mode 0, 1, and 3 only (Mode 2 removed)
- final_probability() simplified — takes user-provided inputs directly
- Two operating modes (Mode A / Mode B) replace the old Bayesian path
- final_probability() gains two new fields: data_limited and disclaimer

---

## Full Probability Architecture

### The Formula

```
Base probability (grade-anchored, from published stats)
    × EC multiplier          (scored by Ollama, or 1.0 if not applicable)
    × Supplemental multiplier(s) (one per supplemental type the user selected)
    = raw → clamped 3%–92% → display_percent
```

The base probability is computed from the student's grade relative to the
admitted grade distribution for that school+program. All multipliers apply
on top of it independently. They do not interact with each other — each one
is computed separately and all are multiplied together at the end.

### Example: Ivey (essay + interview)

```
base_probability    = 0.35   (student's grade gives 35% base)

EC multiplier:
  Student provided EC text → Ollama scores avg 7.5 → multiplier = 1.20

Essay multiplier:
  Student pasted question + answer → Ollama scores avg 8.0 → multiplier = 1.08

Interview multiplier:
  Fixed penalty → 0.85

Final:
  0.35 × 1.20 × 1.08 × 0.85 = 0.386 → clamped → 39%
```

### Example: Same school, student hasn't completed anything

```
base_probability    = 0.35
EC multiplier:      1.0  (no text provided)
Essay multiplier:   0.92 (not yet completed — fixed penalty)
Interview:          0.85 (always fixed)

0.35 × 1.0 × 0.92 × 0.85 = 0.274 → 27%
```

---

## Two Operating Modes for Base Probability

BASE_RATES — acceptance rate per combo. Every combo you show anything for.
ADMITTED_PROFILES — admitted grade statistics per combo. Subset of BASE_RATES.

Combo in ADMITTED_PROFILES → Mode A (grade-adjusted probability)
Combo in BASE_RATES only → Mode B (base rate only, data_limited=True)
Combo in neither → return None

### Mode A — Grade-Adjusted Probability

Three inputs per combo: mean_admitted, std_admitted, base_rate

Step 1 — Z-score:
  z = (student_grade - mean_admitted) / std_admitted
  Measures how many standard deviations above/below the mean admitted student.
  std_admitted normalization is critical — the same grade gap means different
  things at schools with tight vs wide admitted grade pools.

Step 2 — Percentile:
  from scipy.stats import norm
  percentile = norm.cdf(z)
  What fraction of admitted students had a lower grade? Range 0.0–1.0.
  This is NOT the probability of admission yet.

Step 3 — Scale by base rate:
  deviation  = percentile - 0.5
  adjustment = deviation * sensitivity   (default sensitivity = 1.5)
  raw        = base_rate * (1 + adjustment)
  probability = min(max(raw, 0.03), 0.92)

  When percentile = 0.5 (student exactly at mean admitted grade):
  deviation = 0, adjustment = 0, raw = base_rate exactly.
  Above mean → boosted above base_rate.
  Below mean → pulled below base_rate.

Mode A confidence:
  "high"   — verified=True
  "medium" — verified=True but std was derived rather than directly published
  "low"    — verified=False

### Mode B — Base Rate Only

No grade distribution data. probability = base_rate (before clamp).
EC and supplemental multipliers still apply on top.
Always: data_limited=True, confidence="estimate"
disclaimer = "Based on published acceptance rate only. There may not be
              enough data on this program. This percentage is an estimate."

### Gate Structure in calibrated_probability()

Gate 1: In BASE_RATES? No → return None
Gate 2: In ADMITTED_PROFILES? No → return Mode B
Gate 3: verified=True? No → confidence="low", proceed Mode A
Gate 4: Inverted distribution check (query DB)
  avg accepted grade <= avg rejected grade for this combo?
  Yes → fall back to Mode B (not None — student still sees a number)
  No  → proceed Mode A formula

---

## EC Multiplier

The EC multiplier applies when the school considers ECs in admissions and the
student provides EC text. It is scored by Ollama independently of all
supplemental multipliers.

EC_CONSIDERED lookup (in calibrate.py) controls whether the frontend shows
the EC input field. If school not in EC_CONSIDERED, default to True.

```python
EC_CONSIDERED: dict[str, bool] = {
    "UBC Vancouver":           True,
    "University of Waterloo":  True,
    "University of Toronto":   True,
    "Western University":      True,
    "Queen's University":      True,
    "McMaster University":     False,  # BHSc: no CV/resume, grade + supp only
    "Simon Fraser University": False,  # grade-only admission
}
```

EC scoring uses Ollama Mode 1. Range: 0.80–1.375.
If no EC text provided, or ec_considered=False: EC multiplier = 1.0.

---

## Supplemental Multipliers

The user selects which supplemental types their program required (multi-select).
Each type gets its own independent multiplier. All are multiplied against the
base probability together with the EC multiplier at the end.

### Supplemental types the user can select (multi-select, pick all that apply)

```
"none"          — no supplemental required
"essay"         — written personal statement or response questions
"aif"           — Admission Information Form (Waterloo-style structured form)
"interview"     — in-person or video interview
"activity_list" — standalone activity/extracurricular list form
```

For essay and aif: the user also provides:
  - supplemental_completed: bool (did they do it?)
  - supplemental_text: str (optional — paste question + answer)
  - UI label: "Paste the question, then your answer below it"
    Ollama is explicitly told the question is context only — score the answer.

### Fixed penalties (applied when type is present but unscored)

```python
SUPPLEMENTAL_PENALTIES = {
    "essay":         0.92,   # not yet completed
    "aif":           0.90,   # not yet completed
    "interview":     0.85,   # always fixed — cannot evaluate performance
}
```

### Multiplier logic per supplemental type

**"none":**
  multiplier = 1.0

**"essay" or "aif":**
  IF not completed:
    multiplier = SUPPLEMENTAL_PENALTIES[type]
  ELIF completed but no text pasted:
    multiplier = 1.0  (they did it, we just can't score it — no penalty)
  ELIF completed and text provided:
    multiplier = score_profile(supplemental_text=text).multiplier  [Mode 3]
    Range: 0.80–1.15

**"interview":**
  multiplier = SUPPLEMENTAL_PENALTIES["interview"] = 0.85 always
  Cannot evaluate interview performance. No scoring path.

**"activity_list":**
  IF text provided:
    multiplier = score_profile(ec_text=activity_text).multiplier  [Mode 1]
    Range: 0.80–1.375
  ELSE:
    multiplier = 1.0

---

## Ollama Scoring Modes

Mode 2 (combined EC + essay) is removed. Each component is scored
independently. Three modes only:

### Mode 0 — Nothing provided
No Ollama call. Return multiplier=1.0 immediately.

### Mode 1 — EC text or activity list
Used for: EC text, activity_list supplemental type.

Prompt:
```
You are an expert Canadian university admissions evaluator.
Score this student's extracurricular activities on four dimensions, each 0-10:
1. Leadership - did they lead, not just participate?
2. Sustained commitment - multi-year involvement, not one-off?
3. Community impact - did their work meaningfully affect others?
4. Program relevance - does it connect to their intended field of study?

Return ONLY a JSON object, nothing else, no markdown fences:
{"leadership": 7, "commitment": 8, "impact": 6, "relevance": 9, "reasoning": "one sentence"}
```

Multiplier calculation:
```python
avg = (leadership + commitment + impact + relevance) / 4.0
if avg >= 8.5:   multiplier = 1.375
elif avg >= 7.0: multiplier = 1.20
elif avg >= 5.0: multiplier = 1.025
elif avg >= 3.0: multiplier = 0.90
else:            multiplier = 0.80
```

### Mode 3 — Written supplemental (essay or AIF)
Used for: essay and aif supplemental types when completed and text provided.
The student pastes both the question and their answer. Ollama scores the answer
only — the question is context. The prompt must make this explicit.

Prompt:
```
You are an expert Canadian university admissions evaluator.
The student has provided a supplemental application question and their answer.
The question is included for context only. Score the student's ANSWER only.

Score on four dimensions, each 0-10:
1. Clarity - is the answer specific and concrete, not vague or generic?
2. Self-awareness - do they understand why they want this program?
3. Curiosity - do they show genuine intellectual interest beyond grades?
4. Fit - does the answer reflect real understanding of this program?

Return ONLY a JSON object, nothing else, no markdown fences:
{"clarity": 8, "self_awareness": 7, "curiosity": 6, "fit": 9, "reasoning": "one sentence"}
```

Multiplier calculation:
```python
avg = (clarity + self_awareness + curiosity + fit) / 4.0
if avg >= 8.5:   multiplier = 1.15
elif avg >= 7.0: multiplier = 1.08
elif avg >= 5.0: multiplier = 1.00
elif avg >= 3.0: multiplier = 0.88
else:            multiplier = 0.80
```

### score_profile() function signature

```python
def score_profile(
    ec_text: str = "",
    supplemental_text: str = "",
    program_category: str = "",
) -> dict:
    """
    Selects mode based on which text fields are non-empty.
    Mode 0: neither provided
    Mode 1: ec_text only
    Mode 3: supplemental_text only (Mode 2 removed)

    If both are provided, prefer Mode 1 if ec_text is set and
    supplemental_text is empty, Mode 3 if supplemental_text is set.
    Caller is responsible for passing the right combination.

    Returns:
        multiplier    float
        mode          int     0 | 1 | 3
        scores        dict
        reasoning     str
        raw_avg       float

    Returns multiplier=1.0 on any Ollama failure — never crash.
    """
```

Critical: wrap Ollama in try/except, strip markdown fences before JSON parse,
log raw response on parse failure, never call Ollama in Mode 0.

---

## Data Structures in calibrate.py

```python
BASE_RATES: dict[tuple[str, str], float] = {
    ("UBC Vancouver",           "ENGINEERING"):      0.32,
    ("UBC Vancouver",           "SCIENCE"):          0.52,
    ("UBC Vancouver",           "BUSINESS"):         0.30,
    ("UBC Vancouver",           "COMPUTER_SCIENCE"): 0.25,
    ("UBC Vancouver",           "HEALTH"):           0.20,
    ("UBC Vancouver",           "ARTS"):             0.55,
    ("University of Waterloo",  "COMPUTER_SCIENCE"): 0.12,
    ("University of Waterloo",  "ENGINEERING"):      0.38,
    ("University of Toronto",   "ENGINEERING"):      0.35,
    ("University of Toronto",   "COMPUTER_SCIENCE"): 0.15,
    ("University of Toronto",   "BUSINESS"):         0.20,
    ("University of Toronto",   "SCIENCE"):          0.40,
    ("Western University",      "BUSINESS"):         0.25,
    ("Queen's University",      "BUSINESS"):         0.22,
    ("McMaster University",     "HEALTH"):           0.05,
    ("Simon Fraser University", "ENGINEERING"):      0.55,
    ("Simon Fraser University", "SCIENCE"):          0.60,
    ("Simon Fraser University", "BUSINESS"):         0.45,
}

ADMITTED_PROFILES: dict[tuple[str, str], dict] = {
    ("UBC Vancouver", "ENGINEERING"): {
        "mean_admitted": 90.0,
        "std_admitted":  3.0,
        "verified":      True,
        "source":        "UBC Engineering FAQ — competitive range 88-92%",
    },
    ("UBC Vancouver", "SCIENCE"): {
        "mean_admitted": 88.0,
        "std_admitted":  3.0,
        "verified":      True,
        "source":        "UBC 2024 data — range 86-90%",
    },
    ("UBC Vancouver", "BUSINESS"): {
        "mean_admitted": 90.0,
        "std_admitted":  2.5,
        "verified":      True,
        "source":        "Sauder official page — competitive avg 87-92%",
    },
    ("University of Waterloo", "COMPUTER_SCIENCE"): {
        "mean_admitted": 95.5,
        "std_admitted":  1.5,
        "verified":      True,
        "source":        "Multiple sources — most admitted above 95%",
    },
    ("University of Waterloo", "ENGINEERING"): {
        "mean_admitted": 94.0,
        "std_admitted":  2.0,
        "verified":      True,
        "source":        "Multiple sources — mid-90s norm",
    },
    ("University of Toronto", "ENGINEERING"): {
        "mean_admitted": 95.4,
        "std_admitted":  2.0,
        "verified":      True,
        "source":        "UofT Engineering By The Numbers 2024 — OFFICIAL",
    },
    ("University of Toronto", "COMPUTER_SCIENCE"): {
        "mean_admitted": 96.0,
        "std_admitted":  1.5,
        "verified":      True,
        "source":        "Multiple sources — mid to high 90s consensus",
    },
    ("University of Toronto", "BUSINESS"): {
        "mean_admitted": 91.0,
        "std_admitted":  2.5,
        "verified":      True,
        "source":        "grantme.ca — Rotman ~89-91%",
    },
    ("Western University", "BUSINESS"): {
        "mean_admitted": 93.0,
        "std_admitted":  2.0,
        "verified":      True,
        "source":        "youthfully.com Ivey guide — 90% minimum competitive",
    },
    ("Queen's University", "BUSINESS"): {
        "mean_admitted": 90.0,
        "std_admitted":  2.5,
        "verified":      True,
        "source":        "Smith Commerce FAQ — 87% minimum, competitive high 80s-90s",
    },
    ("McMaster University", "HEALTH"): {
        "mean_admitted": 93.0,
        "std_admitted":  2.0,
        "verified":      True,
        "source":        "McMaster BHSc FAQ — offers across low-to-high 90s",
    },
    ("Simon Fraser University", "ENGINEERING"): {
        "mean_admitted": 85.0,
        "std_admitted":  3.0,
        "verified":      True,
        "source":        "SFU official historical grade ranges — mid 80s",
    },
    ("Simon Fraser University", "SCIENCE"): {
        "mean_admitted": 82.0,
        "std_admitted":  3.5,
        "verified":      True,
        "source":        "SFU grade-only admission, Science range estimated",
    },
}

EC_CONSIDERED: dict[str, bool] = {
    "UBC Vancouver":           True,
    "University of Waterloo":  True,
    "University of Toronto":   True,
    "Western University":      True,
    "Queen's University":      True,
    "McMaster University":     False,
    "Simon Fraser University": False,
}

SUPPLEMENTAL_PENALTIES: dict[str, float] = {
    "essay":     0.92,
    "aif":       0.90,
    "interview": 0.85,
}
```

---

## Phase 1 — Rewrite calibrate.py

Delete all existing Bayesian code. Implement calibrated_probability() using
the gate structure and Mode A/B formula above.

Check if scipy is installed: pip show scipy. Ask before adding if not present.

### calibrated_probability() signature

```python
from scipy.stats import norm

def calibrated_probability(
    school: str,
    program_category: str,
    grade: float,
    sensitivity: float = 1.5,
    conn=None,
) -> dict | None:
    """
    Returns None only when school+program not in BASE_RATES.

    Mode A output:
        probability     float   0.03-0.92
        confidence      str     "high" | "medium" | "low"
        base_rate       float
        mean_admitted   float
        std_admitted    float
        z_score         float
        percentile      float
        data_limited    bool    False
        disclaimer      None
        mode            str     "grade_adjusted"

    Mode B output:
        probability     float   0.03-0.92
        confidence      str     "estimate"
        base_rate       float
        mean_admitted   None
        std_admitted    None
        z_score         None
        percentile      None
        data_limited    bool    True
        disclaimer      str
        mode            str     "base_rate_only"
    """
```

### Smoke tests

```python
from calibrate import calibrated_probability

# Test 1 — grade above mean → probability above base_rate (0.35)
print(calibrated_probability("University of Toronto", "ENGINEERING", grade=97.0))

# Test 2 — grade below mean → probability below base_rate
print(calibrated_probability("University of Toronto", "ENGINEERING", grade=92.0))

# Test 3 — grade at mean (95.4) → probability within 0.03 of base_rate
print(calibrated_probability("University of Toronto", "ENGINEERING", grade=95.4))

# Test 4 — in BASE_RATES, not in ADMITTED_PROFILES → Mode B
print(calibrated_probability("University of Toronto", "SCIENCE", grade=90.0))

# Test 5 — not in BASE_RATES → None
print(calibrated_probability("University of Ottawa", "ENGINEERING", grade=85.0))

# Test 6 — known inverted distribution combo from DB → Mode B not None
```

Flag as problems:
- Test 1 not above 0.35
- Test 2 not below 0.35
- Test 3 differs from 0.35 by more than 0.03
- Test 4 data_limited is not True
- Test 5 returns anything other than None
- Test 6 returns None

### Sensitivity validation

Run calibrated_probability() on every accepted and rejected row in the DB
with a non-null core_avg and a matching ADMITTED_PROFILES entry. Report
average output probability for accepted vs rejected students. Accepted must
average higher. If not, adjust sensitivity to 2.0 and re-test. Report all
group averages before proceeding.

---

## Phase 2 — Build ec_scorer.py

Use pipeline/reddit_agent.py as the exact Ollama calling reference.

Implement Mode 0, Mode 1, and Mode 3 only. Mode 2 is removed.

Mode 0: neither text provided → multiplier=1.0, no Ollama call
Mode 1: ec_text provided → score ECs with Mode 1 prompt
Mode 3: supplemental_text provided → score essay/AIF with Mode 3 prompt

The caller (final_probability) is responsible for passing the right
combination. score_profile() never needs to decide between Mode 1 and 3
in the same call — they are always called separately.

Implement score_profile() as specified in the Ollama Scoring Modes section.
Wrap Ollama in try/except, strip markdown fences, log on parse failure.

---

## Phase 3 — Build final_probability() in calibrate.py

Add to bottom of calibrate.py. Do not modify existing functions above it.

### Input parameters

```python
def final_probability(
    school: str,
    program_category: str,
    grade: float,
    ec_text: str = "",
    supplemental_types: list[str] = [],  # multi-select, e.g. ["essay", "interview"]
    supplemental_texts: dict[str, str] = {},  # keyed by type, e.g. {"essay": "Q+A text"}
    supplemental_completed: dict[str, bool] = {},  # keyed by type
    sensitivity: float = 1.5,
    conn=None,
) -> dict | None:
```

### Decision logic

```python
# Step 1 — Get base probability
base = calibrated_probability(school, program_category, grade, sensitivity, conn)
if base is None:
    return None

# Step 2 — EC multiplier
ec_considered = EC_CONSIDERED.get(school, True)
if ec_considered and ec_text.strip():
    ec_multiplier = score_profile(ec_text=ec_text).multiplier
else:
    ec_multiplier = 1.0

# Step 3 — Supplemental multipliers (one per type, all independent)
supp_multipliers = []

for supp_type in supplemental_types:

    if supp_type == "none":
        supp_multipliers.append(1.0)

    elif supp_type in ("essay", "aif"):
        completed = supplemental_completed.get(supp_type, False)
        text = supplemental_texts.get(supp_type, "")
        if not completed:
            supp_multipliers.append(SUPPLEMENTAL_PENALTIES[supp_type])
        elif completed and text.strip():
            m = score_profile(supplemental_text=text).multiplier  # Mode 3
            supp_multipliers.append(m)
        else:
            supp_multipliers.append(1.0)  # completed, no text — no penalty

    elif supp_type == "interview":
        supp_multipliers.append(SUPPLEMENTAL_PENALTIES["interview"])  # always fixed

    elif supp_type == "activity_list":
        text = supplemental_texts.get("activity_list", "")
        if text.strip():
            m = score_profile(ec_text=text).multiplier  # Mode 1
            supp_multipliers.append(m)
        else:
            supp_multipliers.append(1.0)

if not supp_multipliers:
    supp_multipliers = [1.0]

# Step 4 — Compose all multipliers on top of base
profile_multiplier = ec_multiplier
for m in supp_multipliers:
    profile_multiplier *= m

raw = base["probability"] * profile_multiplier
probability = round(min(max(raw, 0.03), 0.92), 4)
```

### Output dict

```python
return {
    "probability":        probability,
    "display_percent":    f"{round(probability * 100)}%",
    "base_probability":   base["probability"],
    "ec_multiplier":      ec_multiplier,
    "supp_multipliers":   supp_multipliers,
    "profile_multiplier": profile_multiplier,
    "confidence":         base["confidence"],
    "base_rate":          base["base_rate"],
    "mean_admitted":      base["mean_admitted"],
    "std_admitted":       base["std_admitted"],
    "data_limited":       base["data_limited"],
    "disclaimer":         base["disclaimer"],
    "ec_considered":      ec_considered,
    "mode":               base["mode"],
}
```

---

## Phase 4 — Tests

Write tests/test_calibration.py using pytest.

```python
# calibrated_probability
# 1.  Returns None for combo not in BASE_RATES
# 2.  Returns Mode B (data_limited=True) for combo in BASE_RATES only
# 3.  Mode A: grade above mean → probability above base_rate
# 4.  Mode A: grade below mean → probability below base_rate
# 5.  Mode A: grade at mean → probability within 0.03 of base_rate
# 6.  Mode B: probability equals base_rate (no grade adjustment)
# 7.  Inverted distribution in DB → Mode B fallback, not None
# 8.  verified=True → confidence "high" or "medium", not "low"
# 9.  Higher sensitivity → more spread between high and low grade outputs

# score_profile
# 10. Returns multiplier=1.0 when both texts empty (Mode 0)
# 11. Returns multiplier=1.0 when Ollama unreachable (mock HTTP call)
# 12. Selects Mode 1 when ec_text provided, no supplemental_text
# 13. Selects Mode 3 when supplemental_text provided, no ec_text
# 14. Mode 2 does not exist — passing both texts should raise or default
#     gracefully (caller should never pass both — test the boundary)
# 15. Handles Ollama response wrapped in json fences without crashing

# final_probability
# 16. Returns None when school+program not in BASE_RATES
# 17. Output clamped at 0.92 maximum
# 18. Output floored at 0.03 minimum
# 19. data_limited=True propagates when Mode B fires
# 20. disclaimer is not None when data_limited=True
# 21. supplemental_types=[] → profile_multiplier equals ec_multiplier only
# 22. interview in supplemental_types → 0.85 penalty regardless of other inputs
# 23. essay not completed → SUPPLEMENTAL_PENALTIES["essay"] applied
# 24. essay completed with text → Mode 3 score applied, no fixed penalty
# 25. essay completed without text → multiplier=1.0, no penalty
# 26. activity_list with text → Mode 1 score applied
# 27. multiple supplemental types → all multipliers composed independently
# 28. EC_CONSIDERED=False → ec_text ignored, ec_multiplier=1.0
# 29. school not in EC_CONSIDERED → ec_text respected (default True)
# 30. base × ec × supp1 × supp2 composition is correct (verify arithmetic)
```

Run all tests. Report full pytest output — do not summarize.

---

## What NOT to do

- Do not build supplemental_flags.py — it does not exist in this architecture
- Do not build Mode 2 in ec_scorer.py — it has been removed
- Do not preserve any old Bayesian formula code — rewrite calibrate.py fully
- Do not modify recommend.py, main.py, or any pipeline file
- Do not add new pip dependencies without asking (check scipy first)
- Do not hardcode school names into conditional branches anywhere except
  EC_CONSIDERED and the two profile dicts
- Do not call Ollama inside pytest tests — mock it
- Do not proceed to next phase without reporting

---

## Reporting Format

After each phase report:
1. What you built or found
2. Full outputs and test results — do not summarize, show everything
3. Decisions made and why
4. Any concerns or anomalies

Do not proceed without reporting.
