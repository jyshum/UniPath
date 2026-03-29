# calibrate.py
# Grade-distribution probability calibration anchored to published admission statistics.
# Replaces the previous Bayesian (accepted vs rejected DB rows) approach entirely.

import sqlite3
from scipy.stats import norm
import ec_scorer
from ec_scorer import score_profile

DB_PATH = "database/unipath.db"

# ── Data structures ───────────────────────────────────────────────────────────

# Published acceptance rates. Every combo shown to the user must appear here.
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

# Published admitted grade profiles. Subset of BASE_RATES.
# Combo in ADMITTED_PROFILES → Mode A (grade-adjusted).
# Combo in BASE_RATES only  → Mode B (base rate only, data_limited=True).
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

# Whether a school formally considers ECs in admissions.
# Used by final_probability() to decide whether to apply the EC multiplier.
# If a school is not listed, default is True.
EC_CONSIDERED: dict[str, bool] = {
    "UBC Vancouver":           True,
    "University of Waterloo":  True,
    "University of Toronto":   True,
    "Western University":      True,
    "Queen's University":      True,
    "McMaster University":     False,  # BHSc: grade + CASPer only, no CV/resume
    "Simon Fraser University": False,  # grade-only admission
}

# Fixed multiplier penalties applied when a supplemental exists but
# cannot be scored (interview always fixed; essay/AIF when not yet completed).
SUPPLEMENTAL_PENALTIES: dict[str, float] = {
    "essay":     0.92,
    "aif":       0.90,
    "interview": 0.85,
}

_MODE_B_DISCLAIMER = (
    "Based on published acceptance rate only. There may not be "
    "enough data on this program. This percentage is an estimate."
)


# ── Internal helper ───────────────────────────────────────────────────────────

def _mode_b(base_rate: float) -> dict:
    """Constructs a Mode B (base-rate-only) result dict."""
    return {
        "probability":   round(min(max(base_rate, 0.03), 0.92), 4),
        "confidence":    "estimate",
        "base_rate":     base_rate,
        "mean_admitted": None,
        "std_admitted":  None,
        "z_score":       None,
        "percentile":    None,
        "data_limited":  True,
        "disclaimer":    _MODE_B_DISCLAIMER,
        "mode":          "base_rate_only",
    }


# ── Core probability function ─────────────────────────────────────────────────

