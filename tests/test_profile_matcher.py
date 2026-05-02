from sqlalchemy.orm import Session

from core.profile_matcher import get_program_archetypes, match_profiles
from database.models import (
    ApplicantActivity,
    ApplicantProfile,
    init_db,
)


def _profile(session, *, decision, grade, activity_type, category="BUSINESS", role="MEMBER"):
    profile = ApplicantProfile(
        source="USER_SUBMITTED",
        source_confidence=0.95,
        school_normalized="UBC Vancouver",
        program_normalized="Commerce",
        program_category="BUSINESS",
        decision=decision,
        decision_confidence=0.95,
        grade_average=grade,
        grade_context="CORE_AVERAGE",
        grade_confidence=0.95,
        curriculum_type="REGULAR",
        course_rigor_score=0.0,
        profile_completeness_score=0.8,
    )
    session.add(profile)
    session.flush()
    session.add(ApplicantActivity(
        profile_id=profile.id,
        category=category,
        activity_type=activity_type,
        role_level=role,
        achievement_level="PROVINCIAL" if role == "PRESIDENT" else "LOCAL",
        program_relevance="HIGH",
        source_confidence=0.9,
    ))
    return profile


def test_match_profiles_returns_nearest_accepted_and_rejected(tmp_path):
    db_path = tmp_path / "matcher.db"
    engine = init_db(str(db_path))
    with Session(engine) as session:
        _profile(session, decision="ACCEPTED", grade=94, activity_type="DECA", role="PRESIDENT")
        _profile(session, decision="ACCEPTED", grade=88, activity_type="ROBOTICS", category="STEM")
        _profile(session, decision="REJECTED", grade=92, activity_type="DECA")
        session.commit()

    result = match_profiles(
        str(db_path),
        {
            "school": "UBC Vancouver",
            "program": "Commerce",
            "grade_average": 93,
            "curriculum_type": "REGULAR",
            "activities": [{"category": "BUSINESS", "activity_type": "DECA", "role_level": "EXECUTIVE"}],
        },
    )

    assert result["data_confidence"]["label"] == "medium"
    assert result["grade_percentile"] == 67
    assert result["accepted_matches"][0]["decision"] == "ACCEPTED"
    assert result["accepted_matches"][0]["activity_types"] == ["DECA"]
    assert "DECA" in result["accepted_matches"][0]["match_explanation"]
    assert result["rejected_or_waitlisted_matches"][0]["decision"] == "REJECTED"


def test_archetypes_hide_low_support_groups(tmp_path):
    db_path = tmp_path / "archetypes.db"
    engine = init_db(str(db_path))
    with Session(engine) as session:
        _profile(session, decision="ACCEPTED", grade=94, activity_type="DECA", role="PRESIDENT")
        _profile(session, decision="ACCEPTED", grade=93, activity_type="BUSINESS_CLUB", role="EXECUTIVE")
        _profile(session, decision="ACCEPTED", grade=92, activity_type="ROBOTICS", category="STEM")
        session.commit()

    result = get_program_archetypes(str(db_path), "UBC Vancouver", "Commerce", min_support=2)

    assert result == [
        {
            "name": "Business leadership profile",
            "support_count": 2,
            "median_grade": 93.5,
            "common_activity_types": ["BUSINESS_CLUB", "DECA"],
            "common_role_levels": ["EXECUTIVE", "PRESIDENT"],
            "confidence_label": "medium",
        }
    ]
