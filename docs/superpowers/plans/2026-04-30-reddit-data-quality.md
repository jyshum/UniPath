# Reddit Data Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep grade-only Reddit rows for grade analytics while ensuring EC analytics only use rows with real EC evidence, and repair existing malformed Reddit tag JSON.

**Architecture:** Update the Reddit loader so inserted, duplicate, and failed rows are counted separately. Store tag lists in one canonical JSON layer through `row_to_student`, and make program EC breakdowns ignore rows with no real EC tags. Add a small cleanup script to normalize existing double-encoded Reddit tags in SQLite without deleting rows.

**Tech Stack:** Python 3.13, pytest, SQLAlchemy, SQLite.

---

### Task 1: Reddit Loader Accounting And Tag Storage

**Files:**
- Modify: `pipeline/reddit_agent.py`
- Test: `tests/test_reddit_agent.py`

- [ ] Write tests that show `load_student()` returns `False` for duplicate rows and that Reddit tag lists are stored as `["TAG"]`, not `["[\"TAG\"]"]`.
- [ ] Run `pytest tests/test_reddit_agent.py -v` and verify the new tests fail before implementation.
- [ ] Remove pre-serialization of `ec_tags` and `circumstance_tags` in `pipeline/reddit_agent.py`, because `row_to_student()` already serializes pipe/list-like values.
- [ ] Use the boolean return value from `load_student()` to increment `inserted_rows` or `duplicate_skipped` separately.
- [ ] Run `pytest tests/test_reddit_agent.py -v` and verify the tests pass.

### Task 2: EC Analytics Filtering

**Files:**
- Modify: `core/recommend.py`
- Test: `tests/test_program_stats.py`

- [ ] Add a test proving `program_stats()` counts total grade rows but excludes `NONE`/empty EC rows from EC percentage denominators.
- [ ] Run that test and verify it fails before implementation.
- [ ] Decode tag JSON defensively, including existing double-encoded values during the transition.
- [ ] Count EC breakdown percentages over accepted rows that have at least one real EC tag after removing `NONE` and `OTHER`.
- [ ] Run `pytest tests/test_program_stats.py -v` and verify it passes.

### Task 3: Existing DB Cleanup

**Files:**
- Create: `scripts/normalize_reddit_tags.py`
- Test: `tests/test_normalize_reddit_tags.py`

- [ ] Add tests for normalizing double-encoded tag JSON.
- [ ] Run the tests and verify they fail before implementation.
- [ ] Implement a script that updates only `REDDIT_SCRAPED` rows and only the `ec_tags`/`circumstance_tags` columns.
- [ ] Run the tests and verify they pass.
- [ ] Run `python scripts/normalize_reddit_tags.py` once against `database/unipath.db`.
- [ ] Verify no Reddit rows still have double-encoded tags.

### Task 4: Final Verification

**Files:**
- No additional files.

- [ ] Run `pytest tests/test_reddit_agent.py tests/test_program_stats.py tests/test_normalize_reddit_tags.py -v`.
- [ ] Query `students` by source and Reddit EC coverage.
- [ ] Confirm grade-only Reddit rows remain in `students`.
- [ ] Confirm malformed Reddit tags are gone.
