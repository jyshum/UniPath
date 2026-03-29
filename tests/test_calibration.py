# tests/test_calibration.py
# 30 pytest tests covering calibrated_probability, score_profile, final_probability.
# Ollama is never called — all Ollama interactions are mocked.
# DB interactions are controlled via injected mock connections.

import pytest
from unittest.mock import MagicMock, patch

from calibrate import (
    calibrated_probability,
    final_probability,
    BASE_RATES,
    ADMITTED_PROFILES,
    SUPPLEMENTAL_PENALTIES,
)
from ec_scorer import score_profile


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_conn(avg_accepted, avg_rejected):
    """Returns a mock sqlite3 connection whose fetchone returns the given averages."""
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (avg_accepted, avg_rejected)
    return conn


def mode1_result(multiplier=1.20):
    """Stub score_profile Mode 1 return dict."""
    return {
        "multiplier": multiplier,
        "mode":       1,
        "scores":     {"leadership": 7.0, "commitment": 8.0, "impact": 6.0, "relevance": 8.0},
        "reasoning":  "Strong EC profile with sustained leadership.",
        "raw_avg":    7.25,
    }


def mode3_result(multiplier=1.08):
    """Stub score_profile Mode 3 return dict."""
    return {
        "multiplier": multiplier,
        "mode":       3,
        "scores":     {"clarity": 7.0, "self_awareness": 7.0, "curiosity": 7.0, "fit": 7.5},
        "reasoning":  "Clear, self-aware supplemental answer.",
        "raw_avg":    7.13,
    }


# ── calibrated_probability (Tests 1–9) ───────────────────────────────────────

def test_1_returns_none_for_unknown_combo():
    """Gate 1: school+program not in BASE_RATES → None."""
    result = calibrated_probability("University of Ottawa", "ENGINEERING", grade=85.0)
    assert result is None


def test_2_returns_mode_b_for_base_rates_only_combo():
    """Gate 2: combo in BASE_RATES but not ADMITTED_PROFILES → Mode B, data_limited=True."""
    # UofT SCIENCE is in BASE_RATES (0.40) but has no ADMITTED_PROFILES entry
    result = calibrated_probability("University of Toronto", "SCIENCE", grade=90.0)
    assert result is not None
    assert result["data_limited"] is True
    assert result["mode"] == "base_rate_only"
    assert result["mean_admitted"] is None
    assert result["std_admitted"] is None


def test_3_grade_above_mean_probability_above_base_rate():
    """Mode A: grade above admitted mean → probability > base_rate."""
    conn = make_conn(avg_accepted=95.0, avg_rejected=88.0)  # not inverted
    result = calibrated_probability("UBC Vancouver", "ENGINEERING", grade=95.0, conn=conn)
    assert result is not None
    assert result["mode"] == "grade_adjusted"
    assert result["probability"] > result["base_rate"]


def test_4_grade_below_mean_probability_below_base_rate():
    """Mode A: grade below admitted mean → probability < base_rate."""
    conn = make_conn(avg_accepted=95.0, avg_rejected=88.0)
    result = calibrated_probability("UBC Vancouver", "ENGINEERING", grade=85.0, conn=conn)
    assert result is not None
    assert result["mode"] == "grade_adjusted"
    assert result["probability"] < result["base_rate"]


def test_5_grade_at_mean_probability_within_tolerance_of_base_rate():
    """Mode A: grade exactly at admitted mean → probability within 0.03 of base_rate."""
    conn = make_conn(avg_accepted=95.0, avg_rejected=88.0)
    mean = ADMITTED_PROFILES[("UBC Vancouver", "ENGINEERING")]["mean_admitted"]  # 90.0
    base_rate = BASE_RATES[("UBC Vancouver", "ENGINEERING")]                     # 0.32
    result = calibrated_probability("UBC Vancouver", "ENGINEERING", grade=mean, conn=conn)
    assert result is not None
    assert abs(result["probability"] - base_rate) <= 0.03


