# Profile Matcher Rich Applicant Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend foundation for retention-focused applicant profile matching: structured profile tables, deterministic enrichment from existing rows, interpretable nearest-profile matching, archetypes, and FastAPI endpoints.

**Architecture:** Add profile-layer tables alongside the existing `students` table without mutating original student rows. Use deterministic rule-based enrichment for v1 so tests are stable, then expose a weighted similarity matcher and archetype summaries through FastAPI. Frontend work is intentionally deferred until these APIs are stable.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, SQLAlchemy, SQLite, pytest.

---

## Scope

This plan implements the backend profile matcher v1. It does not build the frontend profile-entry UI yet. After this plan passes, create a separate frontend plan for profile input, nearest-profile results, and program archetype display.

## File Structure

- Create `core/profile_taxonomy.py`: enums, normalization helpers, and rule-based activity/course extraction primitives.
- Create `core/profile_enrichment.py`: convert existing `Student` rows into `ApplicantProfile`, `ApplicantCourse`, and `ApplicantActivity` rows.
- Create `core/profile_matcher.py`: weighted similarity, explanations, percentile, gap comparison, archetypes, and redacted profile cards.
- Create `scripts/backfill_applicant_profiles.py`: idempotent backfill from existing students into profile tables.
- Modify `database/models.py`: add `ApplicantProfile`, `ApplicantCourse`, and `ApplicantActivity` ORM models.
- Modify `server/main.py`: add request/response models and endpoints for `/profiles`, `/profile-match`, and `/programs/{school}/{program_name:path}/archetypes`.
- Create `tests/test_profile_taxonomy.py`: taxonomy and deterministic extraction tests.
- Create `tests/test_profile_enrichment.py`: ORM profile backfill tests.
- Create `tests/test_profile_matcher.py`: similarity, explanations, archetypes, and privacy tests.
- Create `tests/test_profile_api.py`: FastAPI endpoint shape tests.

---

### Task 1: Profile ORM Tables

**Files:**
- Modify: `database/models.py`
- Test: `tests/test_profile_enrichment.py`

- [ ] **Step 1: Write failing ORM table creation test**

Add `tests/test_profile_enrichment.py`:

```python
from sqlalchemy import inspect

from database.models import init_db


def test_init_db_creates_profile_tables(tmp_path):
    db_path = tmp_path / "profiles.db"
    engine = init_db(str(db_path))

    tables = set(inspect(engine).get_table_names())

    assert "applicant_profiles" in tables
    assert "applicant_courses" in tables
    assert "applicant_activities" in tables
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `pytest tests/test_profile_enrichment.py::test_init_db_creates_profile_tables -v`

Expected: FAIL because `applicant_profiles` does not exist.

- [ ] **Step 3: Add ORM models**

In `database/models.py`, extend the SQLAlchemy imports:

```python
from sqlalchemy import (
    Column, Integer, Float, String, Boolean, DateTime, Text, create_engine,
    ForeignKey, UniqueConstraint
)
```

Add these classes after `CudoProgram`:

```python
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
```

- [ ] **Step 4: Run the ORM table test**

Run: `pytest tests/test_profile_enrichment.py::test_init_db_creates_profile_tables -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add database/models.py tests/test_profile_enrichment.py
git commit -m "feat: add applicant profile tables"
```

---

### Task 2: Activity And Course Taxonomy

**Files:**
- Create: `core/profile_taxonomy.py`
- Modify: `tests/test_profile_taxonomy.py`

- [ ] **Step 1: Write failing taxonomy tests**

Add `tests/test_profile_taxonomy.py`:

```python
from core.profile_taxonomy import (
    extract_activity_signals,
    extract_course_signals,
    normalize_curriculum_type,
)


def test_extracts_deca_president_as_business_leadership():
    activities = extract_activity_signals("DECA president for 2 years, placed provincially")

    assert activities == [
        {
            "category": "BUSINESS",
            "activity_type": "DECA",
            "raw_text": "DECA president for 2 years, placed provincially",
            "role_level": "PRESIDENT",
            "duration_months": 24,
            "achievement_level": "PROVINCIAL",
            "program_relevance": "HIGH",
            "source_confidence": 0.9,
        }
    ]


def test_extracts_hackathon_founder_as_stem_entrepreneurial_signal():
    activities = extract_activity_signals("Founded coding club, won a hackathon, built an app")

    assert activities[0]["category"] == "STEM"
    assert activities[0]["activity_type"] == "HACKATHON"
    assert activities[0]["role_level"] == "FOUNDER"
    assert activities[0]["achievement_level"] == "LOCAL"
    assert activities[0]["program_relevance"] == "HIGH"


