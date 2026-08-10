# UniPath AI

Canadian university admissions outcomes tool for high school students.

Students browse real admitted student data by school and program — grade distributions, EC breakdowns, and historical acceptance trends — and optionally get a calibrated acceptance likelihood based on their own grades.

**Core differentiator:** real student submission data, not synthetic or generic LLM advice.

Currently not live due to lack of usable data — an ongoing problem.

---

## What It Does

- **Browse page:** grid of programs with filters by school category; each card shows acceptance rate and grade range
- **Program page:** detailed grade distribution chart (7 buckets), EC tag breakdown, historical trends by year, and a "Where Do You Stand?" acceptance likelihood panel
- **Anonymous submission form:** students can submit their own outcome to grow the dataset
- **Acceptance probability engine:** personalized likelihood using published stats + grade-adjusted normal distribution; scored via Ollama llama3.2 for essays/AIFs/ECs
- **Canonical program taxonomy:** `canadian_programs.json` drives program aliases, categories, admission metadata, Reddit prompt guidance, and backfills
- Covers 7 Canadian universities across 18+ school/program combinations

---

## Tech Stack

| Layer | Tech |
|---|---|
| Data pipeline | Python 3.13, pandas, SQLAlchemy, SQLite |
| Probability engine | scipy (normal distribution), Ollama llama3.2 |
| Data sources | Google Sheets (BC 2025/2026), Reddit JSON API, CUDO (HTML scraper) |
| Frontend | Next.js + TypeScript + Tailwind CSS |
| Python–Node bridge | FastAPI sidecar (Railway/Render) |

---

## Architecture

```
Google Sheets → fetch_sheets.py → normalize.py → extract_fields.py → unipath.db
Reddit JSON API → reddit_agent.py → unipath.db
CUDO HTML → cudo_scraper.py → merged at API layer (not stored in DB)

unipath.db → /api/program_stats  (grade distribution, EC breakdown)
           → /api/final-probability → calibrate.py + recommend.py → JSON response → UI
```

---

## Database

- Path: `database/unipath.db`
- **949 rows total** — Reddit (508), BC 2025 (218), BC (216), User-submitted (7)
- Reddit rows now include grade-only records for grade analytics; EC analytics only use rows with real EC tags

### The Data Problem

Most rows are skewed toward accepted students (selection bias — people post wins). Reddit adds useful grade/program/decision records, but many rows do not contain extracurricular evidence, so EC breakdowns intentionally exclude grade-only Reddit rows from their percentage denominator. Some programs still have few community records, which makes grade distributions noisy for those programs.

**Mitigation:** CUDO integration supplements with aggregated institutional data (grade ranges, acceptance rates) for programs where individual row counts are too low.

---

## What's Been Built

### v1 — Probability Engine
- Data pipeline: BC Google Sheets fetch → normalize → extract fields → SQLite
- Reddit scraper agent (Ollama llama3.2) for additional data points
- Acceptance probability model (Mode A: grade-adjusted z-score; Mode B: base rate fallback)
- EC/essay/AIF scoring via Ollama multipliers

### v2 — Program Intelligence Platform (current)
- Replaced odds-calculator homepage with a **program browse grid** + category filter bar
- Built **Program Intelligence page** per program: grade distribution (7 buckets), EC tag breakdown, historical trends collapsible
- Added **"Where Do You Stand?"** collapsible section with personalized probability
- Added **anonymous submission form** (inline + standalone `/submit`) to grow dataset
- Integrated **CUDO scraper** (University of Windsor + others) — merges with pipeline data at the API layer
- Added `program_normalized` column + backfill for consistent program name matching
- Built **LLM extraction eval framework** (ablation: llama freeform vs structured output vs qwen3)
- Expanded grade buckets from 5 to 7 for better CUDO alignment
- Cleaned up double-encoded EC/circumstance tags on Reddit rows

---

## Covered Schools

| School | Mode A (grade-adjusted) | Mode B (base rate only) |
|---|---|---|
| UBC Vancouver | Engineering, Science, Business | Computer Science, Health, Arts |
| University of Waterloo | Computer Science, Engineering | — |
| University of Toronto | Engineering, Computer Science, Business | Science |
| Western University | Business | — |
| Queen's University | Business | — |
| McMaster University | Health | — |
| Simon Fraser University | Engineering, Science | Business |

---

## Setup

### Prerequisites

- Python 3.13+
- Node.js 18+
- [Ollama](https://ollama.ai) with `llama3.2` pulled

### Python environment

```bash
pip install -r requirements.txt
```

### Run the data pipeline

```bash
python main.py
```

To scrape Reddit data (slow, run separately):

```bash
python pipeline/reddit_agent.py
```

### Run the frontend

```bash
cd frontend
npm install
npm run dev
```

App runs at `http://localhost:3000`.

---

## Deployment

Frontend deploys to Vercel. The Python bridge (probability engine) requires a FastAPI sidecar on Railway or Render — Vercel serverless cannot spawn subprocesses.
