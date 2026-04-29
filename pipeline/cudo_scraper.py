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
# Windsor uses vertical-format tables (one per program), each preceded by a <strong> tag.
UNIVERSITY_CONFIGS = {
    "University of Windsor": [
        (2023, "https://www.uwindsor.ca/common-university-data-ontario/421/b-admission-2023"),
        (2022, "https://www.uwindsor.ca/institutional-analysis/370/b-admission-2022"),
        (2021, "https://www.uwindsor.ca/common-university-data-ontario/395/b-admission-2021"),
        (2020, "https://www.uwindsor.ca/common-university-data-ontario/385/b-admission-2020"),
    ],
}

# Rows in Windsor's vertical table, in order
_WINDSOR_ROW_LABELS = [
    "95%+",
    "between 90% and 94%",
    "between 85% and 89%",
    "between 80% and 84%",
    "between 75% and 79%",
    "between 70% and 74%",
    "below 70%",
    "overall average",
]


def _parse_pct(cell: str) -> float | None:
    """Parse a percentage cell value. Returns None for suppressed or missing values."""
    cell = cell.replace("%", "").strip()
    if cell in ("*", "", "N/A", "-", "n/a"):
        return None
    try:
        return float(cell)
    except ValueError:
        return None


def _is_windsor_grade_table(table) -> bool:
    """Return True if this table is a Windsor-style vertical grade distribution table."""
    rows = table.find_all("tr")
    if len(rows) < 2:
        return False
    # Header row must have exactly 2 columns: "Entering Average" and "% of Students"
    header_cells = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
    return (
        len(header_cells) == 2
        and "entering average" in header_cells[0]
        and "%" in header_cells[1]
    )


def parse_cudo_b3_table(html: str, school: str, year: int) -> list[dict]:
    """Parse a CUDO B3 HTML page into a list of program dicts.

    Supports Windsor's vertical table format where each program has its own
    9-row table (header + 7 grade rows + overall average), preceded by a
    <strong> tag containing the program name.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    tables = soup.find_all("table")

    for table in tables:
        if not _is_windsor_grade_table(table):
            continue

        # Find the program name from the preceding <strong> tag
        prev_strong = table.find_previous("strong")
        if not prev_strong:
            continue

        program_raw = prev_strong.get_text(strip=True)

        # Skip totals/overall rows
        if any(
            skip in program_raw.lower()
            for skip in ["total", "overall", "university of"]
        ):
            continue
        if not program_raw:
            continue

        # Parse grade rows
        rows = table.find_all("tr")
        # Build a label → value dict for robustness against row order differences
        row_data = {}
        for row in rows[1:]:  # skip header
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if len(cells) == 2:
                label = cells[0].strip().lower()
                row_data[label] = _parse_pct(cells[1])

        # Map label patterns to fields
        pct_95_plus = row_data.get("95%+")
        pct_90_94 = row_data.get("between 90% and 94%")
        pct_85_89 = row_data.get("between 85% and 89%")
        pct_80_84 = row_data.get("between 80% and 84%")
        pct_75_79 = row_data.get("between 75% and 79%")
        pct_70_74 = row_data.get("between 70% and 74%")
        pct_below_70 = row_data.get("below 70%")
        overall_avg = row_data.get("overall average")

        program_name = normalize_program_name(program_raw)
        program_category = get_program_category(program_name)

        results.append(
            {
                "school": school,
                "program_name": program_name,
                "program_category": program_category,
                "year": year,
                "pct_95_plus": pct_95_plus,
                "pct_90_94": pct_90_94,
                "pct_85_89": pct_85_89,
                "pct_80_84": pct_80_84,
                "pct_75_79": pct_75_79,
                "pct_70_74": pct_70_74,
                "pct_below_70": pct_below_70,
                "overall_avg": overall_avg,
            }
        )

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
    """Load parsed CUDO records into the database. Idempotent."""
    with Session(engine) as session:
        deleted = (
            session.query(CudoProgram).filter(CudoProgram.school == school).delete()
        )
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
