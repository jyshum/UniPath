import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import server.main as server_main
from database.models import Student, init_db
from server.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_submit_db(tmp_path, monkeypatch):
    db_path = tmp_path / "submit.db"
    init_db(str(db_path))
    monkeypatch.setattr(server_main, "DB_PATH", str(db_path))
    server_main._engine = None
    yield db_path
    server_main._engine = None


def test_submit_valid_outcome(isolated_submit_db):
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

    engine = init_db(str(isolated_submit_db))
    with Session(engine) as session:
        assert session.query(Student).filter(Student.source == "USER_SUBMITTED").count() == 1


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
