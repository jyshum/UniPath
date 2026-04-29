# tests/test_program_stats.py
import pytest
from core.recommend import program_stats, list_programs


def test_program_stats_returns_expected_shape():
    result = program_stats("UBC Vancouver", "Engineering")
    assert "grade_distribution" in result
    assert "ec_breakdown" in result
    assert "total_records" in result
    assert "data_tier" in result
    assert "program_name" in result


def test_program_stats_grade_distribution_has_buckets():
    result = program_stats("UBC Vancouver", "Engineering")
    dist = result["grade_distribution"]
    assert isinstance(dist, list)
    assert len(dist) > 0
    first = dist[0]
    assert "bucket" in first
    assert "pct" in first


def test_program_stats_ec_breakdown_has_percentages():
    result = program_stats("UBC Vancouver", "Engineering")
    ec = result["ec_breakdown"]
    assert isinstance(ec, list)
    for entry in ec:
        assert "tag" in entry
        assert "pct" in entry
        assert 0 <= entry["pct"] <= 100


def test_program_stats_unknown_combo_returns_error():
    result = program_stats("Fake University", "Fake Program")
    assert result.get("error") == "no_data"


def test_list_programs_returns_non_empty():
    result = list_programs()
    assert isinstance(result, list)
    assert len(result) > 0
    first = result[0]
    assert "school" in first
    assert "program_name" in first
    assert "program_category" in first
    assert "data_tier" in first


def test_list_programs_category_filter():
    all_programs = list_programs()
    eng_programs = list_programs(category="ENGINEERING")
    assert len(eng_programs) <= len(all_programs)
    for p in eng_programs:
        assert p["program_category"] == "ENGINEERING"