def test_6_mode_b_probability_equals_clamped_base_rate():
    """Mode B: probability is the base_rate (clamped to 0.03–0.92, no grade shift)."""
    result = calibrated_probability("University of Toronto", "SCIENCE", grade=90.0)
    assert result is not None
    base_rate = BASE_RATES[("University of Toronto", "SCIENCE")]  # 0.40
    expected = round(min(max(base_rate, 0.03), 0.92), 4)
    assert result["probability"] == expected


def test_7_inverted_distribution_falls_back_to_mode_b_not_none():
    """Gate 4: avg_accepted ≤ avg_rejected → Mode B fallback, NOT None."""
    conn = make_conn(avg_accepted=93.0, avg_rejected=93.5)  # inverted
    result = calibrated_probability("UBC Vancouver", "ENGINEERING", grade=90.0, conn=conn)
    assert result is not None
    assert result["mode"] == "base_rate_only"
    assert result["data_limited"] is True


def test_8_verified_true_yields_high_or_medium_confidence_not_low():
    """Gate 3: verified=True → confidence is 'high' or 'medium', never 'low'."""
    conn = make_conn(avg_accepted=95.0, avg_rejected=88.0)
    result = calibrated_probability("UBC Vancouver", "ENGINEERING", grade=90.0, conn=conn)
    assert result is not None
    assert result["confidence"] in ("high", "medium")
    assert result["confidence"] != "low"


def test_9_higher_sensitivity_increases_probability_spread():
    """Higher sensitivity → larger spread between high-grade and low-grade outputs."""
    low_grade  = 84.0
    high_grade = 96.0

    r_low_s1  = calibrated_probability("UBC Vancouver", "ENGINEERING", low_grade,  sensitivity=1.0, conn=make_conn(95.0, 88.0))
    r_high_s1 = calibrated_probability("UBC Vancouver", "ENGINEERING", high_grade, sensitivity=1.0, conn=make_conn(95.0, 88.0))
    r_low_s3  = calibrated_probability("UBC Vancouver", "ENGINEERING", low_grade,  sensitivity=3.0, conn=make_conn(95.0, 88.0))
    r_high_s3 = calibrated_probability("UBC Vancouver", "ENGINEERING", high_grade, sensitivity=3.0, conn=make_conn(95.0, 88.0))

    spread_s1 = r_high_s1["probability"] - r_low_s1["probability"]
    spread_s3 = r_high_s3["probability"] - r_low_s3["probability"]
    assert spread_s3 > spread_s1


# ── score_profile (Tests 10–15) ───────────────────────────────────────────────

def test_10_mode_0_no_text_returns_multiplier_1_no_ollama_call():
    """Mode 0: no text → multiplier=1.0, mode=0, no Ollama call."""
    with patch("ec_scorer.ollama.chat") as mock_chat:
        result = score_profile()
    assert result["multiplier"] == 1.0
    assert result["mode"] == 0
    assert result["scores"] == {}
    mock_chat.assert_not_called()


def test_11_ollama_unreachable_returns_multiplier_1_no_crash():
    """Ollama failure (exception) → multiplier=1.0, never raises."""
    with patch("ec_scorer.ollama.chat", side_effect=Exception("connection refused")):
        result = score_profile(ec_text="Led robotics club for three years")
    assert result["multiplier"] == 1.0


def test_12_ec_text_only_selects_mode_1():
    """ec_text provided, supplemental_text empty → Mode 1, EC dimensions scored."""
    payload = '{"leadership": 7, "commitment": 8, "impact": 6, "relevance": 8, "reasoning": "Solid."}'
    with patch("ec_scorer.ollama.chat", return_value={"message": {"content": payload}}):
        result = score_profile(ec_text="Robotics club president for three years")
    assert result["mode"] == 1
    assert set(result["scores"].keys()) == {"leadership", "commitment", "impact", "relevance"}


