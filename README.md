# UniPath AI

Canadian university admissions outcomes tool for high school students.

Students enter their grades, target school, and program to get a **calibrated acceptance likelihood** anchored to published university acceptance rates — plus a panel showing grade data from real admitted students in our dataset.

**Core differentiator:** real student submission data, not synthetic or generic LLM advice.

---

## What It Does

- Calculates a personalized acceptance probability using published admission statistics and a grade-adjusted normal distribution model
- Scores extracurriculars and supplemental materials (essays, AIFs) via a local LLM (Ollama llama3.2)
- Surfaces a similar students panel: grade ranges and averages from real accepted applicants in the database
- Covers 7 Canadian universities across 18 school/program combinations

---

## Tech Stack

| Layer | Tech |
|---|---|
| Data pipeline | Python 3.13, pandas, SQLAlchemy, SQLite |
| Probability engine | scipy (normal distribution), Ollama llama3.2 |
| Data sources | Google Sheets (BC 2025/2026), Reddit JSON API |
| Frontend | Next.js + TypeScript + Tailwind CSS |
| Python–Node bridge | stdin/stdout JSON subprocess |

---

## Architecture

```
Google Sheets → fetch_sheets.py → normalize.py → extract_fields.py → unipath.db
Reddit JSON API → reddit_agent.py → unipath.db

unipath.db → core/calibrate.py  (probability calculation)
          → core/recommend.py   (similar students panel)

Next.js form → /api/final-probability → python_bridge/final_probability.py
                                      → calibrate + recommend → JSON response → UI
```

---

## How Probability Is Calculated

```
base_probability × EC_multiplier × supp_multiplier_1 × ... = raw → clamped 3%–92%
```

**Mode A (grade-adjusted):** uses a z-score against published admitted grade stats (mean, std) to adjust above/below the school's base acceptance rate.

**Mode B (base rate only):** fires when grade data is unavailable or the database shows an inverted distribution (selection bias safety valve).

Supplemental multipliers cover essays, AIFs, and activity lists — scored via Ollama when text is provided.

---

## Database

- Path: `database/unipath.db`
- 814 rows — BC 2025 (218), BC 2026 (181), Reddit scraped (415)
- Decision split: 666 ACCEPTED, 68 REJECTED, 65 WAITLISTED, 28 DEFERRED
- Reddit data preserved across pipeline re-runs; BC sources are cleared and reloaded

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

The app runs at `http://localhost:3000`.

---

## Project Status

Functionally complete for v1. See [PROJECT_STATE.md](PROJECT_STATE.md) for full architecture details, known issues, and next steps.

**Deployment is not yet live.** The Python bridge requires a FastAPI sidecar (Railway/Render) — subprocess spawning does not work in Vercel serverless environments.

---

## Repo

Private: https://github.com/jyshum/UniPath
