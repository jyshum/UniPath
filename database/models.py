# database/models.py

from sqlalchemy import (
    Column, Integer, Float, String, Boolean, DateTime, Text, create_engine
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


def get_engine(db_path: str = "database/unipath.db"):
    return create_engine(f"sqlite:///{db_path}", echo=False)


def init_db(db_path: str = "database/unipath.db"):
    """Creates the database and all tables if they don't exist."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine