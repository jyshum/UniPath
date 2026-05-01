import json

import pytest
from sqlalchemy.orm import Session

from database.models import Student, init_db
from pipeline.reddit_agent import load_student


def _reddit_row(**overrides):
    row = {
        "source": "REDDIT_SCRAPED",
        "pulled_at": "2026-04-30T00:00:00+00:00",
        "school_raw": "Waterloo",
        "school_normalized": "University of Waterloo",
        "multi_school_flag": False,
        "program_raw": "Engineering",
        "program_category": "ENGINEERING",
        "program_normalized": "Engineering",
        "decision": "ACCEPTED",
        "grade_11_avg": None,
        "grade_12_avg": None,
        "core_avg": 94.5,
        "ec_tags": ["LEADERSHIP", "RESEARCH"],
        "circumstance_tags": ["NONE"],
        "province": "ON",
        "citizenship": "DOMESTIC",
        "scholarship": None,
        "comments_raw": None,
        "ec_raw": "robotics president and lab research",
        "circumstances_raw": None,
    }
    row.update(overrides)
    return row


def test_load_student_stores_tag_lists_as_single_json_layer(tmp_path):
    db_path = tmp_path / "reddit.db"
    engine = init_db(str(db_path))

    assert load_student(_reddit_row(), engine) is True

    with Session(engine) as session:
        student = session.query(Student).one()

    assert json.loads(student.ec_tags) == ["LEADERSHIP", "RESEARCH"]
    assert json.loads(student.circumstance_tags) == ["NONE"]
    assert student.program_normalized == "Engineering"


def test_load_student_does_not_treat_different_programs_as_duplicates(tmp_path):
    db_path = tmp_path / "reddit.db"
    engine = init_db(str(db_path))

    assert load_student(_reddit_row(program_raw="Engineering", program_category="ENGINEERING"), engine) is True
    assert load_student(_reddit_row(program_raw="Computer Science", program_category="COMPUTER_SCIENCE"), engine) is True

    with Session(engine) as session:
        rows = session.query(Student).all()

    assert len(rows) == 2


def test_load_student_reports_exact_duplicate_as_skipped(tmp_path):
    db_path = tmp_path / "reddit.db"
    engine = init_db(str(db_path))

    row = _reddit_row()
    assert load_student(row, engine) is True
    assert load_student(row, engine) is False

    with Session(engine) as session:
        assert session.query(Student).count() == 1
