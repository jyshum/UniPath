# recommend.py

import json
import json as _json
import sqlite3
import pandas as pd
from pathlib import Path
from core import calibrate

DB_PATH = Path(__file__).parent.parent / "database" / "unipath.db"
DEFAULT_TOLERANCE = 2.0


def get_connection():
    return sqlite3.connect(DB_PATH)


def find_similar(
    grade: float,
    program_category: str,
    school: str = None,
    tolerance: float = DEFAULT_TOLERANCE,
    min_results: int = 10,
    max_tolerance: float = 10.0,
) -> tuple[pd.DataFrame, float]:
    """
    Core query engine. Automatically widens tolerance if results are too thin.

    Returns:
        Tuple of (DataFrame of matching students, tolerance actually used)
    """
    current_tolerance = tolerance

    while current_tolerance <= max_tolerance:
        conn = get_connection()

        query = """
            SELECT
                school_normalized,
                program_category,
                decision,
                core_avg,
                grade_11_avg,
                grade_12_avg,
                citizenship,
                province
            FROM students
            WHERE program_category = :program
            AND core_avg IS NOT NULL
            AND ABS(core_avg - :grade) <= :tolerance
        """
        params = {
            "program": program_category.upper(),
            "grade": grade,
            "tolerance": current_tolerance,
        }

        if school:
            query += " AND school_normalized = :school"
            params["school"] = school

        df = pd.read_sql(query, conn, params=params)
        conn.close()

        if len(df) >= min_results or current_tolerance >= max_tolerance:
            return df, current_tolerance

        current_tolerance += 1.0

    return df, current_tolerance


def lookup_school(
    school: str,
    grade: float,
    program_category: str,
    tolerance: float = DEFAULT_TOLERANCE,
) -> dict:
    df, used_tolerance = find_similar(
        grade, program_category, school=school, tolerance=tolerance
    )
    result = summarize_results(df, school=school)
    result["tolerance_used"] = used_tolerance
    if used_tolerance > tolerance:
        result["note"] = (
            f"Not enough data at ±{tolerance}. "
            f"Widened search to ±{used_tolerance} to find more results."
        )
    result["acceptance_probability"] = calibrate.calibrated_probability(
        school, program_category, grade, tolerance
    )
    return result


def discover_schools(
    grade: float,
    program_category: str,
    tolerance: float = DEFAULT_TOLERANCE,
    min_results: int = 3,
) -> list[dict]:
    df, used_tolerance = find_similar(
        grade, program_category, tolerance=tolerance
    )

    if df.empty:
        return []

    results = []
    for school in df["school_normalized"].dropna().unique():
        school_df = df[df["school_normalized"] == school]
        if len(school_df) < min_results:
            continue
        summary = summarize_results(school_df, school=school)
        summary["tolerance_used"] = used_tolerance
        results.append(summary)

    results.sort(
        key=lambda x: next(
            (b["count"] for b in x["breakdown"] if b["decision"] == "ACCEPTED"), 0
        ),
        reverse=True,
    )

    return results

def summarize_results(df: pd.DataFrame, school: str = None) -> dict:
    """
    Takes a DataFrame of similar students and builds a summary dict.

    Returns:
        {
            "school": str,
            "total_similar": int,
            "breakdown": [
                {
                    "decision": "ACCEPTED",
                    "count": 7,
                    "avg_grade": 96.1,
                    "min_grade": 91.5,
                    "max_grade": 99.0,
                }
            ]
        }
    """
    if df.empty:
        return {
            "school": school or "All schools",
            "total_similar": 0,
            "breakdown": [],
            "note": "Not enough data to make a recommendation.",
        }

    breakdown = []
    decision_order = ["ACCEPTED", "DEFERRED", "WAITLISTED", "REJECTED"]

    for decision in decision_order:
        subset = df[df["decision"] == decision]
        if subset.empty:
            continue
        breakdown.append({
            "decision": decision,
            "count": len(subset),
            "avg_grade": round(subset["core_avg"].mean(), 1),
            "min_grade": round(subset["core_avg"].min(), 1),
            "max_grade": round(subset["core_avg"].max(), 1),
        })

    return {
        "school": school or "All schools",
        "total_similar": len(df),
        "breakdown": breakdown,
    }

GRADE_BUCKETS = [
    ("< 70", 0, 69.99),
    ("70-74", 70, 74.99),
    ("75-79", 75, 79.99),
    ("80-84", 80, 84.99),
    ("85-89", 85, 89.99),
    ("90-94", 90, 94.99),
    ("95-100", 95, 100),
]


