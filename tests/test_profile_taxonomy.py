from core.profile_taxonomy import (
    extract_activity_signals,
    extract_course_signals,
    normalize_curriculum_type,
)


def test_extracts_deca_president_as_business_leadership():
    activities = extract_activity_signals("DECA president for 2 years, placed provincially")

    assert activities == [
        {
            "category": "BUSINESS",
            "activity_type": "DECA",
            "raw_text": "DECA president for 2 years, placed provincially",
            "role_level": "PRESIDENT",
            "duration_months": 24,
            "achievement_level": "PROVINCIAL",
            "program_relevance": "HIGH",
            "source_confidence": 0.9,
        }
    ]


def test_extracts_hackathon_founder_as_stem_entrepreneurial_signal():
    activities = extract_activity_signals("Founded coding club, won a hackathon, built an app")

    assert activities[0]["category"] == "STEM"
    assert activities[0]["activity_type"] == "HACKATHON"
    assert activities[0]["role_level"] == "FOUNDER"
    assert activities[0]["achievement_level"] == "LOCAL"
    assert activities[0]["program_relevance"] == "HIGH"


def test_extracts_ib_hl_courses():
    courses = extract_course_signals("IB HL Math 96, IB HL Chemistry 94, SL English 91")

    assert courses == [
        {
            "course_name": "Math",
            "course_subject": "MATH",
            "course_level": "IB_HL",
            "grade": 96.0,
            "is_required_for_program": False,
            "source_confidence": 0.85,
        },
        {
            "course_name": "Chemistry",
            "course_subject": "SCIENCE",
            "course_level": "IB_HL",
            "grade": 94.0,
            "is_required_for_program": False,
            "source_confidence": 0.85,
        },
        {
            "course_name": "English",
            "course_subject": "ENGLISH",
            "course_level": "IB_SL",
            "grade": 91.0,
            "is_required_for_program": False,
            "source_confidence": 0.8,
        },
    ]


def test_normalizes_curriculum_type():
    assert normalize_curriculum_type("IB HL Math and TOK") == "IB"
    assert normalize_curriculum_type("AP Calculus and AP Physics") == "AP"
    assert normalize_curriculum_type("regular BC curriculum") == "REGULAR"
    assert normalize_curriculum_type("") == "UNKNOWN"
