# CUDO Data Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate official Ontario university grade distributions (CUDO) as a second data source, re-key program pages from broad categories to specific program names, and merge both data sources at the API layer.

**Architecture:** New `cudo_programs` table stores aggregate grade percentages. A normalization layer maps variant program names to canonical names. The API merges CUDO and pipeline data, returning unified responses. The frontend gains a category filter bar, percentage-mode grade charts, data tier badges, and historical trends.

**Tech Stack:** Python/SQLAlchemy (backend), FastAPI (API), Next.js 16/React 19 (frontend), BeautifulSoup (scraper), SQLite (DB)

**Spec:** `docs/superpowers/specs/2026-04-28-cudo-integration-design.md`

---

## File Structure

**Create:**
- `pipeline/program_names.py` — Program name normalization maps and helper function
- `pipeline/cudo_scraper.py` — CUDO HTML table scraper
- `scripts/backfill_program_normalized.py` — One-time migration for existing student records
- `tests/test_program_names.py` — Tests for normalization
- `tests/test_cudo_scraper.py` — Tests for CUDO scraper parsing
- `tests/test_cudo_api.py` — Tests for merged API endpoints

**Modify:**
- `database/models.py` — Add `CudoProgram` model, add `program_normalized` to `Student`
- `core/recommend.py` — Update `program_stats()`, `list_programs()`, update grade buckets to 7
- `server/main.py` — Update API endpoints for new routing and merged responses
- `frontend/lib/types.ts` — Update TypeScript interfaces
- `frontend/components/ProgramCard.tsx` — Show program_name, data tier badge, overall_avg
- `frontend/components/GradeDistribution.tsx` — Add percentage mode
- `frontend/app/page.tsx` — Add category filter bar, use new ProgramSummary shape
- `frontend/app/program/[school]/[program]/page.tsx` — Adapt to merged ProgramStats, add historical trends

---

### Task 1: Program Name Normalization Module

**Files:**
- Create: `pipeline/program_names.py`
- Create: `tests/test_program_names.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_program_names.py
from pipeline.program_names import normalize_program_name, get_program_category


def test_normalize_cudo_name():
    """CUDO-style names map to canonical names."""
    assert normalize_program_name("Computer & Information Science") == "Computer Science"
    assert normalize_program_name("Commerce/Management/Business Admin") == "Commerce"
    assert normalize_program_name("Biological & Biomedical Sciences") == "Biological Sciences"


def test_normalize_pipeline_variant():
    """Pipeline program_raw variants map to canonical names."""
    assert normalize_program_name("CompSci") == "Computer Science"
    assert normalize_program_name("CS") == "Computer Science"
    assert normalize_program_name("Life Sci") == "Life Sciences"
    assert normalize_program_name("Sauder") == "Commerce"
    assert normalize_program_name("Ivey AEO") == "Business Administration"


def test_normalize_passthrough():
    """Names not in the map pass through unchanged."""
    assert normalize_program_name("Engineering") == "Engineering"
    assert normalize_program_name("Nursing") == "Nursing"


def test_normalize_case_insensitive():
    """Lookup is case-insensitive."""
    assert normalize_program_name("compsci") == "Computer Science"
    assert normalize_program_name("COMPSCI") == "Computer Science"


def test_normalize_none_returns_none():
    """None input returns None."""
    assert normalize_program_name(None) is None


def test_get_program_category():
    """Canonical names map to broad categories."""
    assert get_program_category("Computer Science") == "COMPUTER_SCIENCE"
    assert get_program_category("Commerce") == "BUSINESS"
    assert get_program_category("Engineering") == "ENGINEERING"
    assert get_program_category("Life Sciences") == "SCIENCE"
    assert get_program_category("Nursing") == "HEALTH"


def test_get_program_category_unknown():
    """Unknown program names return OTHER."""
    assert get_program_category("Underwater Basket Weaving") == "OTHER"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_program_names.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.program_names'`

- [ ] **Step 3: Write the implementation**

```python
# pipeline/program_names.py
"""Program name normalization. Maps variant names to canonical program names."""

# Keys are lowercase for case-insensitive lookup.
# Values are the canonical program name.
_PROGRAM_NAME_MAP = {
    # CUDO names → canonical
    "computer & information science": "Computer Science",
    "commerce/management/business admin": "Commerce",
    "biological & biomedical sciences": "Biological Sciences",
    "health profession & related programs": "Health Sciences",
    "kinesiology/recreation/physical education": "Kinesiology",
    "fine & applied arts": "Fine Arts",
    "liberal arts & sciences/general studies": "Arts",
    "mathematics & statistics": "Mathematics",
    "physical science": "Physical Sciences",
    "social sciences": "Social Sciences",

    # Pipeline program_raw variants → canonical
    "compsci": "Computer Science",
    "cs": "Computer Science",
    "computer science": "Computer Science",
    "life sci": "Life Sciences",
    "life sciences": "Life Sciences",
    "sauder": "Commerce",
    "bcomm": "Commerce",
    "commerce": "Commerce",
    "ivey aeo": "Business Administration",
    "ivey": "Business Administration",
    "business administration": "Business Administration",
    "health sci": "Health Sciences",
    "health sciences": "Health Sciences",
    "biomed": "Biomedical Sciences",
    "biomedical sciences": "Biomedical Sciences",
    "kin": "Kinesiology",
    "kinesiology": "Kinesiology",
    "med sci": "Medical Sciences",
    "medical sciences": "Medical Sciences",
    "nursing": "Nursing",
    "pharmacy": "Pharmacy",
    "psychology": "Psychology",
    "engineering": "Engineering",
    "science": "Science",
    "arts": "Arts",
    "mathematics": "Mathematics",
    "economics": "Economics",
    "education": "Education",
    "law": "Law",
    "architecture": "Architecture",
    "biochemistry": "Biochemistry",
    "physics": "Physics",
}

# Canonical program name → broad category
_PROGRAM_CATEGORY_MAP = {
    "Computer Science": "COMPUTER_SCIENCE",
    "Commerce": "BUSINESS",
    "Business Administration": "BUSINESS",
    "Engineering": "ENGINEERING",
    "Life Sciences": "SCIENCE",
    "Biological Sciences": "SCIENCE",
    "Biomedical Sciences": "SCIENCE",
    "Science": "SCIENCE",
    "Physical Sciences": "SCIENCE",
    "Mathematics": "SCIENCE",
    "Biochemistry": "SCIENCE",
    "Physics": "SCIENCE",
    "Health Sciences": "HEALTH",
    "Medical Sciences": "HEALTH",
    "Nursing": "HEALTH",
    "Kinesiology": "HEALTH",
    "Pharmacy": "HEALTH",
    "Arts": "ARTS",
    "Fine Arts": "ARTS",
    "Social Sciences": "ARTS",
    "Psychology": "ARTS",
    "Economics": "ARTS",
    "Education": "EDUCATION",
    "Law": "LAW",
    "Architecture": "OTHER",
}


def normalize_program_name(raw: str | None) -> str | None:
    """Normalize a program name to its canonical form.

    Returns the canonical name if found in the map, otherwise returns
    the input unchanged (stripped). Returns None for None input.
    """
    if raw is None:
        return None
    key = raw.strip().lower()
    if key in _PROGRAM_NAME_MAP:
        return _PROGRAM_NAME_MAP[key]
    return raw.strip()


def get_program_category(canonical_name: str) -> str:
    """Get the broad program category for a canonical program name.

    Returns 'OTHER' if the name is not in the category map.
    """
    return _PROGRAM_CATEGORY_MAP.get(canonical_name, "OTHER")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_program_names.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/program_names.py tests/test_program_names.py
git commit -m "feat: add program name normalization module"
```

