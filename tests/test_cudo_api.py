# tests/test_cudo_api.py
import pytest
from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)


def test_get_programs_returns_list():
    response = client.get("/programs")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_programs_has_new_fields():
    response = client.get("/programs")
    data = response.json()
    if len(data) > 0:
        first = data[0]
        assert "program_name" in first
        assert "program_category" in first
        assert "data_tier" in first
        assert first["data_tier"] in ("official", "community", "both")


def test_get_programs_category_filter():
    response = client.get("/programs?category=ENGINEERING")
    data = response.json()
    for item in data:
        assert item["program_category"] == "ENGINEERING"


def test_get_program_detail_returns_stats():
    response = client.get("/programs")
    data = response.json()
    if len(data) > 0:
        first = data[0]
        detail = client.get(
            f"/programs/{first['school']}/{first['program_name']}"
        )
        assert detail.status_code == 200
        d = detail.json()
        assert "grade_distribution" in d
        assert "ec_breakdown" in d
        assert "data_tier" in d
        assert "historical" in d
        assert "program_name" in d
        assert "program_category" in d


def test_get_program_detail_grade_buckets_have_pct():
    response = client.get("/programs")
    data = response.json()
    if len(data) > 0:
        first = data[0]
        detail = client.get(
            f"/programs/{first['school']}/{first['program_name']}"
        )
        d = detail.json()
        for bucket in d["grade_distribution"]:
            assert "pct" in bucket
            assert "bucket" in bucket
