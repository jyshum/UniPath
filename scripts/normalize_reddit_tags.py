import json
import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).parent.parent / "database" / "unipath.db"
TAG_COLUMNS = ("ec_tags", "circumstance_tags")


def normalize_tag_json(raw: str | None) -> str:
    if not raw:
        return json.dumps([])

    try:
        tags = json.loads(raw)
    except json.JSONDecodeError:
        return json.dumps([])

    if (
        isinstance(tags, list)
        and len(tags) == 1
        and isinstance(tags[0], str)
        and tags[0].strip().startswith("[")
    ):
        try:
            nested = json.loads(tags[0])
            if isinstance(nested, list):
                tags = nested
        except json.JSONDecodeError:
            pass

    if not isinstance(tags, list):
        return json.dumps([])

    return json.dumps([str(tag).strip() for tag in tags if str(tag).strip()])


def normalize_reddit_tags(db_path: str | Path = DB_PATH) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, ec_tags, circumstance_tags FROM students WHERE source = 'REDDIT_SCRAPED'"
    ).fetchall()

    updated = 0
    for row_id, ec_tags, circumstance_tags in rows:
        normalized_ec = normalize_tag_json(ec_tags)
        normalized_circumstances = normalize_tag_json(circumstance_tags)
        if normalized_ec != ec_tags or normalized_circumstances != circumstance_tags:
            conn.execute(
                "UPDATE students SET ec_tags = ?, circumstance_tags = ? WHERE id = ?",
                (normalized_ec, normalized_circumstances, row_id),
            )
            updated += 1

    conn.commit()
    conn.close()
    return {"checked": len(rows), "updated": updated}


if __name__ == "__main__":
    result = normalize_reddit_tags()
    print(f"Checked Reddit rows: {result['checked']}")
    print(f"Updated Reddit rows: {result['updated']}")
