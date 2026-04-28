import pytest
from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)


def test_submit_valid_outcome():
    """Valid submission returns success."""
    response = client.post("/submit-outcome", json={
        "school": "UBC",
        "program": "Engineering",
        "grade": 94.5,
        "decision": "Accepted",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_submit_invalid_grade_rejected():
    """Grade outside 50-100 is rejected."""
    response = client.post("/submit-outcome", json={
        "school": "UBC",
        "program": "Engineering",
        "grade": 105,
        "decision": "Accepted",
    })
    assert response.status_code == 422 or response.json().get("error")


def test_submit_invalid_decision_rejected():
    """Invalid decision string is rejected."""
    response = client.post("/submit-outcome", json={
        "school": "UBC",
        "program": "Engineering",
        "grade": 90,
        "decision": "Maybe",
    })
    assert response.status_code == 422 or response.json().get("error")
