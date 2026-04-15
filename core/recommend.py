# recommend.py

import json
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