from collections import defaultdict
from statistics import median

from sqlalchemy.orm import Session

from database.models import ApplicantActivity, ApplicantProfile, init_db


_LEADERSHIP_ROLES = {
    "PRESIDENT",
    "FOUNDER",
    "CAPTAIN",
    "EXECUTIVE",
    "LEAD",
    "AWARD_WINNER",
}


def _confidence_label(support_count: int) -> str:
    if support_count >= 10:
        return "high"
    if support_count >= 2:
        return "medium"
    return "low"


def _program_profiles(session: Session, school: str, program: str) -> list[ApplicantProfile]:
    return (
        session.query(ApplicantProfile)
        .filter(
            ApplicantProfile.school_normalized == school,
            ApplicantProfile.program_normalized == program,
        )
        .all()
    )


def _activities_by_profile(
    session: Session, profile_ids: list[int]
) -> dict[int, list[ApplicantActivity]]:
    if not profile_ids:
        return {}
    rows = (
        session.query(ApplicantActivity)
        .filter(ApplicantActivity.profile_id.in_(profile_ids))
        .all()
    )
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.profile_id].append(row)
    return grouped


def _grade_percentile(profiles: list[ApplicantProfile], grade_average: float | None) -> int | None:
    grades = [profile.grade_average for profile in profiles if profile.grade_average is not None]
    if grade_average is None or not grades:
        return None
    at_or_below = sum(1 for grade in grades if grade <= grade_average)
    return round((at_or_below / len(grades)) * 100)


def _query_activity_sets(query: dict) -> tuple[set[str], set[str], set[str]]:
    activities = query.get("activities") or []
    categories = {activity.get("category") for activity in activities if activity.get("category")}
    types = {activity.get("activity_type") for activity in activities if activity.get("activity_type")}
    roles = {activity.get("role_level") for activity in activities if activity.get("role_level")}
    return categories, types, roles


def _match_score(
    profile: ApplicantProfile,
    activities: list[ApplicantActivity],
    query: dict,
) -> float:
    score = 0.0
    query_grade = query.get("grade_average")
    if query_grade is not None and profile.grade_average is not None:
        score += abs(float(query_grade) - float(profile.grade_average))
    else:
        score += 10.0

    if query.get("curriculum_type") and profile.curriculum_type != query.get("curriculum_type"):
        score += 1.5

    query_categories, query_types, query_roles = _query_activity_sets(query)
    activity_categories = {activity.category for activity in activities}
    activity_types = {activity.activity_type for activity in activities}
    activity_roles = {activity.role_level for activity in activities}

    if query_types:
        score -= 4.0 * len(query_types & activity_types)
    if query_categories:
        score -= 2.0 * len(query_categories & activity_categories)
    if query_roles:
        score -= 1.0 * len(query_roles & activity_roles)

    return score


def _profile_card(
    profile: ApplicantProfile,
    activities: list[ApplicantActivity],
    query: dict,
) -> dict:
    activity_types = sorted({activity.activity_type for activity in activities})
    role_levels = sorted({activity.role_level for activity in activities})
    matching_types = sorted(_query_activity_sets(query)[1] & set(activity_types))

    if matching_types:
        explanation = f"Similar activity profile includes {', '.join(matching_types)}."
    elif activity_types:
        explanation = f"Closest grade match with activities including {', '.join(activity_types[:3])}."
    else:
        explanation = "Closest grade match with no structured activities."

    return {
        "id": profile.id,
        "decision": profile.decision,
        "grade_average": profile.grade_average,
        "curriculum_type": profile.curriculum_type,
        "activity_types": activity_types,
        "role_levels": role_levels,
        "match_explanation": explanation,
        "profile_completeness_score": profile.profile_completeness_score,
    }


def match_profiles(db_path: str, query: dict) -> dict:
    engine = init_db(db_path)
    school = query.get("school")
    program = query.get("program")

    with Session(engine) as session:
        profiles = _program_profiles(session, school, program)
        activities = _activities_by_profile(session, [profile.id for profile in profiles])

    ranked = sorted(
        profiles,
        key=lambda profile: (
            _match_score(profile, activities.get(profile.id, []), query),
            profile.id,
        ),
    )
    accepted = [
        _profile_card(profile, activities.get(profile.id, []), query)
        for profile in ranked
        if profile.decision == "ACCEPTED"
    ]
    rejected_or_waitlisted = [
        _profile_card(profile, activities.get(profile.id, []), query)
        for profile in ranked
        if profile.decision in {"REJECTED", "WAITLISTED"}
    ]
    ec_rich_profiles = sum(
        1 for profile in profiles if activities.get(profile.id)
    )

    return {
        "school": school,
        "program": program,
        "data_confidence": {
            "label": _confidence_label(len(profiles)),
            "total_profiles": len(profiles),
            "ec_rich_profiles": ec_rich_profiles,
        },
        "grade_percentile": _grade_percentile(profiles, query.get("grade_average")),
        "accepted_matches": accepted,
        "rejected_or_waitlisted_matches": rejected_or_waitlisted,
    }


def _archetype_name(category: str) -> str:
    normalized = category.replace("_", " ").title()
    if category == "BUSINESS":
        return "Business leadership profile"
    return f"{normalized} profile"


def get_program_archetypes(
    db_path: str,
    school: str,
    program: str,
    min_support: int = 3,
) -> list[dict]:
    engine = init_db(db_path)
    with Session(engine) as session:
        accepted_profiles = (
            session.query(ApplicantProfile)
            .filter(
                ApplicantProfile.school_normalized == school,
                ApplicantProfile.program_normalized == program,
                ApplicantProfile.decision == "ACCEPTED",
            )
            .all()
        )
        activities = _activities_by_profile(
            session, [profile.id for profile in accepted_profiles]
        )

    profiles_by_id = {profile.id: profile for profile in accepted_profiles}
    grouped_profile_ids = defaultdict(set)
    for profile_id, profile_activities in activities.items():
        for activity in profile_activities:
            grouped_profile_ids[activity.category].add(profile_id)

    archetypes = []
    for category, profile_ids in grouped_profile_ids.items():
        if len(profile_ids) < min_support:
            continue
        profile_activities = [
            activity
            for profile_id in profile_ids
            for activity in activities.get(profile_id, [])
            if activity.category == category
        ]
        roles = [activity.role_level for activity in profile_activities]
        name = _archetype_name(category)
        if any(role in _LEADERSHIP_ROLES for role in roles) and category != "BUSINESS":
            name = f"{name} leadership profile"

        grades = [
            profiles_by_id[profile_id].grade_average
            for profile_id in profile_ids
            if profiles_by_id[profile_id].grade_average is not None
        ]
        archetypes.append(
            {
                "name": name,
                "support_count": len(profile_ids),
                "median_grade": median(grades) if grades else None,
                "common_activity_types": sorted(
                    {activity.activity_type for activity in profile_activities}
                ),
                "common_role_levels": sorted({role for role in roles}),
                "confidence_label": _confidence_label(len(profile_ids)),
            }
        )

    return sorted(
        archetypes,
        key=lambda archetype: (
            -archetype["support_count"],
            archetype["name"],
        ),
    )