def test_13_supplemental_text_only_selects_mode_3():
    """supplemental_text provided, ec_text empty → Mode 3, essay dimensions scored."""
    payload = '{"clarity": 8, "self_awareness": 7, "curiosity": 7, "fit": 8, "reasoning": "Clear."}'
    with patch("ec_scorer.ollama.chat", return_value={"message": {"content": payload}}):
        result = score_profile(supplemental_text="Q: Why engineering?\nA: I love building things.")
    assert result["mode"] == 3
    assert set(result["scores"].keys()) == {"clarity", "self_awareness", "curiosity", "fit"}


def test_14_both_texts_provided_mode_1_takes_priority_no_crash():
    """Both ec_text and supplemental_text → Mode 1 fires (ec_text priority), no crash."""
    payload = '{"leadership": 7, "commitment": 8, "impact": 6, "relevance": 8, "reasoning": "Good."}'
    with patch("ec_scorer.ollama.chat", return_value={"message": {"content": payload}}):
        result = score_profile(
            ec_text="Robotics president",
            supplemental_text="Q: Why this program?\nA: I love it.",
        )
    assert result["mode"] == 1
    assert "leadership" in result["scores"]


def test_15_markdown_fenced_json_parsed_without_crash():
    """Ollama response wrapped in ```json ... ``` fences → parsed correctly, no crash."""
    raw = "```json\n{\"leadership\": 9, \"commitment\": 9, \"impact\": 8, \"relevance\": 9, \"reasoning\": \"Excellent.\"}\n```"
    with patch("ec_scorer.ollama.chat", return_value={"message": {"content": raw}}):
        result = score_profile(ec_text="Award-winning researcher and team lead")
    # avg = (9+9+8+9)/4 = 8.75 → multiplier = 1.375
    assert result["multiplier"] == 1.375
    assert result["mode"] == 1


# ── final_probability (Tests 16–30) ──────────────────────────────────────────

def test_16_returns_none_for_unknown_combo():
    """Returns None when school+program not in BASE_RATES."""
    result = final_probability("University of Ottawa", "ENGINEERING", grade=85.0)
    assert result is None


def test_17_output_clamped_at_0_92_maximum():
    """Raw probability above 0.92 is clamped to 0.92."""
    # UBC Science: base_rate=0.52, mean=88, std=3.
    # grade=98 → z=3.33, percentile≈0.9996, deviation≈0.5, raw=0.52*1.75=0.91 (near cap at base).
    # Then EC multiplier 1.375 pushes it well above 0.92.
    conn = make_conn(avg_accepted=95.0, avg_rejected=88.0)
    with patch("calibrate.score_profile", return_value=mode1_result(multiplier=1.375)):
        result = final_probability(
            "UBC Vancouver", "SCIENCE", grade=98.0,
            ec_text="Extensive activities",
            conn=conn,
        )
    assert result is not None
    assert result["probability"] <= 0.92


def test_18_output_floored_at_0_03_minimum():
    """Raw probability below 0.03 is floored to 0.03."""
    # McMaster HEALTH: base_rate=0.05, mean=93, std=2.
    # grade=60 → z=-16.5, percentile≈0, raw≈0.05*0.25=0.0125 → base already clamped to 0.03.
    # interview penalty (0.85) pushes below 0.03 → clamped to 0.03 in final.
    conn = make_conn(avg_accepted=95.0, avg_rejected=88.0)
    result = final_probability(
        "McMaster University", "HEALTH", grade=60.0,
        supplemental_types=["interview"],
        conn=conn,
    )
    assert result is not None
    assert result["probability"] >= 0.03


def test_19_data_limited_true_propagates_from_mode_b():
    """data_limited=True from calibrated_probability propagates through final_probability."""
    # UofT SCIENCE: in BASE_RATES only → always Mode B
    result = final_probability("University of Toronto", "SCIENCE", grade=90.0)
    assert result is not None
    assert result["data_limited"] is True


