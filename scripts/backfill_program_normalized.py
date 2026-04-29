# scripts/backfill_program_normalized.py
"""One-time migration: populate program_normalized on all existing student records."""
import sqlite3
from pipeline.program_names import normalize_program_name

DB_PATH = "database/unipath.db"


def run():
    conn = sqlite3.connect(DB_PATH)

    rows = conn.execute(
        "SELECT id, program_raw FROM students WHERE program_raw IS NOT NULL"
    ).fetchall()

    print(f"Processing {len(rows)} rows...")

    updated = 0
    for row_id, program_raw in rows:
        normalized = normalize_program_name(program_raw)
        if normalized:
            conn.execute(
                "UPDATE students SET program_normalized = ? WHERE id = ?",
                (normalized, row_id),
            )
            updated += 1

    conn.commit()
    conn.close()
    print(f"Updated {updated} rows with program_normalized")

    # Summary
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT program_normalized, COUNT(*) as c FROM students "
        "WHERE program_normalized IS NOT NULL "
        "GROUP BY program_normalized ORDER BY c DESC"
    )
    print("\nProgram distribution:")
    for name, count in cursor.fetchall():
        print(f"  {name}: {count}")
    conn.close()


if __name__ == "__main__":
    run()
