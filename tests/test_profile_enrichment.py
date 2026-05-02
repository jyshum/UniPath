from sqlalchemy import inspect
from sqlalchemy.orm import Session

from core.profile_enrichment import build_profile_from_student, upsert_profile_for_student
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