def test_extracts_ib_hl_courses():
    courses = extract_course_signals("IB HL Math 96, IB HL Chemistry 94, SL English 91")

    assert courses == [
        {
            "course_name": "Math",
            "course_subject": "MATH",
            "course_level": "IB_HL",
            "grade": 96.0,
            "is_required_for_program": False,
            "source_confidence": 0.85,
        },
        {
            "course_name": "Chemistry",
            "course_subject": "SCIENCE",
            "course_level": "IB_HL",
            "grade": 94.0,
            "is_required_for_program": False,
            "source_confidence": 0.85,
        },
        {
            "course_name": "English",
            "course_subject": "ENGLISH",
            "course_level": "IB_SL",
            "grade": 91.0,
            "is_required_for_program": False,
            "source_confidence": 0.8,
        },
    ]


def test_normalizes_curriculum_type():
    assert normalize_curriculum_type("IB HL Math and TOK") == "IB"
    assert normalize_curriculum_type("AP Calculus and AP Physics") == "AP"
    assert normalize_curriculum_type("regular BC curriculum") == "REGULAR"
    assert normalize_curriculum_type("") == "UNKNOWN"
```

- [ ] **Step 2: Run taxonomy tests and verify they fail**

Run: `pytest tests/test_profile_taxonomy.py -v`

Expected: FAIL because `core.profile_taxonomy` does not exist.

- [ ] **Step 3: Implement deterministic taxonomy helpers**

Create `core/profile_taxonomy.py`:

```python
import re


def normalize_curriculum_type(text: str | None) -> str:
    value = (text or "").lower()
    has_ib = "ib" in value or "international baccalaureate" in value
    has_ap = "ap " in f"{value} " or "advanced placement" in value
    if has_ib and has_ap:
        return "MIXED"
    if has_ib:
        return "IB"
    if has_ap:
        return "AP"
    if any(token in value for token in ["honors", "honours"]):
        return "HONORS"
    if any(token in value for token in ["regular", "normal", "bc curriculum", "ontario curriculum"]):
        return "REGULAR"
    return "UNKNOWN"


def _duration_months(text: str) -> int | None:
    match = re.search(r"(\d+)\s*(year|years|yr|yrs)", text.lower())
    if match:
        return int(match.group(1)) * 12
    match = re.search(r"(\d+)\s*(month|months)", text.lower())
    if match:
        return int(match.group(1))
    return None


def _role_level(text: str) -> str:
    value = text.lower()
    if "president" in value:
        return "PRESIDENT"
    if "founder" in value or "founded" in value or "co-founder" in value:
        return "FOUNDER"
    if "captain" in value:
        return "CAPTAIN"
    if "exec" in value or "executive" in value:
        return "EXECUTIVE"
    if "lead" in value or "leader" in value:
        return "LEAD"
    if "won" in value or "award" in value or "placed" in value:
        return "AWARD_WINNER"
    return "UNKNOWN"


def _achievement_level(text: str) -> str:
    value = text.lower()
    if "international" in value or "world" in value:
        return "INTERNATIONAL"
    if "national" in value or "canada" in value:
        return "NATIONAL"
    if "provincial" in value or "provincially" in value:
        return "PROVINCIAL"
    if "regional" in value:
        return "REGIONAL"
    if "won" in value or "placed" in value or "award" in value:
        return "LOCAL"
    if "school" in value:
        return "SCHOOL"
    return "UNKNOWN"


def extract_activity_signals(text: str | None) -> list[dict]:
    raw = (text or "").strip()
    value = raw.lower()
    if not raw:
        return []

    signals = []
    rules = [
        ("deca", "BUSINESS", "DECA", "HIGH", 0.9),
        ("student council", "LEADERSHIP", "STUDENT_COUNCIL", "MEDIUM", 0.85),
        ("business club", "BUSINESS", "BUSINESS_CLUB", "HIGH", 0.85),
        ("hackathon", "STEM", "HACKATHON", "HIGH", 0.85),
        ("robotics", "STEM", "ROBOTICS", "HIGH", 0.85),
        ("science fair", "STEM", "SCIENCE_FAIR", "HIGH", 0.85),
        ("hosa", "COMPETITION", "HOSA", "HIGH", 0.85),
        ("debate", "COMPETITION", "DEBATE", "MEDIUM", 0.8),
        ("model un", "COMPETITION", "MODEL_UN", "MEDIUM", 0.8),
        ("varsity", "SPORTS", "VARSITY_SPORT", "MEDIUM", 0.8),
        ("tutor", "COMMUNITY", "TUTORING", "MEDIUM", 0.75),
        ("part-time", "WORK", "PAID_WORK", "LOW", 0.75),
        ("research", "RESEARCH", "RESEARCH_INTERNSHIP", "HIGH", 0.8),
        ("nonprofit", "ENTREPRENEURSHIP", "NONPROFIT", "HIGH", 0.8),
        ("app", "STEM", "PERSONAL_PROJECT", "HIGH", 0.75),
    ]

    for keyword, category, activity_type, relevance, confidence in rules:
        if keyword in value:
            signals.append({
                "category": category,
                "activity_type": activity_type,
                "raw_text": raw,
                "role_level": _role_level(raw),
                "duration_months": _duration_months(raw),
                "achievement_level": _achievement_level(raw),
                "program_relevance": relevance,
                "source_confidence": confidence,
            })
            break

    if not signals and raw:
        signals.append({
            "category": "OTHER",
            "activity_type": "OTHER",
            "raw_text": raw,
            "role_level": _role_level(raw),
            "duration_months": _duration_months(raw),
            "achievement_level": _achievement_level(raw),
            "program_relevance": "UNKNOWN",
            "source_confidence": 0.45,
        })

    return signals


