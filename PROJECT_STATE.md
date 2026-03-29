# UniPath AI — Project State
Last updated: March 2026

---

## What It Is
University outcomes tool for Canadian high school students.
Students input grades + program + target schools and see how similar
students actually performed — with a calibrated acceptance likelihood
percentage anchored to published university acceptance rates.

Core differentiator: real student submission data, not synthetic or
generic LLM advice.

---

## Current Status
- Stage 1 (ETL pipeline): COMPLETE
- Stage 2 (recommendation engine): COMPLETE
- Reddit scraping agent: COMPLETE (414 rows, re-run after tag_program fix)
- Program category fix (tag_program): COMPLETE
- Calibration layer (calibrate.py + ec_scorer.py): COMPLETE
- app.py wired to final_probability(): NOT STARTED
- Next.js frontend: PLANNED, not started

---

## Architecture

### Data Flow
```
Google Sheets (live) → fetch_sheets.py → data/processed/
data/processed/ → normalize.py → data/cleaned/bc_cleaned.csv
data/cleaned/ → extract_fields.py → data/cleaned/bc_extracted.csv
data/cleaned/ → load_to_db.py → database/unipath.db
Reddit JSON API → reddit_agent.py → database/unipath.db (direct)
database/unipath.db → recommend.py → recommendation output
calibrate.py + ec_scorer.py → final_probability() → display_percent
```

### Key Files
- `main.py` — runs full pipeline end to end (fetch → normalize → extract → load)
- `pipeline/fetch_sheets.py` — pulls BC 2026 and BC 2025 sheets via public CSV URLs
- `pipeline/normalize.py` — grade parsing, school normalization, decision normalization
- `pipeline/extract_fields.py` — NLP keyword tagging for EC, circumstances, program
- `pipeline/load_to_db.py` — loads cleaned CSV to SQLite, idempotent per source
- `pipeline/reddit_agent.py` — standalone agent, run separately from main.py
- `database/models.py` — SQLAlchemy ORM schema
- `recommend.py` — lookup_school() and discover_schools() with auto-tolerance widening
- `calibrate.py` — calibrated_probability() and final_probability(); all probability math
- `ec_scorer.py` — score_profile() for EC and supplemental scoring via Ollama
- `tools/research_profiles.py` — standalone draft tool for ADMITTED_PROFILES research
- `app.py` — Streamlit prototype (not yet wired to final_probability)
- `tests/test_calibration.py` — 30 pytest tests for calibration layer (all passing)

### Database
- Path: database/unipath.db
- Table: students
- Sources: BC (181 rows), BC_2025 (218 rows), REDDIT_SCRAPED (415 rows)
- Total: 814 rows

### Key Constants
- DEFAULT_TOLERANCE = 2.0 (auto-widens to max 10.0)
- MIN_RESULTS = 10 (threshold for tolerance widening)
- REDDIT sources: r/OntarioGrade12s, r/BCGrade12s
- Program categories: ENGINEERING, SCIENCE, BUSINESS, ARTS,
  COMPUTER_SCIENCE, HEALTH, LAW, EDUCATION, OTHER

---

## Calibration Layer — Architecture

### The Formula
```
base_probability × EC_multiplier × supp_multiplier_1 × supp_multiplier_2 …
    = raw → clamped 3%–92% → display_percent
```

### Two Base Probability Modes

**Mode A — Grade-adjusted (requires ADMITTED_PROFILES entry)**
```
z = (student_grade - mean_admitted) / std_admitted
percentile = norm.cdf(z)
raw = base_rate × (1 + (percentile - 0.5) × sensitivity)
probability = clamp(raw, 0.03, 0.92)
```
- sensitivity default = 1.5
- confidence: "high" (verified=True), "low" (verified=False)

**Mode B — Base rate only**
- Fires when: combo not in ADMITTED_PROFILES, OR Gate 4 (inverted DB distribution)
- probability = base_rate (clamped)
- data_limited=True, disclaimer shown to user

### Four-Gate Structure (calibrated_probability)
1. Not in BASE_RATES → return None
2. Not in ADMITTED_PROFILES → Mode B
3. verified flag → sets confidence
4. Inverted DB check (avg_accepted ≤ avg_rejected) → Mode B fallback

