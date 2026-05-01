import sqlite3

from scripts.backfill_program_normalized import backfill_program_normalized


def test_backfill_uses_school_aware_taxonomy_and_preserves_sources(tmp_path):
    db_path = tmp_path / "programs.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE students (
            id INTEGER PRIMARY KEY,
            source TEXT,
            school_normalized TEXT,
            program_raw TEXT,
            program_normalized TEXT,
            program_category TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "REDDIT_SCRAPED", "University of Waterloo", "SYDE", None, None),
            (2, "USER_SUBMITTED", "UBC Vancouver", "Applied Science", None, None),
            (3, "BC", "UBC Vancouver", "Science", None, None),
        ],
    )
    conn.commit()
    conn.close()

    result = backfill_program_normalized(db_path)

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT source, program_normalized, program_category FROM students ORDER BY id"
    ).fetchall()
    conn.close()

    assert result["checked"] == 3
    assert rows == [
        ("REDDIT_SCRAPED", "Systems Design Engineering", "ENGINEERING"),
        ("USER_SUBMITTED", "Engineering", "ENGINEERING"),
        ("BC", "Science", "SCIENCE"),
    ]
