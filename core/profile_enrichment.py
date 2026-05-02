from datetime import datetime, timezone

from sqlalchemy.orm import Session

from core.profile_taxonomy import (
    extract_activity_signals,
    extract_course_signals,
    normalize_curriculum_type,
)
from database.models import ApplicantActivity, ApplicantCourse, ApplicantProfile, Student


class ProfileEnrichmentError(ValueError):
    pass


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


def is_profile_eligible(student: Student) -> bool:
    return bool(
        student.source
        and student.school_normalized
        and student.program_normalized
        and _grade_average(student) is not None
    )


def _dedupe_course_signals(course_signals: list[dict]) -> list[dict]:
    deduped = []
    seen = set()
    for signal in course_signals:
        key = (signal["course_name"], signal["course_level"], signal["grade"])
        if key in seen:
            continue
        deduped.append(signal)
        seen.add(key)
    return deduped


def _completeness(
    student: Student,
    courses: list[ApplicantCourse],
    activities: list[ApplicantActivity],
) -> float:
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


def build_profile_from_student(
    student: Student,
) -> tuple[ApplicantProfile, list[ApplicantCourse], list[ApplicantActivity]]:
    if not is_profile_eligible(student):
        raise ProfileEnrichmentError(
            "Student must include source, school, program, and grade average"
        )

    raw_text = " ".join(
        part
        for part in [student.ec_raw, student.comments_raw, student.circumstances_raw]
        if part
    )
    course_signals = _dedupe_course_signals(extract_course_signals(raw_text))
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
    existing = (
        session.query(ApplicantProfile)
        .filter(ApplicantProfile.source_student_id == student.id)
        .first()
    )
    profile, courses, activities = build_profile_from_student(student)

    if existing:
        profile.id = existing.id
        profile.created_at = existing.created_at
        session.query(ApplicantCourse).filter(
            ApplicantCourse.profile_id == existing.id
        ).delete()
        session.query(ApplicantActivity).filter(
            ApplicantActivity.profile_id == existing.id
        ).delete()
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