def calibrated_probability(
    school: str,
    program_category: str,
    grade: float,
    sensitivity: float = 1.5,
    conn=None,
) -> dict | None:
    """
    Returns None only when school+program is not in BASE_RATES at all.

    Gate structure:
        Gate 1 — In BASE_RATES?         No  → None
        Gate 2 — In ADMITTED_PROFILES?  No  → Mode B
        Gate 3 — verified flag          → sets confidence
        Gate 4 — Inverted DB check      → if inverted, fall back to Mode B

    Mode A output (grade-adjusted):
        probability     float   0.03–0.92 clamped
        confidence      str     "high" | "low"
        base_rate       float
        mean_admitted   float
        std_admitted    float
        z_score         float
        percentile      float
        data_limited    bool    False
        disclaimer      None
        mode            str     "grade_adjusted"

    Mode B output (base rate only):
        probability     float   0.03–0.92 (equals base_rate after clamp)
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
    program_category = program_category.upper()
    key = (school, program_category)

    # Gate 1 — must be in BASE_RATES
    if key not in BASE_RATES:
        return None
    base_rate = BASE_RATES[key]

    # Gate 2 — must be in ADMITTED_PROFILES to attempt Mode A
    if key not in ADMITTED_PROFILES:
        return _mode_b(base_rate)

    profile = ADMITTED_PROFILES[key]
    mean_admitted = profile["mean_admitted"]
    std_admitted  = profile["std_admitted"]
    verified      = profile.get("verified", False)

    # Gate 3 — confidence from verified flag
    confidence = "high" if verified else "low"

    # Gate 4 — inverted distribution check (query live DB)
    # If rejected students average higher grades than accepted ones, the grade
    # signal is inverted for this combo. Fall back to Mode B rather than produce
    # a counterintuitive result.
    _own_conn = conn is None
    _conn = None
    try:
        _conn = sqlite3.connect(DB_PATH) if _own_conn else conn
        dist_row = _conn.execute(
            "SELECT "
            "AVG(CASE WHEN decision = 'ACCEPTED' THEN core_avg END), "
            "AVG(CASE WHEN decision = 'REJECTED' THEN core_avg END) "
            "FROM students "
            "WHERE school_normalized = :school "
            "AND program_category = :program "
            "AND core_avg IS NOT NULL",
            {"school": school, "program": program_category},
        ).fetchone()
        avg_accepted = dist_row[0]
        avg_rejected = dist_row[1]
        if avg_accepted is not None and avg_rejected is not None:
            if avg_accepted <= avg_rejected:
                return _mode_b(base_rate)
    except Exception:
        pass  # DB unavailable (e.g. in isolated tests) — skip Gate 4, proceed Mode A
    finally:
        if _own_conn and _conn is not None:
            _conn.close()

    # Mode A — grade-adjusted probability via normal distribution
    z          = (grade - mean_admitted) / std_admitted
    percentile = float(norm.cdf(z))
    deviation  = percentile - 0.5
    adjustment = deviation * sensitivity
    raw        = base_rate * (1 + adjustment)
    probability = round(min(max(raw, 0.03), 0.92), 4)

    return {
        "probability":   probability,
        "confidence":    confidence,
        "base_rate":     base_rate,
        "mean_admitted": mean_admitted,
        "std_admitted":  std_admitted,
        "z_score":       round(z, 4),
        "percentile":    round(percentile, 4),
        "data_limited":  False,
        "disclaimer":    None,
        "mode":          "grade_adjusted",
    }


# ── Final probability (base × EC × supplemental multipliers) ─────────────────

def final_probability(
    school: str,
    program_category: str,
    grade: float,
    ec_text: str = "",
    supplemental_types: list[str] = [],
    supplemental_texts: dict[str, str] = {},
    supplemental_completed: dict[str, bool] = {},
    sensitivity: float = 1.5,
    conn=None,
) -> dict | None:
    """
    Computes: base_probability × EC_multiplier × supp_multiplier(s) → clamped 3%–92%.

    Step 1 — calibrated_probability() for base.
    Step 2 — EC multiplier (Ollama Mode 1 if school considers ECs and ec_text provided).
    Step 3 — One supplemental multiplier per type in supplemental_types.
    Step 4 — Compose all multipliers, clamp, return.

    Returns None only when school+program not in BASE_RATES.
    """
    # Step 1 — base probability
    base = calibrated_probability(school, program_category, grade, sensitivity, conn)
    if base is None:
        return None

    # Step 2 — EC multiplier
    ec_considered = EC_CONSIDERED.get(school, True)
    if ec_considered and ec_text.strip():
        ec_result = score_profile(ec_text=ec_text)
        ec_multiplier = ec_result["multiplier"]
    else:
        ec_multiplier = 1.0

    # Step 3 — supplemental multipliers (one per type, all independent)
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
                m = score_profile(supplemental_text=text)["multiplier"]  # Mode 3
                supp_multipliers.append(m)
            else:
                supp_multipliers.append(1.0)  # completed, no text — no penalty

        elif supp_type == "interview":
            supp_multipliers.append(SUPPLEMENTAL_PENALTIES["interview"])  # always fixed

        elif supp_type == "activity_list":
            text = supplemental_texts.get("activity_list", "")
            if text.strip():
                m = score_profile(ec_text=text)["multiplier"]  # Mode 1
                supp_multipliers.append(m)
            else:
                supp_multipliers.append(1.0)

    if not supp_multipliers:
        supp_multipliers = [1.0]

    # Step 4 — compose all multipliers on top of base
    profile_multiplier = ec_multiplier
    for m in supp_multipliers:
        profile_multiplier *= m

    raw = base["probability"] * profile_multiplier
    probability = round(min(max(raw, 0.03), 0.92), 4)

    return {
        "probability":        probability,
        "display_percent":    f"{round(probability * 100)}%",
        "base_probability":   base["probability"],
        "ec_multiplier":      ec_multiplier,
        "supp_multipliers":   supp_multipliers,
        "profile_multiplier": round(profile_multiplier, 6),
        "confidence":         base["confidence"],
        "base_rate":          base["base_rate"],
        "mean_admitted":      base["mean_admitted"],
        "std_admitted":       base["std_admitted"],
        "data_limited":       base["data_limited"],
        "disclaimer":         base["disclaimer"],
        "ec_considered":      ec_considered,
        "mode":               base["mode"],
    }
