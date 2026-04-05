# UniPath AI — Project State
Last updated: April 5, 2026

---

## What It Is
University outcomes tool for Canadian high school students.
Students input grades + program + target school and see a calibrated
acceptance likelihood percentage anchored to published university acceptance rates.

Core differentiator: real student submission data, not synthetic or
generic LLM advice.

---

## Current Status

| Component | Status |
|---|---|
| ETL pipeline (Google Sheets → DB) | COMPLETE |
| Reddit scraping agent | COMPLETE — 415 rows |
| Database (814 rows total) | COMPLETE |
| Probability calibration (calibrate.py) | COMPLETE — 30 passing tests |
| EC/supplemental scoring (ec_scorer.py) | COMPLETE |
| Next.js frontend (form + result UI) | COMPLETE |
| API route (/api/final-probability) | COMPLETE |
| Python bridge (frontend → calibrate.py) | COMPLETE |
| recommend.py wired to frontend | NOT DONE — DB lookup results not surfaced in UI |

**Key gap:** The 814 DB rows are not contributing to the frontend result.
The frontend currently shows probability % only (from calibrate.py + hardcoded stats).
The DB data should power the social proof strip: "N similar students found — X accepted, Y rejected."
This requires wiring recommend.py into the API route and result view.

---

## Architecture

### Data Flow

```
Google Sheets (live) → fetch_sheets.py → data/processed/
data/processed/ → normalize.py → data/cleaned/bc_cleaned.csv
data/cleaned/ → extract_fields.py → data/cleaned/bc_extracted.csv
data/cleaned/ → load_to_db.py → database/unipath.db

Reddit JSON API → reddit_agent.py → database/unipath.db (direct)

database/unipath.db → core/calibrate.py (Gate 4 sanity check only)
database/unipath.db → core/recommend.py → similar student breakdown  ← NOT YET IN FRONTEND

core/calibrate.py (published stats + Ollama) → final_probability()
final_probability() → frontend/python_bridge/ → /api/final-probability → page.tsx
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
| `core/recommend.py` | find_similar(), lookup_school(), discover_schools() | COMPLETE but NOT WIRED TO FRONTEND |
| `core/calibrate.py` | calibrated_probability() and final_probability() | COMPLETE |
| `core/ec_scorer.py` | score_profile() via Ollama llama3.2 | COMPLETE |
| `frontend/app/page.tsx` | Main form + result UI | COMPLETE |
| `frontend/app/api/final-probability/route.ts` | POST endpoint → python bridge | COMPLETE |
| `frontend/lib/pythonBridge.ts` | Spawns Python subprocess | COMPLETE |
| `frontend/python_bridge/final_probability.py` | Bridge: JSON stdin → calibrate → JSON stdout | COMPLETE |
| `frontend/components/` | SchoolProgramSelector, GradeInput, SupplementalCards, ResultView, LoadingScreen, SummaryBar | COMPLETE |
| `frontend/lib/constants.ts` | SCHOOLS, PROGRAMS_BY_SCHOOL, ADMITTED_PROFILE_KEYS | COMPLETE |
| `tools/research_profiles.py` | Manual draft tool for new ADMITTED_PROFILES entries | COMPLETE |
| `tests/test_calibration.py` | 30 pytest tests for calibrate.py + ec_scorer.py | COMPLETE, all passing |

### Database

- Path: `database/unipath.db`
- Table: `students`
- Sources: BC (181 rows), BC_2025 (218 rows), REDDIT_SCRAPED (415 rows)
- Total: 814 rows
- REDDIT_SCRAPED rows are preserved across pipeline re-runs (BC/BC_2025 are cleared and reloaded)

---

## How Probability Is Calculated

### The Formula
```
base_probability × EC_multiplier × supp_multiplier_1 × supp_multiplier_2 …
    = raw → clamped 3%–92% → display_percent
