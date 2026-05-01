# UniPath AI — Claude Context

Canadian university admissions outcomes tool. Real student data, not synthetic advice.

## Stack
- **Pipeline:** Python 3.13, pandas, SQLAlchemy, SQLite (`database/unipath.db`)
- **Frontend:** Next.js (app router at `frontend/app/`), TypeScript, Tailwind
- **Python bridge:** FastAPI sidecar (`server/main.py`) — Vercel can't spawn subprocesses
- **LLM:** Ollama llama3.2 (local) for EC/essay scoring and Reddit extraction

## Key Paths
```
pipeline/          fetch_sheets, normalize, extract_fields, load_to_db, reddit_agent, cudo_scraper, program_names
core/              calibrate.py (probability), recommend.py (similar students), ec_scorer.py
server/main.py     FastAPI sidecar
frontend/app/
  program/[school]/[...program]/ program intelligence page
  submit/                       anonymous submission
  api/final-probability/        probability API route
  api/base-probability/
```

## Database
- `students` table — 949 rows: Reddit (508), BC 2025 (218), BC (216), User-submitted (7)
- Key columns: `source`, `school_normalized`, `program_category`, `program_normalized`, `decision`, `grade_11_avg`, `grade_12_avg`, `core_avg`, `ec_tags`, `circumstance_tags`
- **NEVER clear REDDIT_SCRAPED or USER_SUBMITTED rows** — pipeline only reloads BC/BC_2025
- CUDO data is merged at the API layer, not stored in the DB

## The Data Problem
Reddit rows add useful school/program/decision/grade records, but many do not include extracurricular evidence. EC analytics only use rows with real EC tags, while grade-only Reddit rows stay available for grade distributions. CUDO integration supplements sparse community data with aggregated institutional data.

## Probability Model
```
base_rate × EC_multiplier × supp_multipliers → clamped 3%–92%
```
- **Mode A** (grade-adjusted): z-score against published admitted grade stats
- **Mode B** (base rate only): fires when grade data unavailable or distribution is inverted (selection bias guard)

## Program Categories
`ENGINEERING | SCIENCE | BUSINESS | ARTS | COMPUTER_SCIENCE | HEALTH | LAW | EDUCATION | OTHER`

## Decision Values
`ACCEPTED | REJECTED | WAITLISTED | DEFERRED`

## What's Done
- v1: pipeline, Reddit scraper, probability engine, Ollama EC scoring
- v2: program browse grid + category filter, program intelligence page (grade dist, EC breakdown, historical trends), "Where Do You Stand?" panel, anonymous submission form, CUDO HTML scraper, program_normalized column + backfill, LLM extraction eval framework (llama freeform vs structured vs qwen3), 7-bucket grade distribution, fixed double-encoded EC tags
