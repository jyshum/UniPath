# UniPath AI v2 — Program Intelligence Platform

**Date:** 2026-04-27
**Status:** Approved
**Author:** jshum + Claude

## Problem

Canadian high school students lack transparent, qualitative insight into what it actually takes to get admitted to specific university programs. Existing tools (like admit-me.com) show grade distributions behind paywalls and have zero information about extracurriculars, circumstances, or applicant profiles. UniPath AI has an automated NLP pipeline that extracts this qualitative data from Reddit — but the current frontend buries it behind a probability calculator that doesn't surface the pipeline's real value.

## Solution

Reposition UniPath AI from an odds calculator to a **Program Intelligence Platform**. Lead with browsable school/program pages that surface grade distributions, EC tag breakdowns, and circumstance patterns. The probability feature becomes secondary — a "where do you stand?" overlay on the data, not the headline.

## What Makes This Different From admit-me

| Dimension | admit-me | UniPath AI v2 |
|---|---|---|
| Data source | Manual self-report forms | Automated LLM extraction from Reddit + crowdsourced submissions |
| Qualitative data | None | EC tag frequency, circumstance tags per program |
| Paywall | Grade stats locked behind signup | Free |
| Technical story | CRUD app | NLP pipeline with eval methodology |

The EC tag breakdown is the hero feature. No other tool shows "SPORTS appeared in 62% of admitted UBC Engineering profiles."

## Architecture Overview

```
Reddit posts ──> Scraper ──> LLM extraction (Ollama) ──> Normalize ──> Tag ──> SQLite
                                                                                 |
User submissions ──> API endpoint ──> Normalize ──> Tag ─────────────────────────┘
                                                                                 |
                                                              Next.js frontend <─┘
                                                              (Program Intelligence Pages)
```

## Phase 1 — Data Foundation

All frontend work is blocked on this phase. The Program Intelligence Pages need sufficient data density to look credible.

### 1a. Backfill null program_category rows

**Problem:** ~415 rows in the DB have `program_raw` populated but `program_category`, `ec_tags`, and `circumstance_tags` are null. These were loaded from BC/Ontario spreadsheets before `extract_fields.py` existed.

**Fix:** Python script that queries all rows where `program_category IS NULL`, runs `tag_program()`, `tag_ec()`, and `tag_circumstances()` against the existing `program_raw`, `ec_raw`, and `circumstances_raw` fields, and updates in place.

**Success benchmark:** 400+ rows gain a non-null `program_category`. If significantly fewer are categorized, inspect the unmatched `program_raw` strings and expand `tag_program()` keyword lists before proceeding.

### 1b. LLM model migration + eval

**Current state:** `reddit_agent.py` uses `ollama.chat()` with `llama3.2` and free-form JSON parsing (manual markdown-fence stripping + bare `json.loads()`).

**Target state:** Ollama structured output mode (the `format` parameter with a Pydantic JSON schema) + best model determined by eval.

**Eval design (ablation study):**

Directory: `eval/`
- `ground_truth.jsonl` — 50 hand-labeled Reddit records (pull from existing DB, verify against original posts)
- `runner.py` — iterates three configurations:
  - A: llama3.2:3b + free-form (current baseline)
  - B: llama3.2:3b + structured output (isolates decoding effect)
  - C: qwen3:4b + structured output (target)
- `metrics.py` — measures JSON validity rate, schema match rate, field-level accuracy, end-to-end latency
- `results/` — output dumps per config

**Decision rule:** Pick the winner from data. If B matches C, stay on Llama. Document results — the eval itself is portfolio evidence.

**Pydantic schema for extraction:**
- school: Optional[str]
- program: Optional[str]
- decision: Optional[Literal["Accepted", "Rejected", "Waitlisted", "Deferred"]]
- core_avg: Optional[float]
- ec_raw: Optional[str]
- province: Optional[str]
- citizenship: Optional[str]
- relevant: bool

**Constraints:**
- temperature=0 for determinism
- num_ctx capped at 2-4K (Reddit posts don't need 8K)
- No hosted APIs — must stay fully local

### 1c. Scraper improvements (after eval winner chosen)

- Swap model + enable structured output in `reddit_agent.py`
- Replace manual JSON parsing with Pydantic `model_validate_json()`
- Add `r/AlbertaGrade12s` to `SUBREDDITS` list
- Re-run scraper (progress file prevents re-fetching completed queries)

### 1d. Submission pipeline

- New API endpoint: `POST /api/submit-outcome`
- Fields: school, program, grade, decision, ecs (optional freetext), province (optional)
- Runs through same `normalize_row -> extract_row -> load_to_db` pipeline
- Source field: `"USER_SUBMITTED"`
- Validation: grade 50-100, school must normalize to a known school, decision in {Accepted, Rejected, Waitlisted, Deferred}
- No auth required, anonymous submissions

## Phase 2 — Frontend Rebuild

### 2a. Home / Browse page

Grid of school+program cards. Each card shows:
- School name
- Program name
- Record count
- Mini acceptance rate badge or indicator

Search/filter by school name or program category (Engineering, Science, Business, etc.).

Only show combos with meaningful data (threshold TBD — likely 10+ records).

### 2b. Program Intelligence Page (core feature)

One page per school+program combo. Sections:

**Grade Distribution Chart**
- Stacked or grouped bar chart: accepted vs rejected vs waitlisted by grade bucket (e.g., 80-84, 85-89, 90-94, 95-100)
- Free and visible — no paywall, unlike admit-me

**EC Tag Frequency Breakdown**
- Horizontal bar chart showing % of admitted students with each EC tag
- Example: "SPORTS 62%, LEADERSHIP 48%, COMMUNITY_SERVICE 41%, ACADEMIC_COMPETITION 28%"
- This is the differentiating feature no competitor has

**Circumstance Tags**
- Show if meaningful data exists (IB_STUDENT, INTERNATIONAL, etc.)
- Hide section if data is too thin

**Key Stats**
- Total records for this combo
- Average admitted grade
- Grade range (min-max of accepted students)
- Data source badge: "Based on 147 Reddit posts + 23 submissions"

**"Where Do You Stand?"**
- Collapsible section at the bottom
- Student enters their grade
- Shows where they fall on the grade distribution
- Uses existing calibrated_probability engine, but presented as position on the chart, not a headline percentage
- Display percent still available but de-emphasized

**"Add Your Outcome"**
- Inline submission form
- School and program pre-filled from the page context
- Feeds the Phase 1d submission pipeline

**Confidence indicator**
- If record count < 20: "Limited data — N records. Take insights with a grain of salt."

### 2c. Standalone Submit page

Same form as the inline version, accessible from nav. For students who want to contribute without browsing a specific program.

## Phase 3 — Polish & Portfolio

- Data provenance badges on every page
- Confidence indicators for thin combos
- README rewrite with architecture diagram showing full pipeline
- Eval results documented as part of project narrative
- Clean up unused frontend components from the old probability-first design

## What's Cut

- Probability % as the headline feature (demoted to "Where Do You Stand?")
- CASPer/interview/essay scoring multipliers (overengineered for available data)
- Loading screen animation (browsing is instant, no form submission wait)
- The `SummaryBar` component (designed for multi-school odds comparison — no longer relevant)

## Success Criteria

1. **Data:** 400+ null rows backfilled. Total categorized records > 800.
2. **Eval:** Documented ablation study with clear winner selection.
3. **Frontend:** At least 5 school+program combos with credible Program Intelligence Pages (20+ records each).
4. **Differentiation:** EC tag breakdown visible and meaningful on top combos.
5. **Submissions:** Working anonymous submission form that feeds the live DB.