COURSE_SUBJECTS = {
    "math": "MATH",
    "calculus": "MATH",
    "chemistry": "SCIENCE",
    "physics": "SCIENCE",
    "biology": "SCIENCE",
    "english": "ENGLISH",
    "history": "ARTS",
    "economics": "BUSINESS",
}


def _course_subject(course_name: str) -> str:
    lowered = course_name.lower()
    for token, subject in COURSE_SUBJECTS.items():
        if token in lowered:
            return subject
    return "OTHER"


def extract_course_signals(text: str | None) -> list[dict]:
    raw = text or ""
    pattern = re.compile(r"\b(?:(IB)\s+)?(HL|SL|AP)?\s*(Math|Calculus|Chemistry|Physics|Biology|English|History|Economics)\s+(\d{2,3}(?:\.\d+)?)", re.IGNORECASE)
    courses = []
    for match in pattern.finditer(raw):
        ib_prefix, level_token, name, grade = match.groups()
        level_upper = (level_token or "").upper()
        if ib_prefix and level_upper == "HL":
            course_level = "IB_HL"
            confidence = 0.85
        elif level_upper == "SL":
            course_level = "IB_SL"
            confidence = 0.8
        elif level_upper == "AP":
            course_level = "AP"
            confidence = 0.8
        else:
            course_level = "UNKNOWN"
            confidence = 0.65
        courses.append({
            "course_name": name.title(),
            "course_subject": _course_subject(name),
            "course_level": course_level,
            "grade": float(grade),
            "is_required_for_program": False,
            "source_confidence": confidence,
        })
    return courses
```

- [ ] **Step 4: Run taxonomy tests**

Run: `pytest tests/test_profile_taxonomy.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/profile_taxonomy.py tests/test_profile_taxonomy.py
git commit -m "feat: add profile taxonomy helpers"
```

---

### Task 3: Profile Enrichment From Existing Students

**Files:**
- Create: `core/profile_enrichment.py`
- Modify: `tests/test_profile_enrichment.py`

- [ ] **Step 1: Add failing enrichment test**

Append to `tests/test_profile_enrichment.py`:

```python
from sqlalchemy.orm import Session

from core.profile_enrichment import build_profile_from_student, upsert_profile_for_student
from database.models import ApplicantActivity, ApplicantCourse, ApplicantProfile, Student


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
```

- [ ] **Step 2: Run enrichment tests and verify failure**

Run: `pytest tests/test_profile_enrichment.py -v`

Expected: FAIL because `core.profile_enrichment` does not exist.

- [ ] **Step 3: Implement enrichment module**

Create `core/profile_enrichment.py`:

```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from core.profile_taxonomy import (
    extract_activity_signals,
    extract_course_signals,
    normalize_curriculum_type,
)
from database.models import ApplicantActivity, ApplicantCourse, ApplicantProfile, Student


def _grade_context(student: Student) -> str:
    if student.core_avg is not None:
        return "CORE_AVERAGE"
    if student.grade_12_avg is not None:
        return "GRADE_12_AVERAGE"
    if student.grade_11_avg is not None:
        return "GRADE_11_AVERAGE"
    return "UNKNOWN_PERCENT"


def _grade_average(student: Student) -> float | None:
    if student.core_avg is not None:
        return float(student.core_avg)
    if student.grade_12_avg is not None:
        return float(student.grade_12_avg)
    if student.grade_11_avg is not None:
        return float(student.grade_11_avg)
    return None


