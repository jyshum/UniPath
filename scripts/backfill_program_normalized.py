"""One-time migration: populate program_normalized on all existing student records."""
import sqlite3
from pathlib import Path

from pipeline.program_names import get_program_category, normalize_program_name

DB_PATH = Path("database/unipath.db")


def backfill_program_normalized(db_path: str | Path = DB_PATH) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, school_normalized, program_raw, program_normalized, program_category "
        "FROM students WHERE program_raw IS NOT NULL"
    ).fetchall()

    checked = 0
    changed = 0
    for row_id, school, program_raw, current_name, current_category in rows:
        checked += 1
        normalized = normalize_program_name(program_raw, school=school)
        category = get_program_category(normalized) if normalized else current_category
        if normalized != current_name or category != current_category:
            conn.execute(
                "UPDATE students SET program_normalized = ?, program_category = ? WHERE id = ?",
                (normalized, category, row_id),
            )
            changed += 1
    conn.commit()
    conn.close()
    return {"checked": checked, "changed": changed}


def run():
    result = backfill_program_normalized(DB_PATH)
    print(f"Checked {result['checked']} rows")
    print(f"Changed {result['changed']} rows")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT program_normalized, program_category, COUNT(*) as c FROM students "
        "WHERE program_normalized IS NOT NULL GROUP BY program_normalized, program_category "
        "ORDER BY c DESC"
    )
    print("\nProgram distribution:")
    for name, category, count in cursor.fetchall():
        print(f"  {name} ({category}): {count}")
    conn.close()


if __name__ == "__main__":
    run()
