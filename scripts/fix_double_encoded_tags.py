"""
One-time fix: Reddit-scraped rows have double-JSON-encoded ec_tags and
circumstance_tags. e.g. '["[\\"SPORTS\\", \\"ARTS\\"]"]' instead of
'["SPORTS", "ARTS"]'. This script normalizes them in place.
"""
import json
import sqlite3

DB_PATH = "database/unipath.db"


def fix_double_encoded(conn: sqlite3.Connection, column: str) -> int:
    rows = conn.execute(
        f"SELECT id, {column} FROM students WHERE {column} IS NOT NULL"
    ).fetchall()

    fixed = 0
    for row_id, raw in rows:
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        # Detect double-encoding: a list containing a single string that is itself a JSON array
        if (
            isinstance(parsed, list)
            and len(parsed) == 1
            and isinstance(parsed[0], str)
            and parsed[0].startswith("[")
        ):
            try:
                inner = json.loads(parsed[0])
                if isinstance(inner, list):
                    conn.execute(
                        f"UPDATE students SET {column} = ? WHERE id = ?",
                        (json.dumps(inner), row_id),
                    )
                    fixed += 1
            except json.JSONDecodeError:
                continue

    return fixed


def main():
    conn = sqlite3.connect(DB_PATH)

    ec_fixed = fix_double_encoded(conn, "ec_tags")
    print(f"Fixed {ec_fixed} double-encoded ec_tags rows")

    circ_fixed = fix_double_encoded(conn, "circumstance_tags")
    print(f"Fixed {circ_fixed} double-encoded circumstance_tags rows")

    conn.commit()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