### EC Multiplier (ec_scorer.py — Mode 1)
- Applies when EC_CONSIDERED[school]=True AND ec_text provided
- Ollama scores: leadership, commitment, impact, relevance (0–10 each)
- Multiplier range: 0.80–1.375
- If school not in EC_CONSIDERED, defaults to True

### Supplemental Multipliers (multi-select, independent)
Each type in supplemental_types gets its own multiplier:

| Type | Logic |
|---|---|
| none | 1.0 always |
| essay / aif | not completed → fixed penalty (0.92/0.90); completed+text → Ollama Mode 3 (0.80–1.15); completed no text → 1.0 |
| interview | 0.85 always (fixed — cannot score performance) |
| activity_list | text provided → Ollama Mode 1 (0.80–1.375); else 1.0 |

Fixed penalties in SUPPLEMENTAL_PENALTIES: essay=0.92, aif=0.90, interview=0.85

### Covered Combos (ADMITTED_PROFILES — 13 entries, all verified=True)
| School | Programs |
|---|---|
| UBC Vancouver | ENGINEERING, SCIENCE, BUSINESS |
| University of Waterloo | COMPUTER_SCIENCE, ENGINEERING |
| University of Toronto | ENGINEERING, COMPUTER_SCIENCE, BUSINESS |
| Western University | BUSINESS |
| Queen's University | BUSINESS |
| McMaster University | HEALTH |
| Simon Fraser University | ENGINEERING, SCIENCE |

BASE_RATES covers 18 combos total (5 additional as Mode B: UBC COMPUTER_SCIENCE,
UBC HEALTH, UBC ARTS, Waterloo (no extras), UofT SCIENCE, SFU BUSINESS).

EC_CONSIDERED=False: McMaster University, Simon Fraser University

---

## Key Architectural Decisions

### Why published-stats grade distribution instead of Bayesian DB approach
The original Bayesian formula (accepted vs rejected DB rows) was abandoned after
validation confirmed only 4 of 18 combos could produce output. Root cause: Reddit
data structurally over-represents accepted students (self-selection bias), causing
10+ combos to have inverted distributions (avg rejected ≥ avg accepted). The
grade-distribution approach uses published admitted grade statistics (ADMITTED_PROFILES)
anchored to published acceptance rates — produces output for all 13 ADMITTED_PROFILES
combos regardless of DB rejection data quality.

### Why supplemental_flags.py was eliminated
Originally planned as a per-school lookup for supplemental types and EC flags.
Removed because it required maintaining a school-keyed config that duplicated
information students already know about their own application. Final architecture:
student tells the system what supplementals they have — no per-school lookup needed.

### Why clear-and-reload instead of upsert
No natural unique key per student row. Students don't submit identifying information.
Clear-and-reload is idempotent and safe. Only applies to BC and BC_2025 sources —
REDDIT_SCRAPED rows are preserved across pipeline runs.

### Why reddit_agent.py is separate from main.py
The agent is slow (30-40 min), makes live HTTP requests, and should only run
occasionally — not on every data refresh. main.py runs in under 10 seconds
for daily sheet refresh.

### Why SQLite over PostgreSQL
Dataset is <10,000 rows. Zero setup, single file, sufficient for v1. Migration
path: change connection string in get_engine().

### Why JSON arrays for ec_tags and circumstance_tags
SQLite json_each() enables clean tag queries. Pipe-separated strings would
require fragile LIKE queries.

---

## Data Quality State

### Known Issues
- Selection bias: Reddit data over-represents accepted students
  - Handled by published-stats calibration (not fixable at data level)
  - Gate 4 in calibrated_probability detects and neutralizes inverted combos

- Ontario data still pending Reddit DM permission
  - Would add ~3000 rows, single largest data lever

### School Normalization
- SCHOOL_LOOKUP covers 60+ name variants
- Faculty names map to parent schools:
  Rotman→UofT, Ivey→Western, Sauder→UBC Vancouver,
  Schulich→York, Beedie→SFU, Smith→Queen's,
  Desautels→McGill, DeGroote→McMaster

### Grade Imputation
- core_avg imputed from grade_11/grade_12 average if missing
- Recovered 20 rows that would otherwise be invisible to Stage 2
- 22 rows have all grade fields blank — irreducible nulls

---

## Recommendation Engine State