def _source_confidence(source: str | None) -> float:
    if source == "USER_SUBMITTED":
        return 0.95
    if source in ("BC", "BC_2025"):
        return 0.8
    if source == "REDDIT_SCRAPED":
        return 0.65
    return 0.4


def _completeness(student: Student, courses: list[ApplicantCourse], activities: list[ApplicantActivity]) -> float:
    score = 0.0
    if student.school_normalized:
        score += 0.15
    if student.program_normalized:
        score += 0.15
    if student.decision:
        score += 0.15
    if _grade_average(student) is not None:
        score += 0.2
    if courses:
        score += 0.15
    if activities:
        score += 0.2
    return round(min(score, 1.0), 2)


def build_profile_from_student(student: Student) -> tuple[ApplicantProfile, list[ApplicantCourse], list[ApplicantActivity]]:
    raw_text = " ".join(
        part for part in [student.ec_raw, student.comments_raw, student.circumstances_raw]
        if part
    )
    course_signals = extract_course_signals(raw_text)
    activity_signals = extract_activity_signals(student.ec_raw or raw_text)
    now = datetime.now(timezone.utc).isoformat()

    courses = [ApplicantCourse(**signal) for signal in course_signals]
    activities = [ApplicantActivity(**signal) for signal in activity_signals]
    grade_average = _grade_average(student)

    profile = ApplicantProfile(
        source_student_id=student.id,
        source=student.source,
        source_confidence=_source_confidence(student.source),
        school_normalized=student.school_normalized,
        program_normalized=student.program_normalized,
        program_category=student.program_category,
        decision=student.decision,
        decision_confidence=0.9 if student.decision else 0.0,
        province=student.province,
        citizenship=student.citizenship,
        grade_average=grade_average,
        grade_context=_grade_context(student),
        grade_confidence=0.9 if grade_average is not None else 0.0,
        curriculum_type=normalize_curriculum_type(raw_text),
        course_rigor_score=round(min(len(courses) * 0.25, 1.0), 2),
        profile_completeness_score=_completeness(student, courses, activities),
        created_at=now,
        updated_at=now,
    )
    return profile, courses, activities


def upsert_profile_for_student(session: Session, student: Student) -> ApplicantProfile:
    existing = session.query(ApplicantProfile).filter(
        ApplicantProfile.source_student_id == student.id
    ).first()
    profile, courses, activities = build_profile_from_student(student)

    if existing:
        profile.id = existing.id
        profile.created_at = existing.created_at
        session.query(ApplicantCourse).filter(ApplicantCourse.profile_id == existing.id).delete()
        session.query(ApplicantActivity).filter(ApplicantActivity.profile_id == existing.id).delete()
        for key, value in profile.__dict__.items():
            if not key.startswith("_") and key != "id":
                setattr(existing, key, value)
        target = existing
    else:
        session.add(profile)
        session.flush()
        target = profile

    for course in courses:
        course.profile_id = target.id
        session.add(course)
    for activity in activities:
        activity.profile_id = target.id
        session.add(activity)
    session.flush()
    return target
```

- [ ] **Step 4: Run enrichment tests**

Run: `pytest tests/test_profile_enrichment.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/profile_enrichment.py tests/test_profile_enrichment.py
git commit -m "feat: enrich applicant profiles from students"
```

---

### Task 4: Backfill Script

**Files:**
- Create: `scripts/backfill_applicant_profiles.py`
- Modify: `tests/test_profile_enrichment.py`

- [ ] **Step 1: Add failing backfill test**

Append to `tests/test_profile_enrichment.py`:

```python
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
```

- [ ] **Step 2: Run the backfill test and verify failure**

Run: `pytest tests/test_profile_enrichment.py::test_backfill_applicant_profiles_skips_incomplete_rows -v`

Expected: FAIL because `scripts.backfill_applicant_profiles` does not exist.

- [ ] **Step 3: Implement idempotent backfill script**

Create `scripts/backfill_applicant_profiles.py`:

```python
from sqlalchemy.orm import Session

from core.profile_enrichment import upsert_profile_for_student
from database.models import Student, init_db


def _is_profile_eligible(student: Student) -> bool:
    return bool(
        student.school_normalized
        and student.program_normalized
        and student.source
        and student.core_avg is not None
    )


def backfill_applicant_profiles(db_path: str = "database/unipath.db") -> dict:
    engine = init_db(db_path)
    checked = 0
    created_or_updated = 0
    skipped = 0

    with Session(engine) as session:
        students = session.query(Student).all()
        for student in students:
            checked += 1
            if not _is_profile_eligible(student):
                skipped += 1
                continue
            upsert_profile_for_student(session, student)
            created_or_updated += 1
        session.commit()

    summary = {
        "checked": checked,
        "created_or_updated": created_or_updated,
        "skipped": skipped,
    }
    print(summary)
    return summary