---

### Task 2: Database Models — CudoProgram + Student.program_normalized

**Files:**
- Modify: `database/models.py`

- [ ] **Step 1: Add CudoProgram model and program_normalized column to Student**

Add to `database/models.py` after the `Student` class:

```python
# In Student class, add this column after program_category:
    program_normalized = Column(String, nullable=True)  # canonical program name

# New class after Student:
class CudoProgram(Base):
    __tablename__ = "cudo_programs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school = Column(String, nullable=False)
    program_name = Column(String, nullable=False)
    program_category = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    pct_95_plus = Column(Float, nullable=True)
    pct_90_94 = Column(Float, nullable=True)
    pct_85_89 = Column(Float, nullable=True)
    pct_80_84 = Column(Float, nullable=True)
    pct_75_79 = Column(Float, nullable=True)
    pct_70_74 = Column(Float, nullable=True)
    pct_below_70 = Column(Float, nullable=True)
    overall_avg = Column(Float, nullable=True)
    source_url = Column(String, nullable=True)
```

- [ ] **Step 2: Verify the DB initializes with new table**

```bash
python3 -c "
from database.models import init_db, CudoProgram, Student
engine = init_db()
print('Tables created successfully')
# Verify column exists
import sqlite3
conn = sqlite3.connect('database/unipath.db')
cols = [r[1] for r in conn.execute('PRAGMA table_info(cudo_programs)').fetchall()]
print('cudo_programs columns:', cols)
scols = [r[1] for r in conn.execute('PRAGMA table_info(students)').fetchall()]
print('program_normalized in students:', 'program_normalized' in scols)
"
```

Expected: Tables created, `cudo_programs` has all columns, `program_normalized` in students.

**Note:** SQLAlchemy's `create_all` only creates new tables and won't add new columns to existing tables. If `program_normalized` is not in the students table, run:

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('database/unipath.db')
try:
    conn.execute('ALTER TABLE students ADD COLUMN program_normalized TEXT')
    conn.commit()
    print('Column added')
except Exception as e:
    print(f'Column may already exist: {e}')
"
```

- [ ] **Step 3: Commit**

```bash
git add database/models.py
git commit -m "feat: add CudoProgram model and program_normalized column"
```

---

### Task 3: Backfill program_normalized on Existing Records

**Files:**
- Create: `scripts/backfill_program_normalized.py`

- [ ] **Step 1: Write the backfill script**

```python
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
```

- [ ] **Step 2: Run the backfill**

```bash
python3 -m scripts.backfill_program_normalized
```

Expected: "Updated N rows with program_normalized" and a distribution table.

- [ ] **Step 3: Commit**

```bash
git add scripts/backfill_program_normalized.py
git commit -m "feat: backfill program_normalized on existing student records"
```

---

### Task 4: CUDO Scraper — Probe and Build

**Files:**
- Create: `pipeline/cudo_scraper.py`
- Create: `tests/test_cudo_scraper.py`

- [ ] **Step 1: Write parser tests using saved HTML fixture**

First, save a real CUDO HTML page as a test fixture. Fetch the Windsor B3 page and save it:

```bash
curl -s "https://www.uwindsor.ca/common-university-data-ontario/421/b-admission-2023" -o tests/fixtures/windsor_cudo_b3.html
mkdir -p tests/fixtures
```

Then write the tests:

```python
# tests/test_cudo_scraper.py
import pytest
from pathlib import Path
from pipeline.cudo_scraper import parse_cudo_b3_table


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_parse_returns_list_of_dicts():
    """Parser returns a list of program dicts from HTML."""
    html = (FIXTURE_DIR / "windsor_cudo_b3.html").read_text()
    results = parse_cudo_b3_table(html, school="University of Windsor", year=2023)
    assert isinstance(results, list)
    assert len(results) > 0


def test_parse_program_has_required_fields():
    """Each parsed program has all required fields."""
    html = (FIXTURE_DIR / "windsor_cudo_b3.html").read_text()
    results = parse_cudo_b3_table(html, school="University of Windsor", year=2023)
    required = {"school", "program_name", "program_category", "year",
                "pct_95_plus", "pct_90_94", "pct_85_89", "pct_80_84",
                "pct_75_79", "pct_70_74", "pct_below_70", "overall_avg"}
    for r in results:
        assert required.issubset(r.keys()), f"Missing keys: {required - r.keys()}"


def test_parse_percentages_are_floats():
    """Percentage values are floats between 0 and 100."""
    html = (FIXTURE_DIR / "windsor_cudo_b3.html").read_text()
    results = parse_cudo_b3_table(html, school="University of Windsor", year=2023)
    pct_fields = ["pct_95_plus", "pct_90_94", "pct_85_89", "pct_80_84",
                  "pct_75_79", "pct_70_74", "pct_below_70"]
    for r in results:
        for field in pct_fields:
            val = r[field]
            if val is not None:
                assert isinstance(val, float), f"{field} is {type(val)}"
                assert 0 <= val <= 100, f"{field} = {val}"


