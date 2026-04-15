# UniPath AI — Project State
Last updated: April 5, 2026

---

## What It Is
University outcomes tool for Canadian high school students.
Students input grades + program + target school and see a calibrated
acceptance likelihood percentage anchored to published university acceptance rates,
plus a panel showing grade data from real admitted students in our dataset.

Core differentiator: real student submission data, not synthetic or generic LLM advice.

---

## Current Status

| Component | Status |
|---|---|
| ETL pipeline (Google Sheets → DB) | COMPLETE |
| Reddit scraping agent | COMPLETE — 415 rows |
| Database (814 rows total) | COMPLETE |
| Probability calibration (core/calibrate.py) | COMPLETE — 30 passing tests |
| EC/supplemental scoring (core/ec_scorer.py) | COMPLETE |
| Similar students panel (core/recommend.py → frontend) | COMPLETE |
| Next.js frontend (form + result UI) | COMPLETE |
| API route (/api/final-probability) | COMPLETE |
| Python bridge (frontend → calibrate + recommend) | COMPLETE |

**The product is functionally complete for v1.** All core features work end-to-end:
probability calculation, EC/supplemental scoring, and the similar students panel.
Remaining work is coverage expansion and deployment.

---

## Architecture

### Data Flow

```
Google Sheets (live) → fetch_sheets.py → data/processed/
data/processed/ → normalize.py → data/cleaned/bc_cleaned.csv
data/cleaned/ → extract_fields.py → data/cleaned/bc_extracted.csv
data/cleaned/ → load_to_db.py → database/unipath.db

Reddit JSON API → reddit_agent.py → database/unipath.db (direct)

database/unipath.db → core/calibrate.py (Gate 4 sanity check)
database/unipath.db → core/recommend.py → similar_students panel

core/calibrate.py (published stats + Ollama) → final_probability()
core/recommend.py → find_similar() → ACCEPTED-only grade stats

final_probability.py bridge:
  → calibrate.final_probability() + recommend.find_similar()
  → JSON response → /api/final-probability → ResultView
```

### Key Files

| File | Purpose | Status |
|---|---|---|
| `main.py` | Orchestrates full ETL pipeline | COMPLETE |
| `pipeline/fetch_sheets.py` | Pulls BC 2026 + BC 2025 from Google Sheets | COMPLETE |
| `pipeline/normalize.py` | Grade parsing, school/decision normalization | COMPLETE |
| `pipeline/extract_fields.py` | NLP tagging for EC, circumstances, program | COMPLETE |
| `pipeline/load_to_db.py` | Loads cleaned CSV to SQLite, idempotent | COMPLETE |
| `pipeline/reddit_agent.py` | Standalone Reddit scraper (run separately) | COMPLETE |
| `database/models.py` | SQLAlchemy ORM schema | COMPLETE |
| `core/calibrate.py` | calibrated_probability() and final_probability() | COMPLETE |
| `core/ec_scorer.py` | score_profile() via Ollama llama3.2 | COMPLETE |
| `core/recommend.py` | find_similar() — DB lookup for similar admitted students | COMPLETE |
| `frontend/app/page.tsx` | Main form + result UI | COMPLETE |
| `frontend/app/api/final-probability/route.ts` | POST endpoint → python bridge | COMPLETE |
| `frontend/lib/pythonBridge.ts` | Spawns Python subprocess | COMPLETE |
| `frontend/python_bridge/final_probability.py` | Bridge: calls calibrate + recommend, returns combined JSON | COMPLETE |
| `frontend/components/ResultView.tsx` | Result display incl. similar students panel | COMPLETE |
| `frontend/components/` | SchoolProgramSelector, GradeInput, SupplementalCards, LoadingScreen, SummaryBar | COMPLETE |
| `frontend/lib/types.ts` | TypeScript interfaces incl. SimilarStudents, FinalProbabilityResult | COMPLETE |
| `frontend/lib/constants.ts` | SCHOOLS, PROGRAMS_BY_SCHOOL, ADMITTED_PROFILE_KEYS | COMPLETE |
| `tools/research_profiles.py` | Manual draft tool for new ADMITTED_PROFILES entries | COMPLETE |
| `tests/test_calibration.py` | 30 pytest tests for calibrate.py + ec_scorer.py | 28/30 passing* |

*Tests 27 and 30 have a pre-existing bug: they hardcode `0.90` for the interview penalty
but `SUPPLEMENTAL_PENALTIES["interview"]` is `1.00`. Unrelated to any recent changes.