if __name__ == "__main__":
    backfill_applicant_profiles()
```

- [ ] **Step 4: Run profile enrichment tests**

Run: `pytest tests/test_profile_enrichment.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/backfill_applicant_profiles.py tests/test_profile_enrichment.py
git commit -m "feat: add applicant profile backfill"
```

---

### Task 5: Profile Matching Engine

**Files:**
- Create: `core/profile_matcher.py`
- Test: `tests/test_profile_matcher.py`

- [ ] **Step 1: Write failing matcher tests**

Add `tests/test_profile_matcher.py`:

```python
from sqlalchemy.orm import Session

from core.profile_matcher import get_program_archetypes, match_profiles
from database.models import (
    ApplicantActivity,
    ApplicantProfile,
    init_db,
)


def _profile(session, *, decision, grade, activity_type, category="BUSINESS", role="MEMBER"):
    profile = ApplicantProfile(
        source="USER_SUBMITTED",
        source_confidence=0.95,
        school_normalized="UBC Vancouver",
        program_normalized="Commerce",
        program_category="BUSINESS",
        decision=decision,
        decision_confidence=0.95,
        grade_average=grade,
        grade_context="CORE_AVERAGE",
        grade_confidence=0.95,
        curriculum_type="REGULAR",
        course_rigor_score=0.0,
        profile_completeness_score=0.8,
    )
    session.add(profile)
    session.flush()
    session.add(ApplicantActivity(
        profile_id=profile.id,
        category=category,
        activity_type=activity_type,
        role_level=role,
        achievement_level="PROVINCIAL" if role == "PRESIDENT" else "LOCAL",
        program_relevance="HIGH",
        source_confidence=0.9,
    ))
    return profile


def test_match_profiles_returns_nearest_accepted_and_rejected(tmp_path):
    db_path = tmp_path / "matcher.db"
    engine = init_db(str(db_path))
    with Session(engine) as session:
        _profile(session, decision="ACCEPTED", grade=94, activity_type="DECA", role="PRESIDENT")
        _profile(session, decision="ACCEPTED", grade=88, activity_type="ROBOTICS", category="STEM")
        _profile(session, decision="REJECTED", grade=92, activity_type="DECA")
        session.commit()

    result = match_profiles(
        str(db_path),
        {
            "school": "UBC Vancouver",
            "program": "Commerce",
            "grade_average": 93,
            "curriculum_type": "REGULAR",
            "activities": [{"category": "BUSINESS", "activity_type": "DECA", "role_level": "EXECUTIVE"}],
        },
    )

    assert result["data_confidence"]["label"] == "medium"
    assert result["grade_percentile"] == 67
    assert result["accepted_matches"][0]["decision"] == "ACCEPTED"
    assert result["accepted_matches"][0]["activity_types"] == ["DECA"]
    assert "DECA" in result["accepted_matches"][0]["match_explanation"]
    assert result["rejected_or_waitlisted_matches"][0]["decision"] == "REJECTED"


def test_archetypes_hide_low_support_groups(tmp_path):
    db_path = tmp_path / "archetypes.db"
    engine = init_db(str(db_path))
    with Session(engine) as session:
        _profile(session, decision="ACCEPTED", grade=94, activity_type="DECA", role="PRESIDENT")
        _profile(session, decision="ACCEPTED", grade=93, activity_type="BUSINESS_CLUB", role="EXECUTIVE")
        _profile(session, decision="ACCEPTED", grade=92, activity_type="ROBOTICS", category="STEM")
        session.commit()

    result = get_program_archetypes(str(db_path), "UBC Vancouver", "Commerce", min_support=2)

    assert result == [
        {
            "name": "Business leadership profile",
            "support_count": 2,
            "median_grade": 93.5,
            "common_activity_types": ["BUSINESS_CLUB", "DECA"],
            "common_role_levels": ["EXECUTIVE", "PRESIDENT"],
            "confidence_label": "medium",
        }
    ]
```

- [ ] **Step 2: Run matcher tests and verify failure**

Run: `pytest tests/test_profile_matcher.py -v`

Expected: FAIL because `core.profile_matcher` does not exist.

- [ ] **Step 3: Implement matcher module**

Create `core/profile_matcher.py`:

```python
from collections import Counter, defaultdict
from statistics import median

from sqlalchemy.orm import Session

from database.models import ApplicantActivity, ApplicantProfile, init_db