def test_parse_skips_overall_total_row():
    """The 'OVERALL' or 'Total' row is excluded from results."""
    html = (FIXTURE_DIR / "windsor_cudo_b3.html").read_text()
    results = parse_cudo_b3_table(html, school="University of Windsor", year=2023)
    names = [r["program_name"] for r in results]
    for name in names:
        assert "total" not in name.lower()
        assert "overall" not in name.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cudo_scraper.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.cudo_scraper'`

- [ ] **Step 3: Write the scraper implementation**

```python
# pipeline/cudo_scraper.py
"""CUDO B3 table scraper. Fetches and parses entering averages from Ontario universities."""
import time
import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from database.models import CudoProgram, init_db
from pipeline.program_names import normalize_program_name, get_program_category

HEADERS = {"User-Agent": "unipath-ai/1.0 (research project)"}
REQUEST_DELAY = 2

# Each entry: school name, list of (year, url) tuples.
# Populated during the probe step — add confirmed universities here.
UNIVERSITY_CONFIGS = {
    "University of Windsor": [
        (2023, "https://www.uwindsor.ca/common-university-data-ontario/421/b-admission-2023"),
        (2022, "https://www.uwindsor.ca/common-university-data-ontario/395/b-admission-2021"),
    ],
    # Add more universities after probing their CUDO pages.
    # Format: "School Name": [(year, url), ...]
}


def parse_cudo_b3_table(html: str, school: str, year: int) -> list[dict]:
    """Parse a CUDO B3 HTML page into a list of program dicts.

    Looks for HTML tables with grade range columns (95%+, 90-94%, etc.)
    and extracts program names with their percentage distributions.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        # Find header row to identify column positions
        header = rows[0]
        headers = [th.get_text(strip=True).lower() for th in header.find_all(["th", "td"])]

        # Check if this looks like a B3 table (has grade range columns)
        if not any("95" in h for h in headers):
            continue

        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if len(cells) < 4:
                continue

            program_raw = cells[0].strip()

            # Skip total/overall rows
            if any(skip in program_raw.lower() for skip in ["total", "overall", "university of"]):
                continue

            # Skip empty program names
            if not program_raw or program_raw == "":
                continue

            program_name = normalize_program_name(program_raw)
            program_category = get_program_category(program_name)

            # Parse percentage values — handle *, N/A, empty cells
            pct_values = []
            for cell in cells[1:]:
                cell = cell.replace("%", "").strip()
                if cell in ("*", "", "N/A", "-"):
                    pct_values.append(None)
                else:
                    try:
                        pct_values.append(float(cell))
                    except ValueError:
                        pct_values.append(None)

            # Pad if needed
            while len(pct_values) < 8:
                pct_values.append(None)

            results.append({
                "school": school,
                "program_name": program_name,
                "program_category": program_category,
                "year": year,
                "pct_95_plus": pct_values[0],
                "pct_90_94": pct_values[1],
                "pct_85_89": pct_values[2],
                "pct_80_84": pct_values[3],
                "pct_75_79": pct_values[4],
                "pct_70_74": pct_values[5],
                "pct_below_70": pct_values[6],
                "overall_avg": pct_values[7] if len(pct_values) > 7 else None,
            })

    return results


def fetch_and_parse(school: str, year: int, url: str) -> list[dict]:
    """Fetch a CUDO page and parse it."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"  Failed to fetch {url}: {e}")
        return []

    results = parse_cudo_b3_table(response.text, school, year)
    for r in results:
        r["source_url"] = url
    return results


def load_to_db(records: list[dict], school: str, engine):
    """Load parsed CUDO records into the database.

    Deletes existing records for this school before inserting (idempotent).
    """
    with Session(engine) as session:
        deleted = session.query(CudoProgram).filter(
            CudoProgram.school == school
        ).delete()
        if deleted:
            print(f"  Cleared {deleted} existing records for {school}")

        for r in records:
            session.add(CudoProgram(**r))

        session.commit()
        print(f"  Inserted {len(records)} records for {school}")


def run():
    """Scrape all configured universities and load to database."""
    print("=" * 50)
    print("CUDO Scraper — Ontario University Grade Data")
    print("=" * 50)

    engine = init_db()
    total = 0

    for school, year_urls in UNIVERSITY_CONFIGS.items():
        print(f"\nScraping {school}...")
        all_records = []

        for year, url in year_urls:
            print(f"  Year {year}: {url}")
            records = fetch_and_parse(school, year, url)
            print(f"    Parsed {len(records)} programs")
            all_records.extend(records)
            time.sleep(REQUEST_DELAY)

        if all_records:
            load_to_db(all_records, school, engine)
            total += len(all_records)

    print(f"\n{'=' * 50}")
    print(f"CUDO scraper complete. Total records loaded: {total}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Install BeautifulSoup**

```bash
pip3 install beautifulsoup4
```

- [ ] **Step 5: Save HTML fixture and run tests**

```bash
mkdir -p tests/fixtures
curl -s "https://www.uwindsor.ca/common-university-data-ontario/421/b-admission-2023" -o tests/fixtures/windsor_cudo_b3.html
python3 -m pytest tests/test_cudo_scraper.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 6: Probe additional universities**

Run a quick probe script to check which universities have accessible HTML B3 tables. The implementer should try each URL, check if it returns HTML with table data, and add working ones to `UNIVERSITY_CONFIGS`. Target universities:

- York: `https://www.yorku.ca/oipa/common-university-data-ontario-cudo/`
- Brock: `https://brocku.ca/ipap/reports/cudo/`
- Trent: `https://www.trentu.ca/oipa/common-university-data-ontario-cudo`
- Guelph: `https://irp.uoguelph.ca/data-statistics/common-university-data-ontario`
- Ottawa: `https://www.uottawa.ca/about-us/institutional-research-planning/facts-figures/cudo`
- Laurier: search for their CUDO page

For each: fetch the page, follow links to B3/admission section, check if data is in HTML tables. Add working universities to `UNIVERSITY_CONFIGS` with their year-specific URLs.