```

### What the DB contributes vs. what is hardcoded

The probability calculation is anchored to **published university statistics**, not derived
from the DB rows. This was an intentional decision after the Bayesian approach failed due
to selection bias (Reddit over-represents accepted students — 10+ combos had inverted
distributions where avg_rejected ≥ avg_accepted).

| Data Source | Role |
|---|---|
| `BASE_RATES` (hardcoded in core/calibrate.py) | Published acceptance rates for 18 combos |
| `ADMITTED_PROFILES` (hardcoded in core/calibrate.py) | Published admitted grade stats (mean, std) for 13 combos |
| `database/unipath.db` | Gate 4 sanity check only (detects inverted distributions → falls back to Mode B) |
| `database/unipath.db` via core/recommend.py | Should power social proof strip — NOT YET WIRED |

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

### Supplemental Multipliers

| Type | Logic |
|---|---|
| none | 1.0 always |
| essay | not completed → 0.92; completed + text → Ollama Mode 3 (1.00–2.00); completed no text → 1.0 |
| aif | not completed → 0.95; completed + text → Ollama Mode 3; completed no text → 1.0 |
| interview | 0.85 always |
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

## Frontend State

The Next.js frontend is built and wired end-to-end for probability display.

### What works
- Form: school + program selector (validates against ADMITTED_PROFILE_KEYS)
- Grade input (50–100)
- Supplemental cards (multi-select, per-type conditional inputs)
- Loading animation (2.5s)
- Result view: probability %, confidence badge, decision breakdown, Ollama reasoning
- Summary bar: session history for multi-school comparison
- API route → python bridge → calibrate.final_probability() → JSON response

### What's missing
- **Social proof / similar student strip**: "N students found — X accepted, Y rejected"
  This requires adding a recommend.py call to the API route and extending the result view.
- Mobile optimization
- Deployment (Vercel)
- ADMITTED_PROFILE_KEYS gate currently restricts frontend to 13 combos only

### Frontend → Python bridge call chain
```
page.tsx → POST /api/final-probability
  → pythonBridge.ts (spawns subprocess)
  → frontend/python_bridge/final_probability.py
  → calibrate.final_probability(school, program, grade, supplemental_types, ...)
  → JSON response → ResultView
```

---

## Immediate Next Steps

### 1. Wire recommend.py into the result (HIGH VALUE — makes pipeline data matter)
Add a second call in `frontend/python_bridge/final_probability.py` to `recommend.lookup_school()`.
Include in JSON response: `{total_similar, accepted_count, rejected_count, avg_grade_accepted}`.
Extend `ResultView.tsx` to show: "Based on N similar students: X accepted (Y%), Z rejected."
This is the single change that makes the 814 DB rows contribute to the product.

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
- Alternative: deploy Python layer on Railway/Render, call via HTTP from Next.js API routes

---

## Key Architectural Decisions

### Why published-stats calibration instead of Bayesian DB approach
The Bayesian formula (accepted vs rejected DB rows) was abandoned after validation
confirmed only 4 of 18 combos could produce output. Root cause: Reddit data
structurally over-represents accepted students (selection bias), causing 10+ combos
to have inverted distributions (avg_rejected ≥ avg_accepted). The current approach
uses published admitted grade statistics anchored to published acceptance rates —
produces output for all 13 ADMITTED_PROFILES combos regardless of DB quality.

### Why the DB still matters despite not driving calibration
1. Gate 4 sanity check — detects and neutralizes inverted distributions
2. recommend.py lookup — actual students with similar grades/programs → social proof
3. Future expansion — as DB grows, may eventually support Bayesian estimates for
   combos with enough clean data

### Why reddit_agent.py is separate from main.py
The agent is slow (30–40 min), makes live HTTP requests, and should only run
occasionally. main.py runs in under 10 seconds for daily sheet refresh.

### Why Python bridge instead of rewriting calibrate.py in TypeScript
High risk, low benefit. The calibration math and Ollama integration are stable
and tested. The bridge (stdin/stdout JSON) is the lowest-friction path to v1.
Production path: wrap in FastAPI, call via HTTP.

### Why SQLite over PostgreSQL
Dataset is <10,000 rows. Zero setup, single file, sufficient for v1. Migration
path: change connection string in get_engine().

---

## Data Quality State

### Known Issues
- Selection bias: Reddit data over-represents accepted students
  - Handled by published-stats calibration (not fixable at data level)
  - Gate 4 in calibrated_probability detects and neutralizes inverted combos

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
- Next.js + TypeScript + Tailwind CSS (frontend — built)
- GitHub: https://github.com/jyshum/UniPath (private)
- Deployment: NOT YET (Vercel for frontend; Python layer needs sidecar)