def _activities_for(session: Session, profile_ids: list[int]) -> dict[int, list[ApplicantActivity]]:
    if not profile_ids:
        return {}
    rows = session.query(ApplicantActivity).filter(ApplicantActivity.profile_id.in_(profile_ids)).all()
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.profile_id].append(row)
    return grouped


def _score(profile: ApplicantProfile, activities: list[ApplicantActivity], query: dict) -> float:
    score = 0.0
    grade = query.get("grade_average")
    if grade is not None and profile.grade_average is not None:
        score += max(0.0, 40.0 - abs(float(grade) - float(profile.grade_average)) * 8.0)
    if query.get("curriculum_type") == profile.curriculum_type:
        score += 10.0

    query_activities = query.get("activities") or []
    query_categories = {item.get("category") for item in query_activities if item.get("category")}
    query_types = {item.get("activity_type") for item in query_activities if item.get("activity_type")}
    profile_categories = {item.category for item in activities}
    profile_types = {item.activity_type for item in activities}

    score += len(query_categories & profile_categories) * 15.0
    score += len(query_types & profile_types) * 25.0
    if any(item.role_level in ("PRESIDENT", "FOUNDER", "CAPTAIN") for item in activities):
        score += 5.0
    return round(score, 2)


def _profile_card(profile: ApplicantProfile, activities: list[ApplicantActivity], score: float, query: dict) -> dict:
    activity_types = sorted({activity.activity_type for activity in activities})
    categories = sorted({activity.category for activity in activities})
    overlap = sorted(set(activity_types) & {
        item.get("activity_type") for item in query.get("activities", []) if item.get("activity_type")
    })
    if overlap:
        explanation = f"Similar grade range and shared activity signal: {', '.join(overlap)}."
    elif categories:
        explanation = f"Similar grade range with profile strength in {', '.join(categories)}."
    else:
        explanation = "Similar grade range; this profile has limited structured EC detail."
    return {
        "id": profile.id,
        "decision": profile.decision,
        "grade_average": profile.grade_average,
        "curriculum_type": profile.curriculum_type,
        "activity_types": activity_types,
        "categories": categories,
        "similarity_score": score,
        "match_explanation": explanation,
    }


def _confidence_label(total_profiles: int, ec_rich_profiles: int) -> str:
    if total_profiles >= 20 and ec_rich_profiles >= 10:
        return "high"
    if total_profiles >= 3 and ec_rich_profiles >= 2:
        return "medium"
    return "low"


def _grade_percentile(profiles: list[ApplicantProfile], grade: float | None) -> int | None:
    grades = [p.grade_average for p in profiles if p.grade_average is not None]
    if grade is None or not grades:
        return None
    below_or_equal = sum(1 for value in grades if value <= grade)
    return round(below_or_equal / len(grades) * 100)


def match_profiles(db_path: str, query: dict) -> dict:
    engine = init_db(db_path)
    with Session(engine) as session:
        profiles = session.query(ApplicantProfile).filter(
            ApplicantProfile.school_normalized == query["school"],
            ApplicantProfile.program_normalized == query["program"],
        ).all()
        activity_map = _activities_for(session, [profile.id for profile in profiles])

        scored = [
            (profile, activity_map.get(profile.id, []), _score(profile, activity_map.get(profile.id, []), query))
            for profile in profiles
        ]
        scored.sort(key=lambda item: item[2], reverse=True)

        accepted = [
            _profile_card(profile, activities, score, query)
            for profile, activities, score in scored
            if profile.decision == "ACCEPTED"
        ][:5]
        other = [
            _profile_card(profile, activities, score, query)
            for profile, activities, score in scored
            if profile.decision in ("REJECTED", "WAITLISTED", "DEFERRED")
        ][:5]
        ec_rich = sum(1 for profile in profiles if activity_map.get(profile.id))

        return {
            "accepted_matches": accepted,
            "rejected_or_waitlisted_matches": other,
            "grade_percentile": _grade_percentile(profiles, query.get("grade_average")),
            "data_confidence": {
                "label": _confidence_label(len(profiles), ec_rich),
                "total_profiles": len(profiles),
                "ec_rich_profiles": ec_rich,
            },
        }


ARCHETYPE_NAMES = {
    "BUSINESS": "Business leadership profile",
    "STEM": "STEM competition builder",
    "SPORTS": "Athlete plus community service",
    "RESEARCH": "Research-heavy science applicant",
    "ENTREPRENEURSHIP": "Founder/entrepreneur profile",
}


