# tests/test_program_stats.py
import pytest
import sqlite3
from core.recommend import program_stats, list_programs
from core import recommend


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


def test_program_stats_ec_breakdown_excludes_grade_only_rows_from_denominator(tmp_path, monkeypatch):
    db_path = tmp_path / "program_stats.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE students (
            school_normalized TEXT,
            program_normalized TEXT,
            program_category TEXT,
            decision TEXT,
            core_avg REAL,
            ec_tags TEXT,
            source TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE cudo_programs (
            school TEXT,
            program_name TEXT,
            program_category TEXT,
            year INTEGER,
            pct_95_plus REAL,
            pct_90_94 REAL,
            pct_85_89 REAL,
            pct_80_84 REAL,
            pct_75_79 REAL,
            pct_70_74 REAL,
            pct_below_70 REAL,
            overall_avg REAL
        )
        """
    )
    conn.executemany(
        "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("Test University", "Engineering", "ENGINEERING", "ACCEPTED", 95, '["LEADERSHIP"]', "REDDIT_SCRAPED"),
            ("Test University", "Engineering", "ENGINEERING", "ACCEPTED", 94, '["NONE"]', "REDDIT_SCRAPED"),
            ("Test University", "Engineering", "ENGINEERING", "ACCEPTED", 93, None, "REDDIT_SCRAPED"),
            ("Test University", "Engineering", "ENGINEERING", "REJECTED", 92, '["RESEARCH"]', "REDDIT_SCRAPED"),
        ],
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(recommend, "DB_PATH", db_path)

    result = program_stats("Test University", "Engineering")

    assert result["total_records"] == 4
    assert result["accepted_count"] == 3
    assert result["ec_breakdown"] == [{"tag": "LEADERSHIP", "count": 1, "pct": 100}]


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
