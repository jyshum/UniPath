from fastapi.testclient import TestClient
import pytest

from database.models import ApplicantActivity, ApplicantProfile, init_db
import server.main as server_main
from server.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def profile_api_db(tmp_path, monkeypatch):
    db_path = tmp_path / "profile_api.db"
    init_db(str(db_path))
    monkeypatch.setattr(server_main, "DB_PATH", str(db_path))
    return db_path


def _profile(session, *, school="UBC Vancouver", program="Commerce"):
    profile = ApplicantProfile(
        source="USER_SUBMITTED",
        source_confidence=0.95,
        school_normalized=school,
        program_normalized=program,
        program_category="BUSINESS",
        decision="ACCEPTED",
        decision_confidence=0.95,
        grade_average=93,
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
        category="BUSINESS",
        activity_type="DECA",
        role_level="EXECUTIVE",
        achievement_level="PROVINCIAL",
        program_relevance="HIGH",
        source_confidence=0.9,
    ))


def test_profile_api_uses_configured_tmp_db(profile_api_db):
    assert server_main._profile_db_path() == str(profile_api_db)


def test_profile_match_endpoint_returns_shape(profile_api_db):
    from sqlalchemy.orm import Session

    engine = init_db(str(profile_api_db))
    with Session(engine) as session:
        _profile(session)
        session.commit()

    response = client.post("/profile-match", json={
        "school": "UBC Vancouver",
        "program": "Commerce",
        "grade_average": 93,
        "curriculum_type": "REGULAR",
        "activities": [{"category": "BUSINESS", "activity_type": "DECA", "role_level": "EXECUTIVE"}],
    })

    assert response.status_code == 200
    data = response.json()
    assert "accepted_matches" in data
    assert "rejected_or_waitlisted_matches" in data
    assert "grade_percentile" in data
    assert "data_confidence" in data


def test_profile_match_endpoint_normalizes_school_and_program_aliases(profile_api_db):
    from sqlalchemy.orm import Session

    engine = init_db(str(profile_api_db))
    with Session(engine) as session:
        _profile(session)
        session.commit()

    response = client.post("/profile-match", json={
        "school": "UBC",
        "program": "Sauder",
        "grade_average": 93,
        "curriculum_type": "REGULAR",
        "activities": [{"category": "BUSINESS", "activity_type": "DECA"}],
    })

    assert response.status_code == 200
    assert response.json()["data_confidence"]["total_profiles"] == 1


def test_program_archetypes_endpoint_returns_list():
    response = client.get("/programs/UBC%20Vancouver/Commerce/archetypes")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_profiles_endpoint_accepts_anonymous_profile():
    response = client.post("/profiles", json={
        "school": "UBC Vancouver",
        "program": "Commerce",
        "grade_average": 94,
        "decision": "ACCEPTED",
        "province": "BC",
        "curriculum_type": "IB",
        "activities_text": "DECA president for 2 years",
    })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["normalized_school"] == "UBC Vancouver"
    assert data["normalized_program"] == "Commerce"
    assert data["activity_count"] >= 1
    assert all("raw_text" not in activity for activity in data["activities"])


def test_profiles_endpoint_rejects_invalid_grade():
    response = client.post("/profiles", json={
        "school": "UBC Vancouver",
        "program": "Commerce",
        "grade_average": 105,
    })

    assert response.status_code == 200
    assert response.json() == {"error": "grade_out_of_range"}


def test_profiles_endpoint_rejects_unknown_program():
    response = client.post("/profiles", json={
        "school": "UBC Vancouver",
        "program": "Underwater Basket Weaving",
        "grade_average": 94,
    })

    assert response.status_code == 200
    assert response.json() == {"error": "unknown_program"}