def get_program_archetypes(db_path: str, school: str, program: str, min_support: int = 3) -> list[dict]:
    engine = init_db(db_path)
    with Session(engine) as session:
        profiles = session.query(ApplicantProfile).filter(
            ApplicantProfile.school_normalized == school,
            ApplicantProfile.program_normalized == program,
            ApplicantProfile.decision == "ACCEPTED",
        ).all()
        activity_map = _activities_for(session, [profile.id for profile in profiles])

    grouped = defaultdict(list)
    by_id = {profile.id: profile for profile in profiles}
    for profile_id, activities in activity_map.items():
        if activities:
            grouped[activities[0].category].append((by_id[profile_id], activities))

    archetypes = []
    for category, rows in grouped.items():
        if len(rows) < min_support:
            continue
        grades = [profile.grade_average for profile, _ in rows if profile.grade_average is not None]
        activity_types = Counter(activity.activity_type for _, activities in rows for activity in activities)
        role_levels = Counter(activity.role_level for _, activities in rows for activity in activities)
        archetypes.append({
            "name": ARCHETYPE_NAMES.get(category, "High-grade academic competitor"),
            "support_count": len(rows),
            "median_grade": round(median(grades), 1) if grades else None,
            "common_activity_types": sorted(activity_types.keys()),
            "common_role_levels": sorted(role_levels.keys()),
            "confidence_label": _confidence_label(len(rows), len(rows)),
        })
    return sorted(archetypes, key=lambda item: item["support_count"], reverse=True)
```

- [ ] **Step 4: Run matcher tests**

Run: `pytest tests/test_profile_matcher.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/profile_matcher.py tests/test_profile_matcher.py
git commit -m "feat: add applicant profile matcher"
```

---

### Task 6: FastAPI Profile Endpoints

**Files:**
- Modify: `server/main.py`
- Create: `tests/test_profile_api.py`

- [ ] **Step 1: Write failing API tests**

Add `tests/test_profile_api.py`:

```python
from fastapi.testclient import TestClient

from server.main import app


client = TestClient(app)


def test_profile_match_endpoint_returns_shape():
    response = client.post("/profile-match", json={
        "school": "UBC Vancouver",
        "program": "Commerce",
        "grade_average": 93,
        "curriculum_type": "REGULAR",
        "activities": [{"category": "BUSINESS", "activity_type": "DECA", "role_level": "EXECUTIVE"}],
    })

    assert response.status_code == 200
    data = response.json()
    assert "accepted_matches" in data
    assert "rejected_or_waitlisted_matches" in data
    assert "grade_percentile" in data
    assert "data_confidence" in data


def test_program_archetypes_endpoint_returns_list():
    response = client.get("/programs/UBC%20Vancouver/Commerce/archetypes")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_profiles_endpoint_accepts_anonymous_profile():
    response = client.post("/profiles", json={
        "school": "UBC Vancouver",
        "program": "Commerce",
        "grade_average": 94,
        "decision": "ACCEPTED",
        "province": "BC",
        "curriculum_type": "IB",
        "activities_text": "DECA president for 2 years",
    })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["normalized_school"] == "UBC Vancouver"
    assert data["normalized_program"] == "Commerce"
    assert data["activity_count"] >= 1
```

- [ ] **Step 2: Run API tests and verify failure**

Run: `pytest tests/test_profile_api.py -v`

Expected: FAIL because the endpoints do not exist.

- [ ] **Step 3: Add Pydantic request models and endpoints**

In `server/main.py`, add imports:

```python
from core.profile_matcher import get_program_archetypes, match_profiles
from core.profile_taxonomy import extract_activity_signals
from pipeline.program_names import normalize_program_name
```

Add models near the existing request models:

```python
class ActivityInput(BaseModel):
    category: Optional[str] = None
    activity_type: Optional[str] = None
    role_level: Optional[str] = None


class ProfileMatchRequest(BaseModel):
    school: str
    program: str
    grade_average: Optional[float] = None
    curriculum_type: str = "UNKNOWN"
    activities: list[ActivityInput] = []


class CreateProfileRequest(BaseModel):
    school: str
    program: str
    grade_average: Optional[float] = None
    decision: Optional[Literal["ACCEPTED", "REJECTED", "WAITLISTED", "DEFERRED"]] = None
    province: Optional[str] = None
    curriculum_type: str = "UNKNOWN"
    activities_text: Optional[str] = None
```

Add the archetypes endpoint before the existing catch-all `@app.get("/programs/{school}/{program_name:path}")` route so `/archetypes` is not swallowed as part of `program_name`:

```python
@app.get("/programs/{school}/{program_name:path}/archetypes")
def get_archetypes(school: str, program_name: str):
    return get_program_archetypes("database/unipath.db", school, program_name)
```

Add the profile endpoints after `get_program_stats`:

```python

