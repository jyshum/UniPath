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