### Database

- Path: `database/unipath.db`
- Table: `students`
- Sources: BC (181 rows), BC_2025 (218 rows), REDDIT_SCRAPED (415 rows)
- Total: 814 rows — decision split: ACCEPTED 666, REJECTED 68, WAITLISTED 65, DEFERRED 28
- REDDIT_SCRAPED rows preserved across pipeline re-runs (BC/BC_2025 are cleared and reloaded)

---

## How Probability Is Calculated

### The Formula
```
base_probability × EC_multiplier × supp_multiplier_1 × supp_multiplier_2 …
    = raw → clamped 3%–92% → display_percent
```

### What the DB contributes vs. what is hardcoded

The probability calculation is anchored to **published university statistics**, not derived
from DB rows. This was an intentional decision after the Bayesian approach failed due
to selection bias (Reddit over-represents accepted students — 10+ combos had inverted
distributions where avg_rejected ≥ avg_accepted).

| Data Source | Role |
|---|---|
| `BASE_RATES` (hardcoded in core/calibrate.py) | Published acceptance rates for 18 combos |
| `ADMITTED_PROFILES` (hardcoded in core/calibrate.py) | Published admitted grade stats (mean, std) for 13 combos |
| `database/unipath.db` | Gate 4 sanity check (detects inverted distributions → Mode B fallback) |
| `database/unipath.db` via core/recommend.py | Powers similar students panel (ACCEPTED rows only, ±5 grade window) |

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
- data_limited=True, disclaimer shown in UI

### Four-Gate Structure (calibrated_probability)
1. Not in BASE_RATES → return None
2. Not in ADMITTED_PROFILES → Mode B
3. verified flag → sets confidence
4. Inverted DB check (avg_accepted ≤ avg_rejected) → Mode B fallback

### Supplemental Multipliers

| Type | Logic |
|---|---|
| none | 1.0 always |
| essay | not completed → 0.92 penalty; completed + text → Ollama Mode 3 (1.00–2.00); completed no text → 1.0 |
| aif | not completed → 0.95 penalty; completed + text → Ollama Mode 3; completed no text → 1.0 |
| interview | 1.0 always (fixed — cannot score performance) |
| activity_list | text → Ollama Mode 1 (0.80–1.375); else 1.0 |

### EC Multiplier (ec_scorer.py — Mode 1)
- Applies when EC_CONSIDERED[school]=True AND ec_text provided
- Ollama scores: leadership, commitment, impact, relevance (0–10 each)
- Multiplier range: 0.80–1.375
- EC_CONSIDERED=False: McMaster University, Simon Fraser University

### Covered Combos

| School | ADMITTED_PROFILES (Mode A) | BASE_RATES only (Mode B) |
|---|---|---|
| UBC Vancouver | ENGINEERING, SCIENCE, BUSINESS | COMPUTER_SCIENCE, HEALTH, ARTS |
| University of Waterloo | COMPUTER_SCIENCE, ENGINEERING | — |
| University of Toronto | ENGINEERING, COMPUTER_SCIENCE, BUSINESS | SCIENCE |
| Western University | BUSINESS | — |
| Queen's University | BUSINESS | — |
| McMaster University | HEALTH | — |
| Simon Fraser University | ENGINEERING, SCIENCE | BUSINESS |

---

## Similar Students Panel

Surfaces grade data from real admitted students without implying anything about
acceptance rates (DB is ~80% accepted due to Reddit survivorship bias — raw ratios
would actively mislead students).

### What it shows
- Count of ACCEPTED students in DB matching school + program within ±5 grade points
- Their grade range (min–max) and average
- Honest copy that does not imply the DB represents the full applicant pool

### Three states
- **N ≥ 3:** "N students admitted to [School] [Program] reported grades between X% and Y%, with an average of Z%."
- **0 < N < 3:** "A small number of admitted students reported similar grades. Data is limited — treat this as anecdotal."
- **N = 0 / null:** "No admitted students in our dataset reported grades in this range. This doesn't indicate rejection likelihood — our dataset is limited."
- **Field absent:** Panel not shown at all

### Implementation
- Bridge calls `find_similar(grade, program, school, tolerance=5.0, max_tolerance=5.0)` — fixed window, no auto-widening
- Filters DataFrame to `decision == 'ACCEPTED'` before computing any stats
- Returns `similar_students: {count, avg_grade, min_grade, max_grade}` or `null`
- Rendered in `ResultView.tsx` below the "How was this calculated?" collapsible