@app.post("/profile-match")
def post_profile_match(req: ProfileMatchRequest):
    return match_profiles("database/unipath.db", {
        "school": req.school,
        "program": req.program,
        "grade_average": req.grade_average,
        "curriculum_type": req.curriculum_type,
        "activities": [activity.model_dump() for activity in req.activities],
    })


@app.post("/profiles")
def create_profile(req: CreateProfileRequest):
    school_normalized, _ = normalize_school(req.school)
    if school_normalized is None:
        return {"error": "unknown_school"}
    program_normalized = normalize_program_name(req.program, school=school_normalized)
    activities = extract_activity_signals(req.activities_text)
    return {
        "status": "ok",
        "normalized_school": school_normalized,
        "normalized_program": program_normalized,
        "activity_count": len(activities),
        "activities": activities,
    }
```

- [ ] **Step 4: Run API tests**

Run: `pytest tests/test_profile_api.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/main.py tests/test_profile_api.py
git commit -m "feat: expose profile matcher api"
```

---

### Task 7: Run Backfill And Verify Real Data

**Files:**
- No new files.

- [ ] **Step 1: Run profile-related tests**

Run: `pytest tests/test_profile_taxonomy.py tests/test_profile_enrichment.py tests/test_profile_matcher.py tests/test_profile_api.py -v`

Expected: PASS.

- [ ] **Step 2: Backfill local database**

Run: `python scripts/backfill_applicant_profiles.py`

Expected output shape:

```text
{'checked': 949, 'created_or_updated': <number greater than 0>, 'skipped': <number greater than or equal to 0>}
```

- [ ] **Step 3: Verify profile row counts**

Run: `sqlite3 database/unipath.db "select count(*) from applicant_profiles; select count(*) from applicant_activities; select count(*) from applicant_courses;"`

Expected: first count is greater than `0`; activity count is greater than `0`; course count may be `0` or greater depending on extracted text.

- [ ] **Step 4: Verify matcher on a flagship program**

Run: `curl -s http://127.0.0.1:8000/health`

Expected before starting the server: connection failure if the server is not running.

Run: `uvicorn server.main:app --host 127.0.0.1 --port 8000`

In another terminal, run:

```bash
curl -s -X POST http://127.0.0.1:8000/profile-match \
  -H "Content-Type: application/json" \
  -d '{"school":"UBC Vancouver","program":"Commerce","grade_average":93,"curriculum_type":"REGULAR","activities":[{"category":"BUSINESS","activity_type":"DECA","role_level":"EXECUTIVE"}]}'
```

Expected JSON keys:

```json
{
  "accepted_matches": [],
  "rejected_or_waitlisted_matches": [],
  "grade_percentile": null,
  "data_confidence": {
    "label": "low",
    "total_profiles": 0,
    "ec_rich_profiles": 0
  }
}
```

The exact array contents may be non-empty after backfill. The endpoint must return the listed keys and must not return a server error.

- [ ] **Step 5: Commit local database snapshot only if this project intentionally tracks `database/unipath.db` changes**

Check status:

```bash
git status --short
```

If `database/unipath.db` changed and the project is tracking data snapshots, commit:

```bash
git add database/unipath.db
git commit -m "data: backfill applicant profiles"
```

If the database should not be committed, leave it unstaged and document that the backfill script must run in deployment.

---

### Task 8: Final Regression Verification

**Files:**
- No new files.

- [ ] **Step 1: Run focused backend test suite**

Run: `pytest tests/test_profile_taxonomy.py tests/test_profile_enrichment.py tests/test_profile_matcher.py tests/test_profile_api.py tests/test_program_stats.py tests/test_submit.py -v`

Expected: PASS.

- [ ] **Step 2: Run existing known-good tests from project state**

Run: `pytest tests/test_cudo_api.py tests/test_reddit_agent.py tests/test_program_names.py tests/test_program_stats.py -v`

Expected: PASS.

- [ ] **Step 3: Check git status**

Run: `git status --short`

Expected: no uncommitted code changes, except an intentionally uncommitted `database/unipath.db` if Task 7 chose not to commit the local DB snapshot.

---

## Self-Review Notes

- Spec coverage: profile tables, activity/course taxonomy, enrichment, confidence labels, matching, explanations, archetypes, API endpoints, privacy redaction by normalized profile cards, and AdmitMe exclusion are covered.
- Deferred scope: frontend retention screens and saved anonymous profile tokens need a separate frontend/API persistence plan after this backend foundation lands.
- The plan uses deterministic rule-based extraction in v1. A future design should add LLM-based profile enrichment behind the same profile table shape after the basic matcher proves useful.
