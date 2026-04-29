# CUDO Data Integration — Design Spec

**Date:** 2026-04-28
**Status:** Approved
**Author:** jshum + Claude

## Problem

UniPath AI has 478 records, almost all from BC-focused Google Sheets. Ontario coverage is thin (41 Reddit-scraped rows). Meanwhile, Ontario universities publish official admission grade distributions through CUDO (Common University Data Ontario) — free, public, aggregate data covering hundreds of programs across ~20 universities, with multi-year historical data. We're leaving this on the table.

## Solution

Integrate CUDO as a second data source. Store it in its own table (it's aggregate data, not individual records). Merge it with our existing pipeline data at the API layer. Re-key program pages from broad categories (ENGINEERING, SCIENCE) to specific program names (Mechanical Engineering, Life Sciences). Use `program_category` as a filter mechanism instead.

## What This Changes

| Before | After |
|--------|-------|
| ~10 program cards (broad categories, min 10 records) | 200-400+ program cards (specific programs) |
| BC-heavy data only | BC pipeline + Ontario official CUDO data |
| Program pages keyed on `program_category` | Program pages keyed on `program_name` |
| Grade distribution from individual records only | Official percentage distributions (CUDO) + individual record counts (pipeline) |
| No historical trends | Year-over-year admission average trends (CUDO) |

## Architecture

```
CUDO university websites ──> cudo_scraper.py ──> Parse HTML tables ──> cudo_programs table
                                                                            |
Reddit posts ──> reddit_agent.py ──> LLM extract ──> students table ────────┤
                                                                            |
User submissions ──> /submit-outcome ──> students table ────────────────────┤
                                                                            |
                                              program_names.py (normalization)
                                                          |
                                                    API merge layer
                                                          |
                                                   Next.js frontend
                                              (Program Intelligence Pages)
```

## Data Model

### New table: `cudo_programs`

| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | Auto-increment |
| school | String, not null | Normalized school name (e.g., "University of Windsor") |
| program_name | String, not null | Canonical program name after normalization |
| program_category | String, not null | Broad category (ENGINEERING, SCIENCE, etc.) |
| year | Integer, not null | Admission year (e.g., 2023) |
| pct_95_plus | Float | % of admitted students with 95%+ average |
| pct_90_94 | Float | % with 90-94% |
| pct_85_89 | Float | % with 85-89% |
| pct_80_84 | Float | % with 80-84% |
| pct_75_79 | Float | % with 75-79% |
| pct_70_74 | Float | % with 70-74% |
| pct_below_70 | Float | % below 70% |
| overall_avg | Float | Overall admission average for the program |
| source_url | String | URL where data was scraped from (provenance) |

**Unique constraint:** `(school, program_name, year)` — one row per program per year per school.

### Existing `students` table — one new column

- `program_normalized` (String, nullable) — canonical program name derived from `program_raw` via the normalization map. This is what links pipeline records to CUDO programs.

All existing columns remain unchanged.

## Program Name Normalization

New file: `pipeline/program_names.py`

A simple dict mapping variant names to canonical program names. Used by:
- CUDO scraper: normalizes CUDO `program_name` before insert
- Pipeline: populates `program_normalized` on student records
- API: queries both tables using canonical names

```python
PROGRAM_NAME_MAP = {
    # CUDO names → canonical
    "Computer & Information Science": "Computer Science",
    "Commerce/Management/Business Admin": "Commerce",
    "Biological & Biomedical Sciences": "Biological Sciences",
    "Health Profession & Related Programs": "Health Sciences",
    "Kinesiology/Recreation/Physical Education": "Kinesiology",
    "Fine & Applied Arts": "Fine Arts",
    "Liberal Arts & Sciences/General Studies": "Arts",
    "Mathematics & Statistics": "Mathematics",
    "Physical Science": "Physical Sciences",

    # Pipeline program_raw variants → canonical
    "CompSci": "Computer Science",
    "CS": "Computer Science",
    "Life Sci": "Life Sciences",
    "Sauder": "Commerce",
    "BComm": "Commerce",
    "Ivey AEO": "Business Administration",
    "Health Sci": "Health Sciences",
    "Biomed": "Biomedical Sciences",
    "Kin": "Kinesiology",
}

PROGRAM_CATEGORY_MAP = {
    "Computer Science": "COMPUTER_SCIENCE",
    "Commerce": "BUSINESS",
    "Engineering": "ENGINEERING",
    "Life Sciences": "SCIENCE",
    "Biological Sciences": "SCIENCE",
    "Health Sciences": "HEALTH",
    "Nursing": "HEALTH",
    "Kinesiology": "HEALTH",
    "Arts": "ARTS",
    "Psychology": "ARTS",
    "Mathematics": "SCIENCE",
    "Physical Sciences": "SCIENCE",
    "Fine Arts": "ARTS",
    "Education": "EDUCATION",
    "Business Administration": "BUSINESS",
    "Science": "SCIENCE",
    "Social Sciences": "ARTS",
}
```

This is intentionally a simple dict — no fuzzy matching. New entries are added as new variants are encountered. If a name isn't in the map, it passes through as-is.

**Backfill:** A one-time migration script populates `program_normalized` on all existing student records from their `program_raw` values using this map.

## CUDO Scraper

File: `pipeline/cudo_scraper.py`

### Target universities (v1 — HTML tables only)

Confirmed scrapable:
- University of Windsor
- Ontario Tech University

Discovery needed (probe during implementation):
- York University
- Brock University
- Trent University
- University of Guelph
- University of Ottawa
- Wilfrid Laurier University

Target: 5-8 universities with accessible HTML B3 tables.

### Scraper design

- Config dict mapping each university to its CUDO URL pattern and any university-specific parsing quirks
- For each university:
  1. Fetch the B3 admission page (HTML)
  2. Parse the HTML table — extract program name, grade range percentages, overall average
  3. Normalize program name via `PROGRAM_NAME_MAP`
  4. Assign `program_category` via `PROGRAM_CATEGORY_MAP`
  5. Insert into `cudo_programs` table
- Idempotent: re-running deletes that university's existing data before reinserting (same pattern as `load_to_db.py`)
- Rate-limited: 2-second delay between HTTP requests
- Scrapes multiple years if the university provides links to historical CUDO reports
- Prints summary per university: "Windsor: 15 programs × 3 years = 45 records loaded"

### PDF fallback (deferred)

Universities that only provide CUDO data as PDFs are not scraped automatically. If coverage is needed for a PDF-only university, the data is manually extracted from the PDF into a CSV and loaded via a simple CSV import script. This is the fallback path — not part of the initial build.

## API Changes

### `GET /programs`

Returns the union of both data sources, deduplicated by `(school, program_name)`.

Response shape per item:
```json
{
  "school": "University of Windsor",
  "program_name": "Engineering",
  "program_category": "ENGINEERING",
  "data_tier": "official",
  "total_records": null,
  "overall_avg": 87.4
}
```

- `data_tier`: `"official"` (CUDO only), `"community"` (pipeline only), `"both"` (matched data in both tables)
- `total_records`: count of pipeline student records (null if CUDO only)
- `overall_avg`: from CUDO's most recent year (null if pipeline only)
- Accepts optional query param: `?category=ENGINEERING` to filter by `program_category`
- No minimum record threshold for CUDO programs
- Pipeline-only programs keep the `min_records=10` threshold

### `GET /programs/{school}/{program_name}`

Response merges both sources:
```json
{
  "school": "University of Windsor",
  "program_name": "Engineering",
  "program_category": "ENGINEERING",
  "data_tier": "both",
  "grade_distribution": [
    {"bucket": "95-100", "pct": 12.7, "accepted": null, "rejected": null, "waitlisted": null, "deferred": null}
  ],
  "ec_breakdown": [
    {"tag": "SPORTS", "count": 5, "pct": 45}
  ],
  "overall_avg": 87.4,
  "historical": [
    {"year": 2021, "overall_avg": 85.2},
    {"year": 2022, "overall_avg": 86.8},
    {"year": 2023, "overall_avg": 87.4}
  ],
  "total_records": 12,
  "accepted_count": 10,
  "avg_admitted_grade": 88.1,
  "grade_range": {"min": 82.0, "max": 95.5},
  "data_sources": {"CUDO_OFFICIAL": 1, "REDDIT_SCRAPED": 8, "BC": 4}
}
```

**Merge rules:**
- `grade_distribution`: CUDO percentages if available (larger N, official data). Falls back to pipeline record counts if CUDO not available. When CUDO provides percentages, the `accepted`/`rejected`/`waitlisted`/`deferred` fields are null (CUDO data is all admitted students, no decision breakdown).
- `ec_breakdown`: Pipeline data only. Shown when matching pipeline records exist. Empty array if CUDO-only program.
- `historical`: Array of `{year, overall_avg}` from CUDO across available years. Empty array if pipeline-only.
- `overall_avg`: From CUDO most recent year if available, otherwise computed from pipeline accepted records.
- `total_records`, `accepted_count`, `avg_admitted_grade`, `grade_range`: From pipeline records only. Null if CUDO-only.

### URL change

Routes change from `/programs/{school}/{program_category}` to `/programs/{school}/{program_name}`. This is a breaking change — no backwards compatibility needed since there are no external consumers.

## Frontend Changes

### Browse page (`/`)

- **Category filter bar** at the top: chips/buttons for "All", "Engineering", "Science", "Business", "Computer Science", "Health", "Arts". Sends `?category=X` to the API.
- **Program cards** show `program_name` (e.g., "Computer Science") instead of `program_category` (e.g., "COMPUTER_SCIENCE").
- **Data tier badge** on each card:
  - "Official" (green) — CUDO data available
  - "Community" (blue) — pipeline data only
  - "Both" — both sources available (most valuable)
- Cards with CUDO data show `overall_avg`. Cards with pipeline data show record count + acceptance rate.
- Cards link to `/program/{school}/{program_name}` (URL-encoded).

### Program detail page (`/program/[school]/[program]`)

- **Grade distribution component** gains a `mode` prop:
  - `"percentage"` mode (CUDO): bars show percentage labels (e.g., "12.7%"), no decision-type stacking (all admitted students)
  - `"count"` mode (pipeline): existing stacked bars with accepted/rejected/waitlisted/deferred counts
- **Data source note** below grade chart:
  - CUDO: "Official university data (CUDO {year})"
  - Pipeline: "Based on {N} community-reported outcomes"
- **EC breakdown** section: shown only when pipeline data exists for this program. Hidden for CUDO-only programs with a note: "Community insights not yet available for this program. Submit your outcome to contribute."
- **Historical Trends** section: new collapsible section below grade distribution. Shows a simple bar or line chart of `overall_avg` by year. Only shown if `historical` array has 2+ entries. CUDO-only feature.
- **Data provenance footer** updated to show "Official university data (CUDO)" alongside community source counts.

### No changes needed

- **WhereDoYouStand**: Already uses `overall_avg` which both sources provide.
- **SubmitOutcomeForm**: Still works the same. Pre-fills school and program from page context.

## TypeScript Types (updated)

```typescript
interface ProgramSummary {
  school: string
  program_name: string
  program_category: string
  data_tier: "official" | "community" | "both"
  total_records: number | null
  overall_avg: number | null
}

interface GradeBucket {
  bucket: string
  pct: number | null          // percentage (CUDO mode)
  accepted: number | null     // count (pipeline mode)
  rejected: number | null
  waitlisted: number | null
  deferred: number | null
}

interface ProgramStats {
  school: string
  program_name: string
  program_category: string
  data_tier: "official" | "community" | "both"
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

`ECEntry` remains unchanged: `{ tag: string, count: number, pct: number }`.

## Grade Bucket Alignment

CUDO uses 7 buckets: `95%+`, `90-94%`, `85-89%`, `80-84%`, `75-79%`, `70-74%`, `<70%`.

Our current pipeline uses 5 buckets: `< 80`, `80-84`, `85-89`, `90-94`, `95-100`.

**Decision:** Adopt CUDO's 7-bucket system as the standard. The pipeline's grade distribution computation is updated to use 7 buckets. This is more granular and aligns with the official data format. The `< 80` bucket splits into `75-79`, `70-74`, and `< 70`.

## Scope

### In scope (v1)
- `cudo_programs` table and ORM model
- Program name normalization layer (`program_names.py`)
- CUDO HTML scraper for 5-8 Ontario universities
- Backfill `program_normalized` on existing student records
- API re-keyed to `program_name`, merge layer for both data sources
- Frontend: category filter, percentage/count display modes, data tier badges, historical trends
- Grade bucket alignment (5 → 7 buckets)

### Out of scope
- PDF scraping (fallback to manual CSV curation)
- BC equivalent data source
- Fuzzy program name matching
- Search/autocomplete on browse page
- Year selector on program pages (shows most recent, expandable history)

## Success Criteria

1. At least 5 Ontario universities with CUDO data loaded (100+ new program-year combos)
2. Program pages correctly merge CUDO grade distributions with pipeline EC breakdowns where both exist
3. Browse page has working category filter
4. Historical trends shown for programs with multi-year CUDO data
5. Data provenance clearly distinguishes official vs community data
6. No regression in existing pipeline data display