---

## Frontend → Python Bridge Call Chain

```
page.tsx → POST /api/final-probability
  → pythonBridge.ts (spawns subprocess, CWD = frontend/)
  → frontend/python_bridge/final_probability.py
      → core.calibrate.final_probability(school, program, grade, supplemental_types, ...)
      → core.recommend.find_similar(grade, program, school, tolerance=5.0)
          → filter to ACCEPTED only
  → JSON response → ResultView (probability + similar_students)
```

Note: `core/calibrate.py` and `core/recommend.py` use `Path(__file__)` for DB_PATH
so they resolve correctly regardless of the subprocess CWD.

---

## Immediate Next Steps

### 1. Fix tests 27 and 30
Both hardcode `0.90` for the interview penalty but actual value is `1.00`.
Quick fix — update the hardcoded values and expected arithmetic in the test.

### 2. Expand ADMITTED_PROFILES coverage
Current: 13 combos. Missing high-traffic combos:
- UBC COMPUTER_SCIENCE
- UBC HEALTH
- UofT SCIENCE
- SFU BUSINESS
Use `tools/research_profiles.py` as a starting draft, then verify manually.

### 3. Expand BASE_RATES + ADMITTED_PROFILES to new schools
Candidates with 5+ rows but no BASE_RATES entry:
Western ENGINEERING, Queen's ENGINEERING, McMaster SCIENCE, McGill ENGINEERING, York BUSINESS.

### 4. Deployment
- Vercel for Next.js frontend
- Python bridge requires a sidecar (FastAPI or similar) — subprocess spawn won't work in Vercel serverless
- Recommended path: wrap bridge logic in FastAPI on Railway/Render, call via HTTP from Next.js API routes

---

## Key Architectural Decisions

### Why published-stats calibration instead of Bayesian DB approach
The Bayesian formula (accepted vs rejected DB rows) was abandoned after validation
confirmed only 4 of 18 combos could produce output. Root cause: Reddit data
structurally over-represents accepted students (selection bias), causing 10+ combos
to have inverted distributions (avg_rejected ≥ avg_accepted). The current approach
uses published admitted grade statistics anchored to published acceptance rates —
produces output for all 13 ADMITTED_PROFILES combos regardless of DB quality.

### Why the similar students panel shows ACCEPTED-only data
The DB is ~80% accepted due to Reddit survivorship bias. Showing raw accepted/rejected
ratios (e.g. "11 accepted, 2 rejected") would imply an 85% acceptance rate for schools
that actually accept 8–25% of applicants — actively misleading. Grade distributions of
accepted students are trustworthy because self-selection bias doesn't distort them.

### Why the similar students panel uses a fixed ±5 window
Auto-widening (default recommend.py behavior) could produce a "12 admitted students,
grades 80–97%" result after widening to ±8 — a range so broad it means nothing. Fixed
±5 covers ~2 standard deviations of admitted grades and fails honestly when data is sparse.

### Why Python bridge instead of rewriting calibrate.py in TypeScript
High risk, low benefit. The calibration math and Ollama integration are stable and tested.
The bridge (stdin/stdout JSON) is the lowest-friction path to v1.
Production path: wrap in FastAPI, call via HTTP.

### Why SQLite over PostgreSQL
Dataset is <10,000 rows. Zero setup, single file, sufficient for v1.
Migration path: change connection string in get_engine().

### Why reddit_agent.py is separate from main.py
The agent is slow (30–40 min), makes live HTTP requests, and should only run
occasionally. main.py runs in under 10 seconds for daily sheet refresh.

---

## Data Quality State

### Known Issues
- Selection bias: Reddit data over-represents accepted students (~80% ACCEPTED)
  - Handled by published-stats calibration (not fixable at data level)
  - Gate 4 detects and neutralizes inverted distributions
  - Similar students panel intentionally shows ACCEPTED-only grade data

- Ontario data still pending Reddit DM permission
  - Would add ~3,000 rows — single largest data lever

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

## Tech Stack Summary
- Python 3.13, pandas, spaCy, SQLAlchemy, SQLite, scipy
- Ollama (llama3.2) for Reddit extraction and EC/supplemental scoring
- Reddit JSON API (no auth) for scraping
- Next.js + TypeScript + Tailwind CSS (frontend — built and running)
- GitHub: https://github.com/jyshum/UniPath (private)
- Deployment: NOT YET (Vercel for frontend; Python layer needs FastAPI sidecar)