def test_20_disclaimer_not_none_when_data_limited():
    """When data_limited=True, disclaimer is a non-empty string."""
    result = final_probability("University of Toronto", "SCIENCE", grade=90.0)
    assert result is not None
    assert result["disclaimer"] is not None
    assert isinstance(result["disclaimer"], str)
    assert len(result["disclaimer"]) > 0


def test_21_empty_supplemental_types_profile_multiplier_equals_ec_multiplier():
    """supplemental_types=[] → profile_multiplier is exactly the ec_multiplier."""
    conn = make_conn(avg_accepted=95.0, avg_rejected=88.0)
    ec_mult = 1.20
    with patch("calibrate.score_profile", return_value=mode1_result(multiplier=ec_mult)):
        result = final_probability(
            "UBC Vancouver", "ENGINEERING", grade=90.0,
            ec_text="Active in many activities",
            supplemental_types=[],
            conn=conn,
        )
    assert result["ec_multiplier"] == ec_mult
    assert result["profile_multiplier"] == pytest.approx(ec_mult, rel=1e-5)


def test_22_interview_applies_0_85_penalty_regardless_of_other_inputs():
    """interview type → 0.85 fixed penalty always, even with completed=True and text."""
    conn = make_conn(avg_accepted=95.0, avg_rejected=88.0)
    result = final_probability(
        "UBC Vancouver", "ENGINEERING", grade=90.0,
        supplemental_types=["interview"],
        supplemental_completed={"interview": True},
        supplemental_texts={"interview": "I aced my interview."},
        conn=conn,
    )
    assert result is not None
    assert result["supp_multipliers"] == [SUPPLEMENTAL_PENALTIES["interview"]]  # [0.85]


def test_23_essay_not_completed_applies_fixed_penalty():
    """essay not completed → SUPPLEMENTAL_PENALTIES["essay"] = 0.92 applied."""
    conn = make_conn(avg_accepted=95.0, avg_rejected=88.0)
    result = final_probability(
        "UBC Vancouver", "ENGINEERING", grade=90.0,
        supplemental_types=["essay"],
        supplemental_completed={"essay": False},
        conn=conn,
    )
    assert result is not None
    assert result["supp_multipliers"] == [SUPPLEMENTAL_PENALTIES["essay"]]  # [0.92]


def test_24_essay_completed_with_text_applies_mode_3_score_not_fixed_penalty():
    """essay completed with text → Mode 3 Ollama score applied, fixed penalty NOT used."""
    conn = make_conn(avg_accepted=95.0, avg_rejected=88.0)
    scored_mult = 1.08
    with patch("calibrate.score_profile", return_value=mode3_result(multiplier=scored_mult)):
        result = final_probability(
            "UBC Vancouver", "ENGINEERING", grade=90.0,
            supplemental_types=["essay"],
            supplemental_completed={"essay": True},
            supplemental_texts={"essay": "Q: Why UBC?\nA: Excellent research culture."},
            conn=conn,
        )
    assert result is not None
    assert scored_mult in result["supp_multipliers"]
    assert SUPPLEMENTAL_PENALTIES["essay"] not in result["supp_multipliers"]


def test_25_essay_completed_without_text_multiplier_is_1():
    """essay completed but no text pasted → multiplier=1.0, no penalty."""
    conn = make_conn(avg_accepted=95.0, avg_rejected=88.0)
    result = final_probability(
        "UBC Vancouver", "ENGINEERING", grade=90.0,
        supplemental_types=["essay"],
        supplemental_completed={"essay": True},
        supplemental_texts={},  # no text provided
        conn=conn,
    )
    assert result is not None
    assert result["supp_multipliers"] == [1.0]


def test_26_activity_list_with_text_applies_mode_1_score():
    """activity_list with text → Mode 1 Ollama score applied."""
    conn = make_conn(avg_accepted=95.0, avg_rejected=88.0)
    scored_mult = 1.20
    with patch("calibrate.score_profile", return_value=mode1_result(multiplier=scored_mult)):
        result = final_probability(
            "UBC Vancouver", "ENGINEERING", grade=90.0,
            supplemental_types=["activity_list"],
            supplemental_texts={"activity_list": "Robotics, volleyball, coding club."},
            conn=conn,
        )
    assert result is not None
    assert scored_mult in result["supp_multipliers"]


