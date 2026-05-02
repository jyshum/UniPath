from fastapi.testclient import TestClient

from server.main import app


client = TestClient(app)


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
