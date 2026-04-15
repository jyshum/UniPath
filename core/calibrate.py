# calibrate.py
# Grade-distribution probability calibration anchored to published admission statistics.
# Replaces the previous Bayesian (accepted vs rejected DB rows) approach entirely.

import sqlite3
from pathlib import Path
from scipy.stats import norm
from core import ec_scorer
from core.ec_scorer import score_profile

DB_PATH = Path(__file__).parent.parent / "database" / "unipath.db"

# ── Data structures ───────────────────────────────────────────────────────────

# Published acceptance rates. Every combo shown to the user must appear here.
BASE_RATES: dict[tuple[str, str], float] = {
    ("UBC Vancouver",           "ENGINEERING"):      0.27,
    ("UBC Vancouver",           "SCIENCE"):          0.25,
    ("UBC Vancouver",           "BUSINESS"):         0.15,
    ("UBC Vancouver",           "HEALTH"):           0.18,
    ("UBC Vancouver",           "ARTS"):             0.45,
    ("University of Waterloo",  "COMPUTER_SCIENCE"): 0.06,
    ("University of Waterloo",  "ENGINEERING"):      0.15,
    ("University of Toronto",   "ENGINEERING"):      0.30,
    ("University of Toronto",   "COMPUTER_SCIENCE"): 0.08,
    ("University of Toronto",   "BUSINESS"):         0.15,
    ("University of Toronto",   "SCIENCE"):          0.45,
    ("Western University",      "BUSINESS"):         0.09,
    ("Queen's University",      "BUSINESS"):         0.07,
    ("McMaster University",     "HEALTH"):           0.06,
    ("Simon Fraser University", "ENGINEERING"):      0.58,
    ("Simon Fraser University", "SCIENCE"):          0.65,
    ("Simon Fraser University", "BUSINESS"):         0.55,
}

# Published admitted grade profiles. Subset of BASE_RATES.
# Combo in ADMITTED_PROFILES → Mode A (grade-adjusted).
# Combo in BASE_RATES only  → Mode B (base rate only, data_limited=True).
ADMITTED_PROFILES: dict[tuple[str, str], dict] = {
    ("UBC Vancouver", "ENGINEERING"): {
        "mean_admitted": 93.0,
        "std_admitted":  2.0,
        "verified":      True,
        "source":        "UBC Wiki 2024 + UBC Engineering entrance chart — admitted range 91-94%",
    },
    ("UBC Vancouver", "SCIENCE"): {
        "mean_admitted": 93.0,
        "std_admitted":  2.5,
        "verified":      True,
        "source":        "UBC Wiki 2018 — domestic Science incoming avg 93.8%",
    },
    ("UBC Vancouver", "BUSINESS"): {
        "mean_admitted": 93.0,
        "std_admitted":  2.0,
        "verified":      True,
        "source":        "GrantMe + Youthfully Sauder guide — domestic incoming avg ~93%",
    },
    ("University of Waterloo", "COMPUTER_SCIENCE"): {
        "mean_admitted": 95.5,
        "std_admitted":  1.5,
        "verified":      True,
        "source":        "Youthfully + LiwinCo — competitive threshold 95%+, most admits above 95%",
    },
    ("University of Waterloo", "ENGINEERING"): {
        "mean_admitted": 91.5,
        "std_admitted":  3.0,
        "verified":      True,
        "source":        "Youthfully Waterloo Engineering guide — range 88-95% across disciplines; Software ~95+, Civil/Chem lower",
    },
    ("University of Toronto", "ENGINEERING"): {
        "mean_admitted": 95.4,
        "std_admitted":  1.5,
        "verified":      True,
        "source":        "UofT Engineering By The Numbers 2024 — OFFICIAL; 2020 Ontario avg 94.5%, current est. 95.4%",
    },
    ("University of Toronto", "COMPUTER_SCIENCE"): {
        "mean_admitted": 96.0,
        "std_admitted":  1.5,
        "verified":      True,
        "source":        "CollegeVine + Youthfully — mid to high 90s, competitive threshold 95%+",
    },
    ("University of Toronto", "BUSINESS"): {
        "mean_admitted": 92.5,
        "std_admitted":  2.0,
        "verified":      True,
        "source":        "Uniscope CUDO data — largest share admitted 90-94% (32.9%) and 95%+ (29.5%)",
    },
    ("Western University", "BUSINESS"): {
        "mean_admitted": 93.0,
        "std_admitted":  2.0,
        "verified":      True,
        "source":        "Youthfully Ivey AEO guide + GrantMe — 93%+ competitive benchmark for AEO designation",
    },
    ("Queen's University", "BUSINESS"): {
        "mean_admitted": 92.0,
        "std_admitted":  2.0,
        "verified":      True,
        "source":        "Youthfully + MasterStudent — historical avg 91.7% (2014) rising to 92.7% (2016), est. ~92% current",
    },
    ("McMaster University", "HEALTH"): {
        "mean_admitted": 94.5,
        "std_admitted":  1.5,
        "verified":      True,
        "source":        "Youthfully + GrantMe BHSc guide — ~88% of admitted students have 94%+",
    },
    ("Simon Fraser University", "ENGINEERING"): {
        "mean_admitted": 86.0,
        "std_admitted":  3.0,
        "verified":      True,
        "source":        "SFU official historical admission grade ranges — mid 80s for Engineering Science",
    },
    ("Simon Fraser University", "SCIENCE"): {
        "mean_admitted": 85.0,
        "std_admitted":  3.0,
        "verified":      True,
        "source":        "SFU official historical admission grade ranges — mid 80s for Science programs",
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
    "aif":       0.95,
    "interview": 1.00,
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
    supplemental_types: list[str] = [],
    supplemental_texts: dict[str, str] = {},
    supplemental_completed: dict[str, bool] = {},
    sensitivity: float = 1.5,
    conn=None,
) -> dict | None:
    """
    Computes: base_probability × supp_multiplier(s) → clamped 3%–92%.

    Step 1 — calibrated_probability() for base.
    Step 2 — One supplemental multiplier per type in supplemental_types.
    Step 3 — Compose all multipliers, clamp, return.

    Returns None only when school+program not in BASE_RATES.
    """
    # Step 1 — base probability
    base = calibrated_probability(school, program_category, grade, sensitivity, conn)
    if base is None:
        return None

    # Step 2 — supplemental multipliers (one per type, all independent)
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

    # Step 3 — compose all multipliers on top of base
    profile_multiplier = 1.0
    for m in supp_multipliers:
        profile_multiplier *= m

    raw = base["probability"] * profile_multiplier
    probability = round(min(max(raw, 0.03), 0.92), 4)

    return {
        "probability":        probability,
        "display_percent":    f"{round(probability * 100)}%",
        "base_probability":   base["probability"],
        "supp_multipliers":   supp_multipliers,
        "profile_multiplier": round(profile_multiplier, 6),
        "confidence":         base["confidence"],
        "base_rate":          base["base_rate"],
        "mean_admitted":      base["mean_admitted"],
        "std_admitted":       base["std_admitted"],
        "data_limited":       base["data_limited"],
        "disclaimer":         base["disclaimer"],
        "mode":               base["mode"],
    }
