import json
import sqlite3

from scripts.normalize_reddit_tags import normalize_tag_json, normalize_reddit_tags


def test_normalize_tag_json_flattens_double_encoded_tags():
    assert normalize_tag_json('["[\\"LEADERSHIP\\", \\"RESEARCH\\"]"]') == json.dumps(
        ["LEADERSHIP", "RESEARCH"]
    )


def test_normalize_tag_json_preserves_valid_tag_json():
    assert normalize_tag_json('["NONE"]') == json.dumps(["NONE"])


def test_normalize_reddit_tags_updates_only_reddit_rows(tmp_path):
    db_path = tmp_path / "tags.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE students (id INTEGER PRIMARY KEY, source TEXT, ec_tags TEXT, circumstance_tags TEXT)"
    )
    conn.execute(
        "INSERT INTO students VALUES (1, 'REDDIT_SCRAPED', ?, ?)",
        ('["[\\"LEADERSHIP\\"]"]', '["[\\"NONE\\"]"]'),
    )
    conn.execute(
        "INSERT INTO students VALUES (2, 'BC', ?, ?)",
        ('["[\\"SPORTS\\"]"]', '["[\\"NONE\\"]"]'),
    )
    conn.commit()
    conn.close()

    result = normalize_reddit_tags(db_path)

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, ec_tags, circumstance_tags FROM students ORDER BY id"
    ).fetchall()
    conn.close()

    assert result["updated"] == 1
    assert rows[0] == (1, '["LEADERSHIP"]', '["NONE"]')
    assert rows[1] == (2, '["[\\"SPORTS\\"]"]', '["[\\"NONE\\"]"]')
