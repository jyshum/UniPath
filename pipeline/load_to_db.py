# pipeline/load_to_db.py

import json
import pandas as pd
from pathlib import Path
from sqlalchemy.orm import Session

from database.models import Student, init_db, get_engine

BC_EXTRACTED_PATH = Path("data/cleaned/bc_extracted.csv")


def parse_tags(raw) -> str:
    """
    Converts pipe-separated tag string to JSON array string.
    "SPORTS|ARTS" -> '["SPORTS", "ARTS"]'
    """
    if pd.isna(raw) or str(raw).strip() == "":
        return json.dumps([])
    tags = [t.strip() for t in str(raw).split("|") if t.strip()]
    return json.dumps(tags)


def row_to_student(row: pd.Series) -> Student:
    """Maps a DataFrame row to a Student ORM object."""
    return Student(
        source=row.get("source"),
        pulled_at=str(row.get("pulled_at")) if pd.notna(row.get("pulled_at")) else None,
        school_raw=row.get("school_raw") if pd.notna(row.get("school_raw")) else None,
        school_normalized=row.get("school_normalized") if pd.notna(row.get("school_normalized")) else None,
        multi_school_flag=bool(row.get("multi_school_flag")),
        program_raw=row.get("program_raw") if pd.notna(row.get("program_raw")) else None,
        program_category=row.get("program_category") if pd.notna(row.get("program_category")) else None,
        decision=row.get("decision") if pd.notna(row.get("decision")) else None,
        grade_11_avg=float(row["grade_11_avg"]) if pd.notna(row.get("grade_11_avg")) else None,
        grade_12_avg=float(row["grade_12_avg"]) if pd.notna(row.get("grade_12_avg")) else None,
        core_avg=float(row["core_avg"]) if pd.notna(row.get("core_avg")) else None,
        ec_tags=parse_tags(row.get("ec_tags")),
        circumstance_tags=parse_tags(row.get("circumstance_tags")),
        province=row.get("province") if pd.notna(row.get("province")) else None,
        citizenship=row.get("citizenship") if pd.notna(row.get("citizenship")) else None,
        scholarship=row.get("scholarship") if pd.notna(row.get("scholarship")) else None,
        comments_raw=row.get("comments_raw") if pd.notna(row.get("comments_raw")) else None,
        ec_raw=row.get("ec_raw") if pd.notna(row.get("ec_raw")) else None,
        circumstances_raw=row.get("circumstances_raw") if pd.notna(row.get("circumstances_raw")) else None,
    )


def run():
    """
    Loads bc_extracted.csv into the SQLite database.
    Clears existing BC rows before inserting to avoid duplicates on re-run.
    Prints a summary on completion.
    """
    print("Initializing database...")
    engine = init_db()

    print(f"Reading {BC_EXTRACTED_PATH}...")
    df = pd.read_csv(BC_EXTRACTED_PATH)
    print(f"  {len(df)} rows to load")

    with Session(engine) as session:
        # Delete existing BC rows before re-inserting
        # This is the upsert strategy: clear and reload
        deleted = session.query(Student).filter(Student.source == "BC").delete()
        if deleted:
            print(f"  Cleared {deleted} existing BC rows")

        students = [row_to_student(row) for _, row in df.iterrows()]
        session.add_all(students)
        session.commit()
        print(f"  Inserted {len(students)} rows")

        # Summary
        total = session.query(Student).count()
        bc_count = session.query(Student).filter(Student.source == "BC").count()
        print(f"\nDatabase summary:")
        print(f"  Total rows: {total}")
        print(f"  BC rows: {bc_count}")


if __name__ == "__main__":
    run()