def program_stats(school: str, program_name: str) -> dict:
    """Returns merged stats for a school+program from both CUDO and pipeline data."""
    conn = get_connection()

    # --- CUDO data ---
    cudo_rows = conn.execute(
        "SELECT year, pct_95_plus, pct_90_94, pct_85_89, pct_80_84, "
        "pct_75_79, pct_70_74, pct_below_70, overall_avg "
        "FROM cudo_programs WHERE school = ? AND program_name = ? "
        "ORDER BY year DESC",
        (school, program_name),
    ).fetchall()

    # --- Pipeline data ---
    pipeline_rows = conn.execute(
        "SELECT decision, core_avg, ec_tags, source FROM students "
        "WHERE school_normalized = ? AND program_normalized = ? AND core_avg IS NOT NULL",
        (school, program_name),
    ).fetchall()

    has_cudo = len(cudo_rows) > 0
    has_pipeline = len(pipeline_rows) > 0

    if not has_cudo and not has_pipeline:
        return {"error": "no_data"}

    # Determine data tier
    if has_cudo and has_pipeline:
        data_tier = "both"
    elif has_cudo:
        data_tier = "official"
    else:
        data_tier = "community"

    # --- Grade distribution ---
    if has_cudo:
        latest = cudo_rows[0]
        _, p95, p90, p85, p80, p75, p70, pbelow, _ = latest
        grade_dist = [
            {"bucket": "95-100", "pct": p95, "accepted": None, "rejected": None, "waitlisted": None, "deferred": None},
            {"bucket": "90-94", "pct": p90, "accepted": None, "rejected": None, "waitlisted": None, "deferred": None},
            {"bucket": "85-89", "pct": p85, "accepted": None, "rejected": None, "waitlisted": None, "deferred": None},
            {"bucket": "80-84", "pct": p80, "accepted": None, "rejected": None, "waitlisted": None, "deferred": None},
            {"bucket": "75-79", "pct": p75, "accepted": None, "rejected": None, "waitlisted": None, "deferred": None},
            {"bucket": "70-74", "pct": p70, "accepted": None, "rejected": None, "waitlisted": None, "deferred": None},
            {"bucket": "< 70", "pct": pbelow, "accepted": None, "rejected": None, "waitlisted": None, "deferred": None},
        ]
    else:
        grade_dist = []
        for label, lo, hi in GRADE_BUCKETS:
            bucket = {"bucket": label, "pct": None, "accepted": 0, "rejected": 0, "waitlisted": 0, "deferred": 0}
            for decision, grade, _, _ in pipeline_rows:
                if lo <= grade <= hi and decision:
                    key = decision.lower()
                    if key in bucket:
                        bucket[key] += 1
            grade_dist.append(bucket)

    # --- EC breakdown (pipeline only) ---
    from collections import Counter
    ec_counter = Counter()
    accepted_count = 0
    accepted_grades = []
    source_counter = Counter()

    for decision, grade, ec_tags_str, source in pipeline_rows:
        source_counter[source] += 1
        if decision == "ACCEPTED":
            accepted_count += 1
            accepted_grades.append(grade)
            if ec_tags_str:
                try:
                    tags = _json.loads(ec_tags_str)
                    for tag in tags:
                        if tag not in ("NONE", "OTHER"):
                            ec_counter[tag] += 1
                except (_json.JSONDecodeError, TypeError):
                    pass

    ec_breakdown = [
        {"tag": tag, "count": count, "pct": round(count / accepted_count * 100)}
        for tag, count in ec_counter.most_common()
    ] if accepted_count > 0 else []

    # --- Historical trends (CUDO only) ---
    historical = []
    if has_cudo:
        for row in reversed(cudo_rows):
            year, _, _, _, _, _, _, _, avg = row
            if avg is not None:
                historical.append({"year": year, "overall_avg": avg})

    # --- Overall avg ---
    if has_cudo:
        overall_avg = cudo_rows[0][8]
    elif accepted_grades:
        overall_avg = round(sum(accepted_grades) / len(accepted_grades), 1)
    else:
        overall_avg = None

    # --- Data sources ---
    data_sources = dict(source_counter)
    if has_cudo:
        data_sources["CUDO_OFFICIAL"] = len(cudo_rows)

    # --- Get program_category ---
    pc_conn = get_connection()
    if has_cudo:
        pc_row = pc_conn.execute(
            "SELECT program_category FROM cudo_programs WHERE school = ? AND program_name = ? LIMIT 1",
            (school, program_name),
        ).fetchone()
    else:
        pc_row = pc_conn.execute(
            "SELECT program_category FROM students WHERE school_normalized = ? AND program_normalized = ? LIMIT 1",
            (school, program_name),
        ).fetchone()
    pc_conn.close()
    conn.close()
    program_category = pc_row[0] if pc_row else "OTHER"

    return {
        "school": school,
        "program_name": program_name,
        "program_category": program_category,
        "data_tier": data_tier,
        "grade_distribution": grade_dist,
        "ec_breakdown": ec_breakdown,
        "overall_avg": overall_avg,
        "historical": historical,
        "total_records": len(pipeline_rows) if has_pipeline else None,
        "accepted_count": accepted_count if has_pipeline else None,
        "avg_admitted_grade": round(sum(accepted_grades) / len(accepted_grades), 1) if accepted_grades else None,
        "grade_range": {
            "min": round(min(accepted_grades), 1),
            "max": round(max(accepted_grades), 1),
        } if accepted_grades else None,
        "data_sources": data_sources,
    }