def test_27_multiple_supplemental_types_composed_independently():
    """Multiple supplemental types → each multiplier applied independently, correct product."""
    conn = make_conn(avg_accepted=95.0, avg_rejected=88.0)
    # essay not completed → 0.92 penalty; interview → 0.85 fixed
    result = final_probability(
        "UBC Vancouver", "ENGINEERING", grade=90.0,
        supplemental_types=["essay", "interview"],
        supplemental_completed={"essay": False},
        conn=conn,
    )
    assert result is not None
    assert len(result["supp_multipliers"]) == 2
    assert 0.92 in result["supp_multipliers"]
    assert 0.85 in result["supp_multipliers"]
    expected_profile_mult = 1.0 * 0.92 * 0.85  # ec=1.0 (no ec_text) × two supp multipliers
    assert result["profile_multiplier"] == pytest.approx(expected_profile_mult, rel=1e-5)


def test_28_ec_considered_false_ignores_ec_text():
    """EC_CONSIDERED=False for school → ec_text ignored, ec_multiplier=1.0, score_profile not called for EC."""
    conn = make_conn(avg_accepted=95.0, avg_rejected=88.0)
    with patch("calibrate.score_profile") as mock_sp:
        result = final_probability(
            "Simon Fraser University", "ENGINEERING", grade=85.0,
            ec_text="Award-winning researcher and team lead",
            conn=conn,
        )
    assert result["ec_multiplier"] == 1.0
    assert result["ec_considered"] is False
    mock_sp.assert_not_called()


def test_29_school_not_in_ec_considered_defaults_to_true_and_respects_ec_text():
    """school absent from EC_CONSIDERED dict → default True → ec_text IS scored."""
    conn = make_conn(avg_accepted=95.0, avg_rejected=88.0)
    ec_mult = 1.20
    # Clear EC_CONSIDERED entirely so UBC Vancouver is no longer listed
    with patch.dict("calibrate.EC_CONSIDERED", {}, clear=True):
        with patch("calibrate.score_profile", return_value=mode1_result(multiplier=ec_mult)):
            result = final_probability(
                "UBC Vancouver", "ENGINEERING", grade=90.0,
                ec_text="Many great extracurriculars",
                conn=conn,
            )
    assert result["ec_multiplier"] == ec_mult
    assert result["ec_considered"] is True


def test_30_arithmetic_composition_is_correct():
    """base × ec × supp1 × supp2 = expected probability (verify exact arithmetic)."""
    ec_mult    = 1.20
    supp1_mult = 0.92   # essay not completed
    supp2_mult = 0.85   # interview fixed

    base = calibrated_probability(
        "UBC Vancouver", "ENGINEERING", grade=90.0,
        conn=make_conn(avg_accepted=95.0, avg_rejected=88.0),
    )
    base_prob = base["probability"]

    conn = make_conn(avg_accepted=95.0, avg_rejected=88.0)
    with patch("calibrate.score_profile", return_value=mode1_result(multiplier=ec_mult)):
        result = final_probability(
            "UBC Vancouver", "ENGINEERING", grade=90.0,
            ec_text="Active in many activities",
            supplemental_types=["essay", "interview"],
            supplemental_completed={"essay": False},
            conn=conn,
        )

    expected_profile_mult = ec_mult * supp1_mult * supp2_mult
    expected_raw          = base_prob * expected_profile_mult
    expected_prob         = round(min(max(expected_raw, 0.03), 0.92), 4)

    assert result["probability"]        == expected_prob
    assert result["profile_multiplier"] == pytest.approx(expected_profile_mult, rel=1e-5)
    assert result["base_probability"]   == base_prob
    assert result["display_percent"]    == f"{round(expected_prob * 100)}%"