- [ ] **Step 7: Run the scraper**

```bash
python3 -m pipeline.cudo_scraper
```

Expected: Summary showing records loaded per university.

- [ ] **Step 8: Verify data in DB**

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('database/unipath.db')
cursor = conn.execute('SELECT school, COUNT(*), COUNT(DISTINCT program_name), COUNT(DISTINCT year) FROM cudo_programs GROUP BY school')
for row in cursor.fetchall():
    print(f'{row[0]}: {row[1]} records, {row[2]} programs, {row[3]} years')
total = conn.execute('SELECT COUNT(*) FROM cudo_programs').fetchone()[0]
print(f'Total CUDO records: {total}')
"
```

- [ ] **Step 9: Commit**

```bash
git add pipeline/cudo_scraper.py tests/test_cudo_scraper.py tests/fixtures/
git commit -m "feat: add CUDO HTML scraper with Windsor data"
```

---

### Task 5: Update Grade Buckets to 7-Bucket System

**Files:**
- Modify: `core/recommend.py:174-180`

- [ ] **Step 1: Update GRADE_BUCKETS constant**

In `core/recommend.py`, replace the existing `GRADE_BUCKETS`:

```python
GRADE_BUCKETS = [
    ("< 70", 0, 69.99),
    ("70-74", 70, 74.99),
    ("75-79", 75, 79.99),
    ("80-84", 80, 84.99),
    ("85-89", 85, 89.99),
    ("90-94", 90, 94.99),
    ("95-100", 95, 100),
]
```

- [ ] **Step 2: Run existing tests to verify no breakage**

Run: `python3 -m pytest tests/test_program_stats.py -v`
Expected: All 5 tests PASS (bucket structure tests check for "bucket", "accepted", "rejected" keys — still valid)

- [ ] **Step 3: Commit**

```bash
git add core/recommend.py
git commit -m "refactor: expand grade buckets from 5 to 7 (CUDO alignment)"
```

---

### Task 6: Update API — Merged list_programs and program_stats

**Files:**
- Modify: `core/recommend.py:183-295` (the `program_stats` and `list_programs` functions)
- Modify: `server/main.py:100-111`
- Create: `tests/test_cudo_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
# tests/test_cudo_api.py
import pytest
from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)


def test_get_programs_returns_list():
    """GET /programs returns a list of programs."""
    response = client.get("/programs")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_programs_has_new_fields():
    """Each program has program_name, program_category, data_tier."""
    response = client.get("/programs")
    data = response.json()
    if len(data) > 0:
        first = data[0]
        assert "program_name" in first
        assert "program_category" in first
        assert "data_tier" in first
        assert first["data_tier"] in ("official", "community", "both")


def test_get_programs_category_filter():
    """GET /programs?category=ENGINEERING filters by category."""
    response = client.get("/programs?category=ENGINEERING")
    data = response.json()
    for item in data:
        assert item["program_category"] == "ENGINEERING"


def test_get_program_detail_returns_stats():
    """GET /programs/{school}/{program_name} returns merged stats."""
    # Use a program we know exists in pipeline data
    response = client.get("/programs")
    data = response.json()
    if len(data) > 0:
        first = data[0]
        detail = client.get(
            f"/programs/{first['school']}/{first['program_name']}"
        )
        assert detail.status_code == 200
        d = detail.json()
        assert "grade_distribution" in d
        assert "ec_breakdown" in d
        assert "data_tier" in d
        assert "historical" in d
        assert "program_name" in d
        assert "program_category" in d


def test_get_program_detail_grade_buckets_have_pct():
    """Grade distribution buckets include pct field."""
    response = client.get("/programs")
    data = response.json()
    if len(data) > 0:
        first = data[0]
        detail = client.get(
            f"/programs/{first['school']}/{first['program_name']}"
        )
        d = detail.json()
        for bucket in d["grade_distribution"]:
            assert "pct" in bucket
            assert "bucket" in bucket
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cudo_api.py -v`
Expected: FAIL (endpoints return old shape)

- [ ] **Step 3: Rewrite list_programs in core/recommend.py**

Replace the existing `list_programs` function:

```python
def list_programs(min_records: int = 10, category: str = None) -> list[dict]:
    """Returns all programs from both pipeline and CUDO data, deduplicated.

    Pipeline-only programs require min_records. CUDO programs have no minimum.
    """
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

    # Build lookup: (school, program_name) -> data
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

    # Filter by category if specified
    if category:
        result = [p for p in result if p["program_category"] == category.upper()]

    # Sort: "both" first, then by total_records or overall_avg
    result.sort(key=lambda p: (
        0 if p["data_tier"] == "both" else 1 if p["data_tier"] == "official" else 2,
        -(p["total_records"] or 0),
    ))

    return result
