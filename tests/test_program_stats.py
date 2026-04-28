import pytest
import sqlite3
import json
from core.recommend import program_stats, list_programs


def test_program_stats_returns_expected_shape():
    """program_stats returns grade buckets, ec breakdown, and key stats."""
    result = program_stats("UBC Vancouver", "ENGINEERING")
    assert "grade_distribution" in result
    assert "ec_breakdown" in result
    assert "total_records" in result
    assert "avg_admitted_grade" in result
    assert result["total_records"] > 0


def test_program_stats_grade_distribution_has_buckets():
    """Grade distribution has accepted/rejected counts per bucket."""
    result = program_stats("UBC Vancouver", "ENGINEERING")
    dist = result["grade_distribution"]
    assert isinstance(dist, list)
    assert len(dist) > 0
    first = dist[0]
    assert "bucket" in first
    assert "accepted" in first
    assert "rejected" in first


def test_program_stats_ec_breakdown_has_percentages():
    """EC breakdown shows tag names with percentage of admitted students."""
    result = program_stats("UBC Vancouver", "ENGINEERING")
    ec = result["ec_breakdown"]
    assert isinstance(ec, list)
    for entry in ec:
        assert "tag" in entry
        assert "pct" in entry
        assert 0 <= entry["pct"] <= 100


def test_program_stats_unknown_combo_returns_empty():
    """Unknown school+program returns zero records."""
    result = program_stats("Fake University", "FAKE_PROGRAM")
    assert result["total_records"] == 0


def test_list_programs_returns_non_empty():
    """list_programs returns a list of combos with record counts."""
    result = list_programs()
    assert isinstance(result, list)
    assert len(result) > 0
    first = result[0]
    assert "school" in first
    assert "program" in first
    assert "total" in first
