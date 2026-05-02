import pytest
import subprocess
import sys
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from core.profile_enrichment import (
    ProfileEnrichmentError,
    build_profile_from_student,
    is_profile_eligible,
    upsert_profile_for_student,
)
from database.models import ApplicantActivity, ApplicantCourse, ApplicantProfile, Student, init_db


def test_init_db_creates_profile_tables(tmp_path):
    db_path = tmp_path / "profiles.db"
    engine = init_db(str(db_path))

    tables = set(inspect(engine).get_table_names())

    assert "applicant_profiles" in tables
    assert "applicant_courses" in tables
    assert "applicant_activities" in tables


def test_build_profile_from_student_extracts_profile_fields():
    student = Student(
        id=1,
        source="REDDIT_SCRAPED",
        school_normalized="UBC Vancouver",
        program_normalized="Commerce",
        program_category="BUSINESS",
        decision="ACCEPTED",
        province="BC",
        citizenship="DOMESTIC",
        core_avg=94.0,
        ec_raw="DECA president for 2 years, placed provincially. IB HL Math 96.",
    )

    profile, courses, activities = build_profile_from_student(student)

    assert profile.source_student_id == 1
    assert profile.source == "REDDIT_SCRAPED"
    assert profile.school_normalized == "UBC Vancouver"
    assert profile.program_normalized == "Commerce"
    assert profile.grade_average == 94.0
    assert profile.grade_context == "CORE_AVERAGE"
    assert profile.curriculum_type == "IB"
    assert profile.profile_completeness_score > 0.5
    assert courses[0].course_name == "Math"
    assert activities[0].activity_type == "DECA"


def test_incomplete_student_is_ineligible_and_raises_domain_error():
    student = Student(
        source="USER_SUBMITTED",
        core_avg=92.0,
        ec_raw="Student council president",
    )

    assert is_profile_eligible(student) is False

    with pytest.raises(ProfileEnrichmentError):
        build_profile_from_student(student)


def test_build_profile_from_student_deduplicates_course_mentions():
    student = Student(
        id=2,
        source="USER_SUBMITTED",
        school_normalized="UBC Vancouver",
        program_normalized="Engineering",
        program_category="ENGINEERING",
        core_avg=95.0,
        ec_raw="AP Physics 97. AP Physics 97.",
    )

    profile, courses, _activities = build_profile_from_student(student)

    assert len(courses) == 1
    assert courses[0].course_name == "Physics"
    assert profile.course_rigor_score == 0.25


def test_upsert_profile_for_student_is_idempotent(tmp_path):
    db_path = tmp_path / "profiles.db"
    engine = init_db(str(db_path))

    with Session(engine) as session:
        student = Student(
            source="USER_SUBMITTED",
            school_normalized="UBC Vancouver",
            program_normalized="Engineering",
            program_category="ENGINEERING",
            decision="ACCEPTED",
            core_avg=95.0,
            ec_raw="Robotics captain, AP Physics 97",
        )
        session.add(student)
        session.commit()
        student_id = student.id

        created_first = upsert_profile_for_student(session, student)
        created_second = upsert_profile_for_student(session, student)
        session.commit()

        assert created_first.id == created_second.id
        assert session.query(ApplicantProfile).count() == 1
        assert session.query(ApplicantActivity).count() == 1
        assert session.query(ApplicantCourse).count() == 1
        assert session.query(ApplicantProfile).first().source_student_id == student_id


def test_upsert_profile_for_student_does_not_rewrite_unchanged_profile(tmp_path):
    db_path = tmp_path / "profiles.db"
    engine = init_db(str(db_path))

    with Session(engine) as session:
        student = Student(
            source="USER_SUBMITTED",
            school_normalized="UBC Vancouver",
            program_normalized="Engineering",
            program_category="ENGINEERING",
            decision="ACCEPTED",
            core_avg=95.0,
            ec_raw="Robotics captain, AP Physics 97",
        )
        session.add(student)
        session.commit()

        profile = upsert_profile_for_student(session, student)
        session.commit()
        original_updated_at = profile.updated_at
        original_course_id = session.query(ApplicantCourse).one().id
        original_activity_id = session.query(ApplicantActivity).one().id

        upsert_profile_for_student(session, student)
        session.commit()

        unchanged_profile = session.query(ApplicantProfile).one()
        assert unchanged_profile.updated_at == original_updated_at
        assert session.query(ApplicantCourse).one().id == original_course_id
        assert session.query(ApplicantActivity).one().id == original_activity_id


from scripts.backfill_applicant_profiles import backfill_applicant_profiles


def test_backfill_applicant_profiles_skips_incomplete_rows(tmp_path):
    db_path = tmp_path / "profiles.db"
    engine = init_db(str(db_path))

    with Session(engine) as session:
        session.add_all([
            Student(
                source="BC_2025",
                school_normalized="UBC Vancouver",
                program_normalized="Science",
                program_category="SCIENCE",
                decision="ACCEPTED",
                core_avg=93.0,
                ec_raw="Science fair award",
            ),
            Student(
                source="BC_2025",
                school_normalized=None,
                program_normalized="Science",
                decision="ACCEPTED",
                core_avg=90.0,
            ),
        ])
        session.commit()

    summary = backfill_applicant_profiles(str(db_path))

    assert summary == {"checked": 2, "created_or_updated": 1, "skipped": 1}


def test_backfill_script_runs_when_executed_directly(tmp_path):
    db_path = tmp_path / "profiles.db"
    engine = init_db(str(db_path))

    with Session(engine) as session:
        session.add(Student(
            source="BC_2025",
            school_normalized="UBC Vancouver",
            program_normalized="Science",
            program_category="SCIENCE",
            decision="ACCEPTED",
            core_avg=93.0,
            ec_raw="Science fair award",
        ))
        session.commit()

    result = subprocess.run(
        [sys.executable, "scripts/backfill_applicant_profiles.py", str(db_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "'checked': 1" in result.stdout
    assert "'created_or_updated': 1" in result.stdout