```

- [ ] **Step 4: Rewrite program_stats in core/recommend.py**

Replace the existing `program_stats` function:

```python
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

    conn.close()

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
        # Use most recent CUDO year
        latest = cudo_rows[0]
        _, p95, p90, p85, p80, p75, p70, pbelow, _ = latest
        grade_dist = [
            {"bucket": "95-100",  "pct": p95,    "accepted": None, "rejected": None, "waitlisted": None, "deferred": None},
            {"bucket": "90-94",   "pct": p90,    "accepted": None, "rejected": None, "waitlisted": None, "deferred": None},
            {"bucket": "85-89",   "pct": p85,    "accepted": None, "rejected": None, "waitlisted": None, "deferred": None},
            {"bucket": "80-84",   "pct": p80,    "accepted": None, "rejected": None, "waitlisted": None, "deferred": None},
            {"bucket": "75-79",   "pct": p75,    "accepted": None, "rejected": None, "waitlisted": None, "deferred": None},
            {"bucket": "70-74",   "pct": p70,    "accepted": None, "rejected": None, "waitlisted": None, "deferred": None},
            {"bucket": "< 70",    "pct": pbelow, "accepted": None, "rejected": None, "waitlisted": None, "deferred": None},
        ]
    else:
        # Compute from pipeline records
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
        for row in reversed(cudo_rows):  # oldest first
            year, _, _, _, _, _, _, _, avg = row
            if avg is not None:
                historical.append({"year": year, "overall_avg": avg})

    # --- Overall avg ---
    if has_cudo:
        overall_avg = cudo_rows[0][8]  # most recent year
    elif accepted_grades:
        overall_avg = round(sum(accepted_grades) / len(accepted_grades), 1)
    else:
        overall_avg = None

    # --- Data sources ---
    data_sources = dict(source_counter)
    if has_cudo:
        data_sources["CUDO_OFFICIAL"] = len(cudo_rows)

    # --- Get program_category ---
    if has_cudo:
        program_category = conn.execute(
            "SELECT program_category FROM cudo_programs WHERE school = ? AND program_name = ? LIMIT 1",
            (school, program_name),
        ).fetchone()
        # Connection is closed, re-fetch
        _conn = get_connection()
        pc_row = _conn.execute(
            "SELECT program_category FROM cudo_programs WHERE school = ? AND program_name = ? LIMIT 1",
            (school, program_name),
        ).fetchone()
        _conn.close()
        program_category = pc_row[0] if pc_row else "OTHER"
    elif pipeline_rows:
        _conn = get_connection()
        pc_row = _conn.execute(
            "SELECT program_category FROM students WHERE school_normalized = ? AND program_normalized = ? LIMIT 1",
            (school, program_name),
        ).fetchone()
        _conn.close()
        program_category = pc_row[0] if pc_row else "OTHER"
    else:
        program_category = "OTHER"

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
```

- [ ] **Step 5: Update server/main.py endpoints**

Replace the `/programs` and `/programs/{school}/{program}` endpoints:

```python
@app.get("/programs")
def get_programs(category: str = None):
    return list_programs(min_records=10, category=category)


@app.get("/programs/{school}/{program_name}")
def get_program_stats(school: str, program_name: str):
    result = program_stats(school, program_name)
    if isinstance(result, dict) and result.get("error"):
        return result
    return result
```

- [ ] **Step 6: Run API tests**

Run: `python3 -m pytest tests/test_cudo_api.py -v`
Expected: All 5 tests PASS

- [ ] **Step 7: Run all existing tests to check for regressions**

Run: `python3 -m pytest tests/ -v`
Expected: program_stats tests may need updates due to changed response shape. Update `tests/test_program_stats.py`:

```python
# tests/test_program_stats.py
import pytest
from core.recommend import program_stats, list_programs


def test_program_stats_returns_expected_shape():
    """program_stats returns grade buckets, ec breakdown, and key stats."""
    result = program_stats("UBC Vancouver", "Engineering")
    assert "grade_distribution" in result
    assert "ec_breakdown" in result
    assert "total_records" in result
    assert "data_tier" in result
    assert "program_name" in result


def test_program_stats_grade_distribution_has_buckets():
    """Grade distribution has bucket and pct/count fields."""
    result = program_stats("UBC Vancouver", "Engineering")
    dist = result["grade_distribution"]
    assert isinstance(dist, list)
    assert len(dist) > 0
    first = dist[0]
    assert "bucket" in first
    assert "pct" in first


def test_program_stats_ec_breakdown_has_percentages():
    """EC breakdown shows tag names with percentage of admitted students."""
    result = program_stats("UBC Vancouver", "Engineering")
    ec = result["ec_breakdown"]
    assert isinstance(ec, list)
    for entry in ec:
        assert "tag" in entry
        assert "pct" in entry
        assert 0 <= entry["pct"] <= 100


def test_program_stats_unknown_combo_returns_error():
    """Unknown school+program returns error."""
    result = program_stats("Fake University", "Fake Program")
    assert result.get("error") == "no_data"


def test_list_programs_returns_non_empty():
    """list_programs returns a list of programs with new fields."""
    result = list_programs()
    assert isinstance(result, list)
    assert len(result) > 0
    first = result[0]
    assert "school" in first
    assert "program_name" in first
    assert "program_category" in first
    assert "data_tier" in first


def test_list_programs_category_filter():
    """list_programs filters by category."""
    all_programs = list_programs()
    eng_programs = list_programs(category="ENGINEERING")
    assert len(eng_programs) <= len(all_programs)
    for p in eng_programs:
        assert p["program_category"] == "ENGINEERING"
```

- [ ] **Step 8: Run all tests**

Run: `python3 -m pytest tests/test_program_stats.py tests/test_cudo_api.py tests/test_submit.py -v`
Expected: All tests PASS

- [ ] **Step 9: Commit**

```bash
git add core/recommend.py server/main.py tests/test_cudo_api.py tests/test_program_stats.py
git commit -m "feat: merge CUDO and pipeline data in API layer"
```

---

### Task 7: Update TypeScript Types

**Files:**
- Modify: `frontend/lib/types.ts`

- [ ] **Step 1: Rewrite types.ts**

```typescript
// frontend/lib/types.ts

export interface ProgramSummary {
  school: string
  program_name: string
  program_category: string
  data_tier: 'official' | 'community' | 'both'
  total_records: number | null
  accepted: number | null
  overall_avg: number | null
}

export interface GradeBucket {
  bucket: string
  pct: number | null
  accepted: number | null
  rejected: number | null
  waitlisted: number | null
  deferred: number | null
}

export interface ECEntry {
  tag: string
  count: number
  pct: number
}