### recommend.py functions
- lookup_school(school, grade, program, tolerance) → dict
- discover_schools(grade, program, tolerance, min_results) → list[dict]
- find_similar() — core query with auto-tolerance widening
- print_summary() — pretty print for terminal testing

Note: recommend.py currently calls calibrated_probability() directly (old path).
It should eventually call final_probability() so EC/supplemental multipliers
are applied. This update happens when the frontend is wired up.

### School+Program combinations with 5+ rows
UBC Vancouver: SCIENCE(73), ENGINEERING(60), BUSINESS(37),
               COMPUTER_SCIENCE(9), HEALTH(12), ARTS(21)
Western: BUSINESS(38), HEALTH(22), ENGINEERING(20), CS(6)
UofT: ENGINEERING(24), SCIENCE(23), BUSINESS(16), CS(16)
Waterloo: COMPUTER_SCIENCE(25), ENGINEERING(16)
Queen's: BUSINESS(12), ENGINEERING(12), HEALTH(5)
York: BUSINESS(11), ENGINEERING(6)
McMaster: SCIENCE(11), ENGINEERING(6)
McGill: ENGINEERING(10)
SFU: SCIENCE(15), ENGINEERING(10), BUSINESS(8), HEALTH(8)
Laurier: BUSINESS(11)
TMU: ENGINEERING(6)

---

## Immediate Next Steps

### 1. Wire final_probability() into app.py (unblock student-facing display)
The current app.py calls the old calibrated_probability() path and shows
a basic st.metric block. Needs to be replaced with a full input form:
- Grade input (number)
- Program category (select)
- Target school (select)
- EC text area (shown only when EC_CONSIDERED[school]=True)
- Supplemental multi-select (none / essay / aif / interview / activity_list)
- Per-supplemental: completed toggle + optional text paste
Output: display_percent with confidence, disclaimer if data_limited,
reasoning from Ollama if EC/supplemental was scored.

### 2. Frontend planning — Next.js
See Frontend Plan section below.

### 3. Expand ADMITTED_PROFILES coverage
Current: 13 combos. Missing high-traffic combos:
- UBC COMPUTER_SCIENCE (in BASE_RATES, no profile yet)
- UBC HEALTH (in BASE_RATES, no profile yet)
- UofT SCIENCE (in BASE_RATES, no profile yet)
- SFU BUSINESS (in BASE_RATES, no profile yet)
Use tools/research_profiles.py as a starting draft, then verify manually.

### 4. Expand BASE_RATES + ADMITTED_PROFILES to new schools
Candidates with 5+ rows but no BASE_RATES entry: Western ENGINEERING,
Queen's ENGINEERING, McMaster SCIENCE, McGill ENGINEERING, York BUSINESS.
Requires researching published acceptance rates first.

---

## Frontend Plan (Next.js)

### Stack
Next.js + TypeScript + Tailwind CSS, deployed on Vercel.
Backend: Next.js API routes calling Python logic via subprocess or FastAPI sidecar.
(recommend.py and calibrate.py stay in Python — rewriting as TypeScript is
high risk with low benefit at this stage.)

### Core User Flow
1. Student inputs: grade (number), program category (select), target school (select)
2. EC text area appears if school considers ECs
3. Supplemental multi-select: pick all types that apply
4. Per-type conditional inputs: completed toggle, optional paste area
5. Results: large display_percent, confidence badge, outcome distribution strip
6. Honest framing throughout: "X% of similar students were accepted" not
   "your chance is X%"

### Pages
- `/` — value prop + input form (single-page app feel)
- `/results` — school cards with display_percent, confidence, data caveats
- `/school/[slug]` — detailed view: full grade distribution, sample size,
  EC/supplemental breakdown, Mode A/B indicator

### Key UI Decisions to Make
- How to surface data_limited warning without alarming users
- Whether to show the full multiplier chain (base × EC × supp) or just display_percent
- Mobile-first or desktop-first (likely mobile given student demographic)
- Whether to support multi-school comparison in v1 (discover_schools path)

---

## Tech Stack Summary
- Python 3.13, pandas, spaCy, SQLAlchemy, SQLite, scipy
- Ollama (llama3.2) for Reddit extraction and EC/supplemental scoring
- Reddit JSON API (no auth) for scraping
- Next.js + TypeScript + Tailwind (planned frontend)
- Vercel (planned deployment)
- GitHub: https://github.com/jyshum/UniPath (private)
