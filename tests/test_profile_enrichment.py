from sqlalchemy import inspect

from database.models import init_db


def test_init_db_creates_profile_tables(tmp_path):
    db_path = tmp_path / "profiles.db"
    engine = init_db(str(db_path))

    tables = set(inspect(engine).get_table_names())

    assert "applicant_profiles" in tables
    assert "applicant_courses" in tables
    assert "applicant_activities" in tables
