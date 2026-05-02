from fastapi.testclient import TestClient
import pytest

from database.models import init_db
import server.main as server_main
from server.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def profile_api_db(tmp_path, monkeypatch):
    db_path = tmp_path / "profile_api.db"
    init_db(str(db_path))
    monkeypatch.setattr(server_main, "DB_PATH", str(db_path))
    return db_path


def test_profile_api_uses_configured_tmp_db(profile_api_db):
    assert server_main._profile_db_path() == str(profile_api_db)


def test_profile_match_endpoint_returns_shape():
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