export interface ProgramStats {
  school: string
  program_name: string
  program_category: string
  data_tier: 'official' | 'community' | 'both'
  grade_distribution: GradeBucket[]
  ec_breakdown: ECEntry[]
  overall_avg: number | null
  historical: { year: number; overall_avg: number }[]
  total_records: number | null
  accepted_count: number | null
  avg_admitted_grade: number | null
  grade_range: { min: number; max: number } | null
  data_sources: Record<string, number>
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/types.ts
git commit -m "refactor: update TypeScript types for CUDO integration"
```

---

### Task 8: Update ProgramCard Component

**Files:**
- Modify: `frontend/components/ProgramCard.tsx`

- [ ] **Step 1: Rewrite ProgramCard.tsx**

```tsx
// frontend/components/ProgramCard.tsx
import Link from 'next/link'

interface Props {
  school: string
  programName: string
  programCategory: string
  dataTier: 'official' | 'community' | 'both'
  totalRecords: number | null
  accepted: number | null
  overallAvg: number | null
}

const TIER_BADGE: Record<string, { label: string; color: string }> = {
  official: { label: 'Official', color: 'bg-emerald-500/20 text-emerald-400' },
  community: { label: 'Community', color: 'bg-blue-500/20 text-blue-400' },
  both: { label: 'Official + Community', color: 'bg-purple-500/20 text-purple-400' },
}

export default function ProgramCard({
  school,
  programName,
  programCategory,
  dataTier,
  totalRecords,
  accepted,
  overallAvg,
}: Props) {
  const slug = `${encodeURIComponent(school)}/${encodeURIComponent(programName)}`
  const badge = TIER_BADGE[dataTier]

  return (
    <Link
      href={`/program/${slug}`}
      className="block p-5 rounded-xl border border-white/10 bg-white/[0.03]
                 hover:bg-white/[0.06] hover:border-white/20 transition-all duration-200"
    >
      <div className="flex items-start justify-between mb-1">
        <p className="text-xs text-white/40 uppercase tracking-wide">{school}</p>
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${badge.color}`}>
          {badge.label}
        </span>
      </div>
      <h3 className="text-lg font-medium text-[#f5f5f0] mb-3">{programName}</h3>
      <div className="flex items-center gap-4 text-sm text-white/50">
        {overallAvg != null && <span>Avg: {overallAvg}%</span>}
        {totalRecords != null && <span>{totalRecords} records</span>}
        {totalRecords != null && accepted != null && totalRecords > 0 && (
          <span>{Math.round((accepted / totalRecords) * 100)}% accepted</span>
        )}
      </div>
    </Link>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/ProgramCard.tsx
git commit -m "refactor: update ProgramCard for CUDO integration"
```

---

### Task 9: Update GradeDistribution Component (percentage mode)

**Files:**
- Modify: `frontend/components/GradeDistribution.tsx`

- [ ] **Step 1: Rewrite GradeDistribution.tsx with dual mode**

```tsx
// frontend/components/GradeDistribution.tsx
'use client'

import { GradeBucket } from '@/lib/types'

interface Props {
  buckets: GradeBucket[]
}

const COLORS = {
  accepted: '#22c55e',
  rejected: '#ef4444',
  waitlisted: '#f59e0b',
  deferred: '#8b5cf6',
}

export default function GradeDistribution({ buckets }: Props) {
  // Determine mode: if first bucket has pct, use percentage mode
  const isPercentMode = buckets.length > 0 && buckets[0].pct != null

  if (isPercentMode) {
    const maxPct = Math.max(...buckets.map(b => b.pct ?? 0), 1)

    return (
      <div>
        <h2 className="text-lg font-medium text-[#f5f5f0] mb-4">Grade Distribution</h2>
        <div className="space-y-3">
          {buckets.map((bucket) => {
            const pct = bucket.pct ?? 0
            if (pct === 0) return null
            return (
              <div key={bucket.bucket} className="flex items-center gap-3">
                <span className="text-sm text-white/50 w-16 text-right shrink-0">
                  {bucket.bucket}
                </span>
                <div className="flex-1 h-7">
                  <div
                    className="h-full rounded-sm flex items-center justify-center text-xs font-medium"
                    style={{
                      width: `${(pct / maxPct) * 100}%`,
                      minWidth: '24px',
                      backgroundColor: '#3b82f6',
                    }}
                  >
                    {pct}%
                  </div>
                </div>
              </div>
            )
          })}
        </div>
        <p className="text-xs text-white/20 mt-3">% of admitted students in each grade range</p>
      </div>
    )
  }

  // Count mode (existing behavior)
  const maxCount = Math.max(
    ...buckets.flatMap(b => [b.accepted ?? 0, b.rejected ?? 0, b.waitlisted ?? 0, b.deferred ?? 0]),
    1
  )

  return (
    <div>
      <h2 className="text-lg font-medium text-[#f5f5f0] mb-4">Grade Distribution</h2>
      <div className="space-y-3">
        {buckets.map((bucket) => {
          const total = (bucket.accepted ?? 0) + (bucket.rejected ?? 0) + (bucket.waitlisted ?? 0) + (bucket.deferred ?? 0)
          if (total === 0) return null
          return (
            <div key={bucket.bucket} className="flex items-center gap-3">
              <span className="text-sm text-white/50 w-16 text-right shrink-0">
                {bucket.bucket}
              </span>
              <div className="flex-1 flex gap-0.5 h-7">
                {(['accepted', 'rejected', 'waitlisted', 'deferred'] as const).map((decision) => {
                  const count = bucket[decision] ?? 0
                  if (count === 0) return null
                  const widthPct = (count / maxCount) * 100
                  return (
                    <div
                      key={decision}
                      className="h-full rounded-sm flex items-center justify-center text-xs font-medium"
                      style={{
                        width: `${widthPct}%`,
                        minWidth: count > 0 ? '20px' : '0',
                        backgroundColor: COLORS[decision],
                      }}
                    >
                      {count > 0 && count}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
      <div className="flex gap-4 mt-4 text-xs text-white/40">
        {Object.entries(COLORS).map(([label, color]) => (
          <div key={label} className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: color }} />
            <span className="capitalize">{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/GradeDistribution.tsx
git commit -m "feat: add percentage mode to GradeDistribution component"
```

---

### Task 10: Update Home Page with Category Filter

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Rewrite page.tsx**

```tsx
// frontend/app/page.tsx
import ProgramCard from '@/components/ProgramCard'
import CategoryFilter from '@/components/CategoryFilter'
import { ProgramSummary } from '@/lib/types'

const API_URL = process.env.PYTHON_API_URL ?? 'http://localhost:8000'

async function getPrograms(category?: string): Promise<ProgramSummary[]> {
  try {
    const url = category
      ? `${API_URL}/programs?category=${encodeURIComponent(category)}`
      : `${API_URL}/programs`
    const res = await fetch(url, { cache: 'no-store' })
    if (!res.ok) return []
    return res.json()
  } catch {
    return []
  }
}

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ category?: string }>
}) {
  const { category } = await searchParams
  const programs = await getPrograms(category)

  return (
    <div className="min-h-screen flex flex-col bg-[#0a0a0a]">
      <div className="flex-1 px-4 pt-16 pb-16 max-w-4xl mx-auto w-full">
        <div className="mb-10">
          <h1 className="font-display text-3xl text-[#f5f5f0] leading-tight">
            See what it actually takes.
          </h1>
          <p className="mt-2 text-sm text-[#f5f5f0]/45">
            Grade distributions and EC patterns from real Canadian applicants.
          </p>
        </div>

        <CategoryFilter active={category ?? null} />

        {programs.length === 0 ? (
          <p className="text-white/40 mt-6">No program data available for this filter.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-6">
            {programs.map((p) => (
              <ProgramCard
                key={`${p.school}|${p.program_name}`}
                school={p.school}
                programName={p.program_name}
                programCategory={p.program_category}
                dataTier={p.data_tier}
                totalRecords={p.total_records}
                accepted={p.accepted}
                overallAvg={p.overall_avg}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create CategoryFilter component**

```tsx
// frontend/components/CategoryFilter.tsx
'use client'

import { useRouter } from 'next/navigation'

const CATEGORIES = [
  { key: null, label: 'All' },
  { key: 'ENGINEERING', label: 'Engineering' },
  { key: 'SCIENCE', label: 'Science' },
  { key: 'BUSINESS', label: 'Business' },
  { key: 'COMPUTER_SCIENCE', label: 'Computer Science' },
  { key: 'HEALTH', label: 'Health' },
  { key: 'ARTS', label: 'Arts' },
]

interface Props {
  active: string | null
}

export default function CategoryFilter({ active }: Props) {
  const router = useRouter()

  return (
    <div className="flex flex-wrap gap-2">
      {CATEGORIES.map(({ key, label }) => {
        const isActive = active === key
        return (
          <button
            key={label}
            onClick={() => {
              const url = key ? `/?category=${key}` : '/'
              router.push(url)
            }}
            className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
              isActive
                ? 'bg-white/15 text-[#f5f5f0] border border-white/20'
                : 'bg-white/[0.03] text-white/40 border border-white/10 hover:text-white/60 hover:border-white/15'
            }`}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/page.tsx frontend/components/CategoryFilter.tsx
git commit -m "feat: add category filter bar to browse page"
```

---

### Task 11: Update Program Detail Page

**Files:**
- Modify: `frontend/app/program/[school]/[program]/page.tsx`

- [ ] **Step 1: Rewrite the program detail page**

```tsx
// frontend/app/program/[school]/[program]/page.tsx
import GradeDistribution from '@/components/GradeDistribution'
import ECBreakdown from '@/components/ECBreakdown'
import WhereDoYouStand from '@/components/WhereDoYouStand'
import SubmitOutcomeForm from '@/components/SubmitOutcomeForm'
import HistoricalTrends from '@/components/HistoricalTrends'
import Link from 'next/link'
import { ProgramStats } from '@/lib/types'

const API_URL = process.env.PYTHON_API_URL ?? 'http://localhost:8000'

async function getStats(school: string, programName: string): Promise<ProgramStats | null> {
  try {
    const res = await fetch(
      `${API_URL}/programs/${encodeURIComponent(school)}/${encodeURIComponent(programName)}`,
      { cache: 'no-store' }
    )
    if (!res.ok) return null
    const data = await res.json()
    if (data.error) return null
    return data
  } catch {
    return null
  }
}

export default async function ProgramPage({
  params,
}: {
  params: Promise<{ school: string; program: string }>
}) {
  const { school: rawSchool, program: rawProgram } = await params
  const school = decodeURIComponent(rawSchool)
  const programName = decodeURIComponent(rawProgram)
  const stats = await getStats(school, programName)

  if (!stats) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-[#0a0a0a] px-4">
        <p className="text-white/40 mb-4">No data available for this program.</p>
        <Link href="/" className="text-[#3b82f6] hover:underline text-sm">
          Back to browse
        </Link>
      </div>
    )
  }

  const sourceLabel = Object.entries(stats.data_sources)
    .map(([src, count]) => {
      if (src === 'CUDO_OFFICIAL') return `Official university data (CUDO)`
      if (src === 'REDDIT_SCRAPED') return `${count} Reddit posts`
      if (src === 'USER_SUBMITTED') return `${count} submissions`
      return `${count} ${src} records`
    })
    .join(' + ')

  const tierLabel = stats.data_tier === 'official'
    ? 'Official university data'
    : stats.data_tier === 'both'
    ? 'Official + community data'
    : 'Community-reported data'

  return (
    <div className="min-h-screen flex flex-col bg-[#0a0a0a]">
      <div className="flex-1 px-4 pt-12 pb-16 max-w-3xl mx-auto w-full">
        {/* Back link */}
        <Link href="/" className="text-sm text-white/30 hover:text-white/50 transition-colors">
          &larr; All programs
        </Link>

        {/* Header */}
        <div className="mt-6 mb-10">
          <div className="flex items-center gap-3 mb-1">
            <p className="text-xs text-white/40 uppercase tracking-wide">{school}</p>
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
              stats.data_tier === 'official' ? 'bg-emerald-500/20 text-emerald-400' :
              stats.data_tier === 'both' ? 'bg-purple-500/20 text-purple-400' :
              'bg-blue-500/20 text-blue-400'
            }`}>
              {tierLabel}
            </span>
          </div>
          <h1 className="font-display text-3xl text-[#f5f5f0]">{programName}</h1>
        </div>

        {/* Key stats */}
        <div className="grid grid-cols-3 gap-4 mb-10">
          {stats.overall_avg != null && (
            <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03]">
              <p className="text-2xl font-medium text-[#f5f5f0]">{stats.overall_avg}%</p>
              <p className="text-xs text-white/40 mt-1">Avg admitted grade</p>
            </div>
          )}
          {stats.total_records != null && (
            <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03]">
              <p className="text-2xl font-medium text-[#f5f5f0]">{stats.total_records}</p>
              <p className="text-xs text-white/40 mt-1">Community records</p>
            </div>
          )}
          {stats.grade_range && (
            <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03]">
              <p className="text-2xl font-medium text-[#f5f5f0]">
                {stats.grade_range.min}–{stats.grade_range.max}%
              </p>
              <p className="text-xs text-white/40 mt-1">Admitted range</p>
            </div>
          )}
        </div>

        {/* Grade distribution */}
        <div className="mb-10 p-6 rounded-xl border border-white/10 bg-white/[0.03]">
          <GradeDistribution buckets={stats.grade_distribution} />
        </div>

        {/* Historical trends */}
        {stats.historical.length >= 2 && (
          <div className="mb-10">
            <HistoricalTrends data={stats.historical} />
          </div>
        )}

        {/* EC breakdown */}
        {stats.ec_breakdown.length > 0 && stats.accepted_count != null && (
          <div className="mb-10 p-6 rounded-xl border border-white/10 bg-white/[0.03]">
            <ECBreakdown entries={stats.ec_breakdown} acceptedCount={stats.accepted_count} />
          </div>
        )}

        {/* EC not available note for CUDO-only */}
        {stats.data_tier === 'official' && (
          <div className="mb-10 p-6 rounded-xl border border-white/10 bg-white/[0.03]">
            <p className="text-sm text-white/30">
              Community insights (extracurriculars, circumstances) are not yet available for this program.
              Submit your outcome below to contribute.
            </p>
          </div>
        )}

        {/* Where Do You Stand */}
        <div className="mb-10">
          <WhereDoYouStand
            avgAdmittedGrade={stats.overall_avg ?? stats.avg_admitted_grade}
            gradeRange={stats.grade_range}
            totalRecords={stats.total_records ?? 0}
          />
        </div>

        {/* Submit form */}
        <div className="mb-10 p-6 rounded-xl border border-white/10 bg-white/[0.03]">
          <SubmitOutcomeForm defaultSchool={school} defaultProgram={programName} />
        </div>

        {/* Data provenance */}
        <div className="text-xs text-white/20 text-center mt-8">
          {sourceLabel}
          {stats.total_records != null && stats.total_records < 20 && stats.data_tier !== 'official' && (
            <span className="block mt-1 text-yellow-500/50">
              Limited community data — take insights with a grain of salt
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/program/[school]/[program]/page.tsx
git commit -m "feat: update program page for merged CUDO/pipeline data"
```

---

### Task 12: Historical Trends Component

**Files:**
- Create: `frontend/components/HistoricalTrends.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/components/HistoricalTrends.tsx
'use client'

import { useState } from 'react'

interface Props {
  data: { year: number; overall_avg: number }[]
}

export default function HistoricalTrends({ data }: Props) {
  const [open, setOpen] = useState(false)

  if (data.length < 2) return null

  const minAvg = Math.min(...data.map(d => d.overall_avg))
  const maxAvg = Math.max(...data.map(d => d.overall_avg))
  const range = maxAvg - minAvg || 1

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-white/[0.02] transition-colors"
      >
        <span className="text-sm font-medium text-[#f5f5f0]">Historical Trends</span>
        <span className="text-white/30 text-lg">{open ? '−' : '+'}</span>
      </button>

      {open && (
        <div className="px-6 pb-6 pt-2">
          <p className="text-xs text-white/30 mb-4">
            Average admitted grade by year (CUDO official data)
          </p>
          <div className="space-y-2">
            {data.map((d) => {
              const pct = ((d.overall_avg - (minAvg - 2)) / (range + 4)) * 100
              return (
                <div key={d.year} className="flex items-center gap-3">
                  <span className="text-sm text-white/50 w-12 text-right shrink-0">
                    {d.year}
                  </span>
                  <div className="flex-1 h-6 bg-white/[0.03] rounded-sm overflow-hidden">
                    <div
                      className="h-full bg-emerald-500/50 rounded-sm flex items-center px-2"
                      style={{ width: `${Math.max(pct, 10)}%` }}
                    >
                      <span className="text-xs font-medium text-white/90">
                        {d.overall_avg}%
                      </span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/HistoricalTrends.tsx
git commit -m "feat: add HistoricalTrends collapsible component"
```

---

### Task 13: Build and Verify Frontend

**Files:** None new — verification step

- [ ] **Step 1: Build the frontend**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 2: Fix any build errors**

If there are TypeScript errors, fix them. Common issues:
- Old references to `p.program` should be `p.program_name`
- Old references to `stats.total_records === 0` check — now `stats` could be null or have `error`

- [ ] **Step 3: Run the full stack and verify**

```bash
# Terminal 1: Backend
python3 -m uvicorn server.main:app --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
```

Open `http://localhost:3000` and verify:
- Browse page shows category filter chips
- Program cards show data tier badges (Official/Community/Both)
- CUDO programs show overall avg
- Pipeline programs show record count + acceptance rate
- Clicking a card goes to the correct program page
- Grade distribution renders in percentage mode for CUDO data
- Grade distribution renders in count mode for pipeline data
- Historical trends section appears for CUDO programs with multi-year data
- EC breakdown shows for programs with pipeline data
- CUDO-only programs show "Community insights not yet available" note

- [ ] **Step 4: Run all tests**

```bash
python3 -m pytest tests/ -v
```

Expected: All tests pass (may have 2 pre-existing failures in test_calibration.py — those are unrelated).

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve build and integration issues"
```

---

## Self-Review

**Spec coverage check:**

| Spec Section | Task |
|---|---|
| `cudo_programs` table | Task 2 |
| `program_normalized` column on Student | Task 2 |
| Program name normalization | Task 1 |
| CUDO scraper (HTML only, 5-8 universities) | Task 4 |
| Backfill `program_normalized` | Task 3 |
| Grade bucket alignment (5→7) | Task 5 |
| API re-keyed to `program_name` | Task 6 |
| API merge layer | Task 6 |
| Category filter on browse page | Task 10 |
| Percentage/count display modes | Task 9 |
| Data tier badges | Tasks 8, 11 |
| Historical trends | Task 12 |
| Updated TypeScript types | Task 7 |
| Frontend build verification | Task 13 |

**Placeholder scan:** No TBDs, TODOs, or vague instructions found.

**Type consistency:**
- `program_name` used consistently across API, types, and components
- `data_tier` enum `"official" | "community" | "both"` consistent everywhere
- `GradeBucket.pct` field present in type, API response, and component
- `ProgramSummary` has `program_name`, `program_category`, `data_tier`, `overall_avg` — all referenced correctly in ProgramCard props