def list_programs(min_records: int = 10, category: str = None) -> list[dict]:
    """Returns all programs from both pipeline and CUDO data, deduplicated."""
    conn = get_connection()

    # Pipeline programs: group by school + program_normalized
    pipeline_query = """
        SELECT school_normalized, program_normalized, program_category,
               COUNT(*) as cnt,
               SUM(CASE WHEN decision = 'ACCEPTED' THEN 1 ELSE 0 END) as accepted
        FROM students
        WHERE school_normalized IS NOT NULL
          AND program_normalized IS NOT NULL
          AND core_avg IS NOT NULL
        GROUP BY school_normalized, program_normalized
        HAVING cnt >= ?
        ORDER BY cnt DESC
    """
    pipeline_rows = conn.execute(pipeline_query, (min_records,)).fetchall()

    # CUDO programs: most recent year per school+program
    cudo_query = """
        SELECT school, program_name, program_category, overall_avg, MAX(year) as latest_year
        FROM cudo_programs
        GROUP BY school, program_name
        ORDER BY school, program_name
    """
    cudo_rows = conn.execute(cudo_query).fetchall()
    conn.close()

    programs = {}

    for school, program_name, program_category, total, accepted in pipeline_rows:
        key = (school, program_name)
        programs[key] = {
            "school": school,
            "program_name": program_name,
            "program_category": program_category,
            "data_tier": "community",
            "total_records": total,
            "accepted": accepted,
            "overall_avg": None,
        }

    for school, program_name, program_category, overall_avg, year in cudo_rows:
        key = (school, program_name)
        if key in programs:
            programs[key]["data_tier"] = "both"
            programs[key]["overall_avg"] = overall_avg
        else:
            programs[key] = {
                "school": school,
                "program_name": program_name,
                "program_category": program_category,
                "data_tier": "official",
                "total_records": None,
                "accepted": None,
                "overall_avg": overall_avg,
            }

    result = list(programs.values())

    if category:
        result = [p for p in result if p["program_category"] == category.upper()]

    result.sort(key=lambda p: (
        0 if p["data_tier"] == "both" else 1 if p["data_tier"] == "official" else 2,
        -(p["total_records"] or 0),
    ))

    return result


def print_summary(summary: dict):
    """Pretty-prints a single school summary."""
    print(f"\nSchool: {summary['school']}")
    if "note" in summary:
        print(f"  ℹ️  {summary['note']}")
    print(f"Similar students found: {summary['total_similar']}")

    if not summary["breakdown"]:
        print(f"  {summary.get('note', 'No data.')}")
        return

    for b in summary["breakdown"]:
        if b["count"] == 1:
            print(f"  {b['decision']:<12} — {b['count']} student  "
                  f"— grade: {b['avg_grade']}")
        else:
            print(f"  {b['decision']:<12} — {b['count']} students "
                  f"— avg {b['avg_grade']}, range {b['min_grade']}–{b['max_grade']}")


if __name__ == "__main__":
    # Test Mode 1 — School lookup
    print("=" * 50)
    print("MODE 1 — School Lookup")
    print("Profile: 94.0 core avg, ENGINEERING, UBC Vancouver")
    print("=" * 50)
    result = lookup_school("UBC Vancouver", 94.0, "ENGINEERING")
    print_summary(result)

    # Test Mode 2 — School discovery
    print("\n" + "=" * 50)
    print("MODE 2 — School Discovery")
    print("Profile: 94.0 core avg, ENGINEERING")
    print("=" * 50)
    schools = discover_schools(94.0, "ENGINEERING")
    if not schools:
        print("No schools found with enough data.")
    for s in schools:
        print_summary(s)