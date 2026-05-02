# database/models.py

from sqlalchemy import (
    Column, Integer, Float, String, Boolean, DateTime, Text, create_engine,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Student(Base):
    __tablename__ = "students"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Provenance
    source = Column(String, nullable=False)          # "BC" or "Ontario"
    pulled_at = Column(String, nullable=True)        # ISO timestamp string

    # School
    school_raw = Column(Text, nullable=True)
    school_normalized = Column(String, nullable=True)
    multi_school_flag = Column(Boolean, default=False)

    # Program
    program_raw = Column(Text, nullable=True)
    program_category = Column(String, nullable=True)  # ENGINEERING, SCIENCE, etc.
    program_normalized = Column(String, nullable=True)  # canonical program name

    # Decision
    decision = Column(String, nullable=True)          # ACCEPTED, REJECTED, etc.

    # Grades
    grade_11_avg = Column(Float, nullable=True)
    grade_12_avg = Column(Float, nullable=True)
    core_avg = Column(Float, nullable=True)

    # Tags (stored as JSON arrays)
    ec_tags = Column(Text, nullable=True)             # '["SPORTS", "ARTS"]'
    circumstance_tags = Column(Text, nullable=True)   # '["INTERNATIONAL"]'

    # Location and citizenship
    province = Column(String, nullable=True)
    citizenship = Column(String, nullable=True)       # DOMESTIC or INTERNATIONAL

    # Extras
    scholarship = Column(Text, nullable=True)
    comments_raw = Column(Text, nullable=True)
    ec_raw = Column(Text, nullable=True)
    circumstances_raw = Column(Text, nullable=True)


class CudoProgram(Base):
    __tablename__ = "cudo_programs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school = Column(String, nullable=False)
    program_name = Column(String, nullable=False)
    program_category = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    pct_95_plus = Column(Float, nullable=True)
    pct_90_94 = Column(Float, nullable=True)
    pct_85_89 = Column(Float, nullable=True)
    pct_80_84 = Column(Float, nullable=True)
    pct_75_79 = Column(Float, nullable=True)
    pct_70_74 = Column(Float, nullable=True)
    pct_below_70 = Column(Float, nullable=True)
    overall_avg = Column(Float, nullable=True)
    source_url = Column(String, nullable=True)


class ApplicantProfile(Base):
    __tablename__ = "applicant_profiles"
    __table_args__ = (
        UniqueConstraint("source_student_id", name="uq_applicant_profiles_source_student_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    source = Column(String, nullable=False)
    source_url = Column(Text, nullable=True)
    source_confidence = Column(Float, nullable=False, default=0.0)
    school_normalized = Column(String, nullable=False)
    program_normalized = Column(String, nullable=False)
    program_category = Column(String, nullable=True)
    admission_year = Column(Integer, nullable=True)
    decision = Column(String, nullable=True)
    decision_confidence = Column(Float, nullable=False, default=0.0)
    province = Column(String, nullable=True)
    citizenship = Column(String, nullable=True)
    grade_average = Column(Float, nullable=True)
    grade_context = Column(String, nullable=False, default="UNKNOWN_PERCENT")
    grade_confidence = Column(Float, nullable=False, default=0.0)
    curriculum_type = Column(String, nullable=False, default="UNKNOWN")
    course_rigor_score = Column(Float, nullable=False, default=0.0)
    profile_completeness_score = Column(Float, nullable=False, default=0.0)
    created_at = Column(String, nullable=True)
    updated_at = Column(String, nullable=True)


class ApplicantCourse(Base):
    __tablename__ = "applicant_courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey("applicant_profiles.id"), nullable=False)
    course_name = Column(String, nullable=False)
    course_subject = Column(String, nullable=False)
    course_level = Column(String, nullable=False, default="UNKNOWN")
    grade = Column(Float, nullable=True)
    is_required_for_program = Column(Boolean, nullable=False, default=False)
    source_confidence = Column(Float, nullable=False, default=0.0)


class ApplicantActivity(Base):
    __tablename__ = "applicant_activities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey("applicant_profiles.id"), nullable=False)
    category = Column(String, nullable=False)
    activity_type = Column(String, nullable=False)
    raw_text = Column(Text, nullable=True)
    role_level = Column(String, nullable=False, default="UNKNOWN")
    duration_months = Column(Integer, nullable=True)
    achievement_level = Column(String, nullable=False, default="UNKNOWN")
    program_relevance = Column(String, nullable=False, default="UNKNOWN")
    source_confidence = Column(Float, nullable=False, default=0.0)


def get_engine(db_path: str = "database/unipath.db"):
    return create_engine(f"sqlite:///{db_path}", echo=False)


def init_db(db_path: str = "database/unipath.db"):
    """Creates the database and all tables if they don't exist."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine
