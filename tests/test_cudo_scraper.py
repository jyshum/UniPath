# tests/test_cudo_scraper.py
import pytest
from pathlib import Path
from pipeline.cudo_scraper import parse_cudo_b3_table

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_parse_returns_list_of_dicts():
    html = (FIXTURE_DIR / "windsor_cudo_b3.html").read_text()
    results = parse_cudo_b3_table(html, school="University of Windsor", year=2023)
    assert isinstance(results, list)
    assert len(results) > 0


def test_parse_program_has_required_fields():
    html = (FIXTURE_DIR / "windsor_cudo_b3.html").read_text()
    results = parse_cudo_b3_table(html, school="University of Windsor", year=2023)
    required = {
        "school",
        "program_name",
        "program_category",
        "year",
        "pct_95_plus",
        "pct_90_94",
        "pct_85_89",
        "pct_80_84",
        "pct_75_79",
        "pct_70_74",
        "pct_below_70",
        "overall_avg",
    }
    for r in results:
        assert required.issubset(r.keys()), f"Missing keys: {required - r.keys()}"


def test_parse_percentages_are_floats():
    html = (FIXTURE_DIR / "windsor_cudo_b3.html").read_text()
    results = parse_cudo_b3_table(html, school="University of Windsor", year=2023)
    pct_fields = [
        "pct_95_plus",
        "pct_90_94",
        "pct_85_89",
        "pct_80_84",
        "pct_75_79",
        "pct_70_74",
        "pct_below_70",
    ]
    for r in results:
        for field in pct_fields:
            val = r[field]
            if val is not None:
                assert isinstance(val, float), f"{field} is {type(val)}"
                assert 0 <= val <= 100, f"{field} = {val}"


def test_parse_skips_overall_total_row():
    html = (FIXTURE_DIR / "windsor_cudo_b3.html").read_text()
    results = parse_cudo_b3_table(html, school="University of Windsor", year=2023)
    names = [r["program_name"] for r in results]
    for name in names:
        assert "total" not in name.lower()
        assert "overall" not in name.lower()


def test_parse_school_and_year_set():
    html = (FIXTURE_DIR / "windsor_cudo_b3.html").read_text()
    results = parse_cudo_b3_table(html, school="University of Windsor", year=2023)
    for r in results:
        assert r["school"] == "University of Windsor"
        assert r["year"] == 2023


def test_parse_overall_avg_is_float_or_none():
    html = (FIXTURE_DIR / "windsor_cudo_b3.html").read_text()
    results = parse_cudo_b3_table(html, school="University of Windsor", year=2023)
    for r in results:
        val = r["overall_avg"]
        if val is not None:
            assert isinstance(val, float), f"overall_avg is {type(val)}"
            assert 60 <= val <= 100, f"Unexpected overall_avg: {val}"


def test_parse_known_program_exists():
    """Windsor 2023 should contain Engineering."""
    html = (FIXTURE_DIR / "windsor_cudo_b3.html").read_text()
    results = parse_cudo_b3_table(html, school="University of Windsor", year=2023)
    names = [r["program_name"] for r in results]
    assert any("Engineering" in n for n in names), f"Engineering not found in {names}"


def test_parse_program_category_set():
    html = (FIXTURE_DIR / "windsor_cudo_b3.html").read_text()
    results = parse_cudo_b3_table(html, school="University of Windsor", year=2023)
    for r in results:
        assert r["program_category"], f"Empty category for {r['program_name']}"
        assert isinstance(r["program_category"], str)
