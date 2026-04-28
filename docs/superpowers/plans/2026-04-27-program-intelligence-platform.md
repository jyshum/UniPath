# Program Intelligence Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform UniPath AI from a probability calculator into a browsable Program Intelligence Platform where students explore school/program pages showing grade distributions and EC tag breakdowns, with an optional "Where Do You Stand?" calculator and crowdsourced submission form.

**Architecture:** Next.js frontend serves program pages backed by a FastAPI server that queries SQLite. New API endpoints return aggregated stats per school+program combo. The Reddit scraper gets a model eval framework and structured output mode. A submission endpoint accepts anonymous user data through the same normalize/tag pipeline.

**Tech Stack:** Python 3 (FastAPI, SQLAlchemy, Pydantic, Ollama), Next.js 16 (React 19, Tailwind 4), SQLite, pytest

---

## File Structure

### Python (backend)

| File | Responsibility |
|---|---|
| `scripts/fix_double_encoded_tags.py` | **Create.** One-time migration: fix double-JSON-encoded ec_tags and circumstance_tags on REDDIT_SCRAPED rows |
| `eval/ground_truth.jsonl` | **Create.** 50 hand-labeled Reddit extraction records |
| `eval/runner.py` | **Create.** Ablation eval: 3 configs × 50 records, measures accuracy + latency |
| `eval/metrics.py` | **Create.** Field-level accuracy, JSON validity, schema match scoring |
| `eval/schemas.py` | **Create.** Pydantic model for Reddit extraction (shared with runner + reddit_agent) |
| `pipeline/reddit_agent.py` | **Modify.** Switch to structured output mode, use Pydantic schema, add subreddits |
| `server/main.py` | **Modify.** Add `/programs` list endpoint, `/programs/{school}/{program}` detail endpoint, `/submit-outcome` endpoint |
| `core/recommend.py` | **Modify.** Add `program_stats()` function for aggregated stats per combo |

### Frontend

| File | Responsibility |
|---|---|
| `frontend/app/page.tsx` | **Rewrite.** Home/browse page with program cards grid |
| `frontend/app/program/[school]/[program]/page.tsx` | **Create.** Program Intelligence Page |
| `frontend/app/submit/page.tsx` | **Create.** Standalone submission form |
| `frontend/components/ProgramCard.tsx` | **Create.** Card for browse grid |
| `frontend/components/GradeDistribution.tsx` | **Create.** Stacked bar chart (accepted/rejected/waitlisted by grade bucket) |
| `frontend/components/ECBreakdown.tsx` | **Create.** Horizontal bar chart of EC tag frequencies |
| `frontend/components/WhereDoYouStand.tsx` | **Create.** Collapsible grade input + position indicator |
| `frontend/components/SubmitOutcomeForm.tsx` | **Create.** Anonymous submission form (inline + standalone) |
| `frontend/lib/types.ts` | **Modify.** Add new types for program stats, submission |
| `frontend/lib/constants.ts` | **Modify.** Update to dynamic data from API instead of hardcoded lists |

---

## Task 1: Fix double-encoded ec_tags on Reddit rows

The Reddit scraper double-JSON-encodes tags: `["[\"SPORTS\", \"ARTS\"]"]` instead of `["SPORTS", "ARTS"]`. This must be fixed before any frontend reads EC data.

**Files:**
- Create: `scripts/fix_double_encoded_tags.py`
- Test: manual verification via sqlite3

- [ ] **Step 1: Write the migration script**

```python
# scripts/fix_double_encoded_tags.py
"""
One-time fix: Reddit-scraped rows have double-JSON-encoded ec_tags and
circumstance_tags. e.g. '["[\\"SPORTS\\", \\"ARTS\\"]"]' instead of
'["SPORTS", "ARTS"]'. This script normalizes them in place.
"""
import json
import sqlite3

DB_PATH = "database/unipath.db"


def fix_double_encoded(conn: sqlite3.Connection, column: str) -> int:
    rows = conn.execute(
        f"SELECT id, {column} FROM students WHERE {column} IS NOT NULL"
    ).fetchall()

    fixed = 0
    for row_id, raw in rows:
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        # Detect double-encoding: a list containing a single string that is itself a JSON array
        if (
            isinstance(parsed, list)
            and len(parsed) == 1
            and isinstance(parsed[0], str)
            and parsed[0].startswith("[")
        ):
            try:
                inner = json.loads(parsed[0])
                if isinstance(inner, list):
                    conn.execute(
                        f"UPDATE students SET {column} = ? WHERE id = ?",
                        (json.dumps(inner), row_id),
                    )
                    fixed += 1
            except json.JSONDecodeError:
                continue

    return fixed


def main():
    conn = sqlite3.connect(DB_PATH)

    ec_fixed = fix_double_encoded(conn, "ec_tags")
    print(f"Fixed {ec_fixed} double-encoded ec_tags rows")

    circ_fixed = fix_double_encoded(conn, "circumstance_tags")
    print(f"Fixed {circ_fixed} double-encoded circumstance_tags rows")

    conn.commit()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script**

Run: `python3 scripts/fix_double_encoded_tags.py`
Expected: Output showing ~415 ec_tags rows fixed (the REDDIT_SCRAPED rows)

- [ ] **Step 3: Verify the fix**

Run:
```bash
python3 -c "
import sqlite3, json
conn = sqlite3.connect('database/unipath.db')
rows = conn.execute('SELECT ec_tags FROM students WHERE source = \"REDDIT_SCRAPED\" LIMIT 5').fetchall()
for (ec,) in rows:
    parsed = json.loads(ec)
    print(parsed, type(parsed), type(parsed[0]) if parsed else 'empty')
conn.close()
"
```
Expected: Each row prints a list of strings like `['NONE']` or `['SPORTS', 'ARTS']`, where each element is a `str`, not a nested JSON string.

- [ ] **Step 4: Commit**

```bash
git add scripts/fix_double_encoded_tags.py
git commit -m "fix: resolve double-encoded ec_tags/circumstance_tags on Reddit rows"
```

---

## Task 2: Build the LLM eval framework

The eval framework compares three extraction configurations on hand-labeled data. This is both a quality gate for model selection and a portfolio artifact.

**Files:**
- Create: `eval/schemas.py`
- Create: `eval/metrics.py`
- Create: `eval/runner.py`
- Create: `eval/ground_truth.jsonl` (manually curated)

- [ ] **Step 1: Create the Pydantic extraction schema**

```python
# eval/schemas.py
"""Pydantic schema for Reddit admission extraction. Shared by eval and reddit_agent."""
from pydantic import BaseModel
from typing import Literal, Optional


class AdmissionExtraction(BaseModel):
    relevant: bool
    school: Optional[str] = None
    program: Optional[str] = None
    decision: Optional[Literal["Accepted", "Rejected", "Waitlisted", "Deferred"]] = None
    core_avg: Optional[float] = None
    ec_raw: Optional[str] = None
    province: Optional[str] = None
    citizenship: Optional[str] = None
```

- [ ] **Step 2: Create the metrics module**

```python
# eval/metrics.py
"""Scoring functions for extraction eval."""
from eval.schemas import AdmissionExtraction


FIELDS = ["school", "program", "decision", "core_avg", "ec_raw", "province", "citizenship"]


def field_accuracy(predicted: AdmissionExtraction, truth: AdmissionExtraction) -> dict[str, bool]:
    """Returns a dict of field_name -> whether predicted matches truth."""
    results = {}
    for field in FIELDS:
        pred_val = getattr(predicted, field)
        true_val = getattr(truth, field)
        if true_val is None:
            # If ground truth is None, prediction should also be None
            results[field] = pred_val is None
        elif field == "core_avg" and pred_val is not None and true_val is not None:
            # Float comparison with tolerance
            results[field] = abs(pred_val - true_val) <= 1.0
        elif isinstance(true_val, str) and isinstance(pred_val, str):
            results[field] = pred_val.strip().lower() == true_val.strip().lower()
        else:
            results[field] = pred_val == true_val
    return results


def relevance_accuracy(predicted: AdmissionExtraction, truth: AdmissionExtraction) -> bool:
    """Whether predicted.relevant matches truth.relevant."""
    return predicted.relevant == truth.relevant
```

- [ ] **Step 3: Create the eval runner**

```python
# eval/runner.py
"""
Ablation eval runner. Tests 3 configurations on ground truth data:
  A: llama3.2:3b + free-form
  B: llama3.2:3b + structured output
  C: qwen3:4b + structured output

Usage: python3 -m eval.runner
"""
import json
import time
import ollama
from pathlib import Path
from eval.schemas import AdmissionExtraction
from eval.metrics import field_accuracy, relevance_accuracy, FIELDS
from pipeline.reddit_agent import EXTRACTION_PROMPT

GROUND_TRUTH_PATH = Path(__file__).parent / "ground_truth.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"

CONFIGS = {
    "A_llama_freeform": {"model": "llama3.2", "structured": False},
    "B_llama_structured": {"model": "llama3.2", "structured": True},
    "C_qwen3_structured": {"model": "qwen3:4b", "structured": True},
}


def extract_freeform(model: str, post_text: str) -> AdmissionExtraction | None:
    """Extract using free-form JSON (current approach)."""
    prompt = EXTRACTION_PROMPT.format(post_text=post_text[:2000])
    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0},
        )
        raw = response["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        data = json.loads(raw)
        return AdmissionExtraction(**data)
    except Exception:
        return None


def extract_structured(model: str, post_text: str) -> AdmissionExtraction | None:
    """Extract using Ollama structured output mode."""
    prompt = EXTRACTION_PROMPT.format(post_text=post_text[:2000])
    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            format=AdmissionExtraction.model_json_schema(),
            options={"temperature": 0},
        )
        raw = response["message"]["content"].strip()
        return AdmissionExtraction.model_validate_json(raw)
    except Exception as e:
        print(f"  Extraction error: {e}")
        return None


def run_config(name: str, config: dict, records: list[dict]) -> dict:
    """Run a single config against all records, return aggregated metrics."""
    extract_fn = extract_structured if config["structured"] else extract_freeform
    model = config["model"]

    total = len(records)
    json_valid = 0
    relevance_correct = 0
    field_correct = {f: 0 for f in FIELDS}
    field_total = {f: 0 for f in FIELDS}
    latencies = []

    predictions = []

    for i, record in enumerate(records):
        post_text = record["post_text"]
        truth = AdmissionExtraction(**record["expected"])

        start = time.time()
        predicted = extract_fn(model, post_text)
        elapsed = time.time() - start
        latencies.append(elapsed)

        if predicted is None:
            predictions.append({"index": i, "predicted": None, "valid": False})
            continue

        json_valid += 1
        predictions.append({
            "index": i,
            "predicted": predicted.model_dump(),
            "valid": True,
        })

        if relevance_accuracy(predicted, truth):
            relevance_correct += 1

        if truth.relevant and predicted.relevant:
            acc = field_accuracy(predicted, truth)
            for field, correct in acc.items():
                field_total[field] += 1
                if correct:
                    field_correct[field] += 1

        print(f"  [{name}] {i+1}/{total} ({elapsed:.1f}s)")

    results = {
        "config": name,
        "model": model,
        "structured": config["structured"],
        "total": total,
        "json_valid": json_valid,
        "json_valid_pct": round(json_valid / total * 100, 1),
        "relevance_accuracy_pct": round(relevance_correct / total * 100, 1),
        "field_accuracy": {
            f: round(field_correct[f] / field_total[f] * 100, 1) if field_total[f] > 0 else None
            for f in FIELDS
        },
        "avg_latency_s": round(sum(latencies) / len(latencies), 2) if latencies else 0,
        "total_time_s": round(sum(latencies), 1),
        "predictions": predictions,
    }
    return results


def main():
    if not GROUND_TRUTH_PATH.exists():
        print(f"Ground truth not found at {GROUND_TRUTH_PATH}")
        print("Create ground_truth.jsonl with hand-labeled records first.")
        return

    records = [json.loads(line) for line in GROUND_TRUTH_PATH.read_text().strip().splitlines()]
    print(f"Loaded {len(records)} ground truth records\n")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    all_results = {}
    for name, config in CONFIGS.items():
        print(f"\n{'='*50}")
        print(f"Running config: {name} (model={config['model']}, structured={config['structured']})")
        print(f"{'='*50}")
        results = run_config(name, config, records)
        all_results[name] = results

        # Save individual results
        result_path = RESULTS_DIR / f"{name}.json"
        result_path.write_text(json.dumps(results, indent=2))
        print(f"  Saved to {result_path}")

    # Print comparison table
    print(f"\n\n{'='*70}")
    print("COMPARISON SUMMARY")
    print(f"{'='*70}")
    print(f"{'Config':<25} {'JSON Valid':>10} {'Relevance':>10} {'Avg Latency':>12}")
    print("-" * 70)
    for name, r in all_results.items():
        print(f"{name:<25} {r['json_valid_pct']:>9}% {r['relevance_accuracy_pct']:>9}% {r['avg_latency_s']:>10}s")

    print(f"\nField-level accuracy:")
    print(f"{'Config':<25}", end="")
    for f in FIELDS:
        print(f" {f:>10}", end="")
    print()
    print("-" * (25 + 11 * len(FIELDS)))
    for name, r in all_results.items():
        print(f"{name:<25}", end="")
        for f in FIELDS:
            val = r["field_accuracy"][f]
            print(f" {val:>9}%" if val is not None else f" {'N/A':>10}", end="")
        print()

    # Save comparison
    comparison_path = RESULTS_DIR / "comparison.json"
    comparison_path.write_text(json.dumps(all_results, indent=2))
    print(f"\nFull results saved to {comparison_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Create ground truth template**

Create `eval/ground_truth.jsonl` with at least 5 seed records. The full 50 will be hand-labeled by pulling Reddit post texts from the DB and verifying each extraction against the original post.

Each line is a JSON object:
```json
{"post_text": "Got into UBC Engineering with a 94.5 average! Had robotics club, volunteering, and played varsity basketball. From BC, Canadian citizen.", "expected": {"relevant": true, "school": "UBC", "program": "Engineering", "decision": "Accepted", "core_avg": 94.5, "ec_raw": "robotics club, volunteering, varsity basketball", "province": "BC", "citizenship": "Canadian"}}
{"post_text": "What are my chances for Waterloo CS with a 95?", "expected": {"relevant": false, "school": null, "program": null, "decision": null, "core_avg": null, "ec_raw": null, "province": null, "citizenship": null}}
```

- [ ] **Step 5: Verify the eval framework runs**

Run: `python3 -m eval.runner`
Expected: Runs against seed records, prints comparison table. Config A may be slow. JSON validity for Config B and C should be 100%.

- [ ] **Step 6: Commit**

```bash
git add eval/
git commit -m "feat: add LLM extraction eval framework (ablation: llama freeform vs structured vs qwen3)"
```

---

## Task 3: Hand-label 50 ground truth records

This is a manual curation task. Pull Reddit post texts from the DB, find the original posts via stored URLs, and verify/correct each extraction.

**Files:**
- Modify: `eval/ground_truth.jsonl`

- [ ] **Step 1: Extract candidate posts from DB**

```bash
python3 -c "
import sqlite3, json
conn = sqlite3.connect('database/unipath.db')
rows = conn.execute('''
    SELECT id, school_normalized, program_category, decision, core_avg, ec_raw, province, citizenship
    FROM students
    WHERE source = 'REDDIT_SCRAPED'
    ORDER BY RANDOM()
    LIMIT 60
''').fetchall()
for r in rows:
    print(json.dumps({'id': r[0], 'school': r[1], 'program': r[2], 'decision': r[3], 'core_avg': r[4], 'ec_raw': r[5], 'province': r[6], 'citizenship': r[7]}))
conn.close()
"
```

- [ ] **Step 2: For each candidate, find the original post text**

The scraper doesn't store post text in the DB. You'll need to re-fetch a sample of posts from Reddit to get the source text. Alternatively, run the scraper in a dry-run mode that prints post text without inserting. Use the extracted fields as a starting point and manually verify correctness.

- [ ] **Step 3: Build 50 labeled records in `eval/ground_truth.jsonl`**

Include a mix of:
- ~30 relevant posts (with real admission data)
- ~10 irrelevant posts (questions, advice-seeking, hypotheticals)
- ~10 edge cases (multiple schools mentioned, IB scores, ambiguous programs)

- [ ] **Step 4: Commit**

```bash
git add eval/ground_truth.jsonl
git commit -m "feat: add 50 hand-labeled ground truth records for extraction eval"
```

---

## Task 4: Run the eval and select model

**Files:**
- Read: `eval/results/comparison.json`

- [ ] **Step 1: Pull models**

```bash
ollama pull llama3.2
ollama pull qwen3:4b
```

- [ ] **Step 2: Run the full eval**

Run: `python3 -m eval.runner`
Expected: Takes 15-30 minutes. Prints comparison table at the end.

- [ ] **Step 3: Analyze results**

Decision rule:
- If Config B (llama structured) matches Config C (qwen3 structured) on field accuracy within 5%, stay on llama3.2 (simpler)
- If Config C is meaningfully better, switch to qwen3:4b
- JSON validity for B and C should both be 100% (structured output guarantees it)
- Config A (freeform) is the baseline — expect it to be worst

- [ ] **Step 4: Document the decision**

Create `eval/DECISION.md` with the comparison table, analysis, and which config was chosen and why.

- [ ] **Step 5: Commit**

```bash
git add eval/results/ eval/DECISION.md
git commit -m "feat: document model eval results and selection decision"
```

---

## Task 5: Migrate reddit_agent.py to structured output

Apply the eval winner to the production scraper.

**Files:**
- Modify: `pipeline/reddit_agent.py`
- Reference: `eval/schemas.py`

- [ ] **Step 1: Write test for structured extraction**

```python
# tests/test_reddit_agent.py
import pytest
from unittest.mock import patch
from pipeline.reddit_agent import extract_admission_data, is_valid_extraction


def test_structured_extraction_returns_valid_dict():
    """Structured output mode returns a dict with expected fields."""
    mock_response = {
        "message": {
            "content": '{"relevant": true, "school": "UBC", "program": "Engineering", "decision": "Accepted", "core_avg": 94.5, "ec_raw": null, "province": null, "citizenship": null}'
        }
    }
    with patch("pipeline.reddit_agent.ollama.chat", return_value=mock_response):
        result = extract_admission_data("Got into UBC Engineering with a 94.5!")
    assert result is not None
    assert result["relevant"] is True
    assert result["school"] == "UBC"
    assert result["core_avg"] == 94.5


def test_structured_extraction_irrelevant_post():
    """Irrelevant post returns relevant=False."""
    mock_response = {
        "message": {
            "content": '{"relevant": false, "school": null, "program": null, "decision": null, "core_avg": null, "ec_raw": null, "province": null, "citizenship": null}'
        }
    }
    with patch("pipeline.reddit_agent.ollama.chat", return_value=mock_response):
        result = extract_admission_data("What are my chances for Waterloo CS?")
    assert result is not None
    assert result["relevant"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_reddit_agent.py -v`
Expected: FAIL — `extract_admission_data` doesn't exist with the new signature yet (or it still uses freeform)

- [ ] **Step 3: Update reddit_agent.py**

Replace `extract_admission_data()` to use structured output. Replace the model name with the eval winner. Key changes:

```python
# At top of pipeline/reddit_agent.py, add:
from eval.schemas import AdmissionExtraction

# Replace extract_admission_data:
def extract_admission_data(post_text: str) -> dict | None:
    """
    Uses Ollama structured output to extract admissions data.
    Returns a dict if extraction succeeded, None on failure.
    """
    prompt = EXTRACTION_PROMPT.format(post_text=post_text[:2000])

    try:
        response = ollama.chat(
            model="qwen3:4b",  # or llama3.2 — whichever won the eval
            messages=[{"role": "user", "content": prompt}],
            format=AdmissionExtraction.model_json_schema(),
            options={"temperature": 0, "num_ctx": 4096},
        )
        raw = response["message"]["content"].strip()
        parsed = AdmissionExtraction.model_validate_json(raw)
        return parsed.model_dump()
    except Exception as e:
        print(f"    Extraction error: {e}")
        return None
```

Also add `r/AlbertaGrade12s` to the `SUBREDDITS` list:
```python
SUBREDDITS = ["OntarioGrade12s", "BCGrade12s", "AlbertaGrade12s"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_reddit_agent.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/reddit_agent.py eval/schemas.py tests/test_reddit_agent.py
git commit -m "feat: migrate reddit_agent to Ollama structured output + add AlbertaGrade12s"
```

---

## Task 6: Add program stats API endpoint

The frontend needs aggregated stats per school+program combo. Add endpoints to the FastAPI server.

**Files:**
- Modify: `core/recommend.py`
- Modify: `server/main.py`
- Create: `tests/test_program_stats.py`

- [ ] **Step 1: Write the test for program_stats**

```python
# tests/test_program_stats.py
import pytest
import sqlite3
import json
from core.recommend import program_stats, list_programs


def test_program_stats_returns_expected_shape():
    """program_stats returns grade buckets, ec breakdown, and key stats."""
    result = program_stats("UBC Vancouver", "ENGINEERING")
    assert "grade_distribution" in result
    assert "ec_breakdown" in result
    assert "total_records" in result
    assert "avg_admitted_grade" in result
    assert result["total_records"] > 0


def test_program_stats_grade_distribution_has_buckets():
    """Grade distribution has accepted/rejected counts per bucket."""
    result = program_stats("UBC Vancouver", "ENGINEERING")
    dist = result["grade_distribution"]
    assert isinstance(dist, list)
    assert len(dist) > 0
    first = dist[0]
    assert "bucket" in first
    assert "accepted" in first
    assert "rejected" in first


def test_program_stats_ec_breakdown_has_percentages():
    """EC breakdown shows tag names with percentage of admitted students."""
    result = program_stats("UBC Vancouver", "ENGINEERING")
    ec = result["ec_breakdown"]
    assert isinstance(ec, list)
    # Each entry has tag and pct
    for entry in ec:
        assert "tag" in entry
        assert "pct" in entry
        assert 0 <= entry["pct"] <= 100


def test_program_stats_unknown_combo_returns_empty():
    """Unknown school+program returns zero records."""
    result = program_stats("Fake University", "FAKE_PROGRAM")
    assert result["total_records"] == 0


def test_list_programs_returns_non_empty():
    """list_programs returns a list of combos with record counts."""
    result = list_programs()
    assert isinstance(result, list)
    assert len(result) > 0
    first = result[0]
    assert "school" in first
    assert "program" in first
    assert "total" in first
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_program_stats.py -v`
Expected: FAIL — `program_stats` and `list_programs` don't exist yet

- [ ] **Step 3: Implement program_stats and list_programs in recommend.py**

Add to `core/recommend.py`:

```python
import json as _json

GRADE_BUCKETS = [
    ("< 80", 0, 79.99),
    ("80-84", 80, 84.99),
    ("85-89", 85, 89.99),
    ("90-94", 90, 94.99),
    ("95-100", 95, 100),
]


def program_stats(school: str, program_category: str) -> dict:
    """
    Returns aggregated stats for a school+program combo:
    - grade_distribution: list of {bucket, accepted, rejected, waitlisted, deferred}
    - ec_breakdown: list of {tag, pct} among accepted students
    - total_records, avg_admitted_grade, grade_range, data_sources
    """
    conn = get_connection()
    program_category = program_category.upper()

    # All rows for this combo
    rows = conn.execute(
        "SELECT decision, core_avg, ec_tags, source FROM students "
        "WHERE school_normalized = ? AND program_category = ? AND core_avg IS NOT NULL",
        (school, program_category),
    ).fetchall()
    conn.close()

    if not rows:
        return {
            "school": school,
            "program": program_category,
            "grade_distribution": [],
            "ec_breakdown": [],
            "total_records": 0,
            "avg_admitted_grade": None,
            "grade_range": None,
            "data_sources": {},
        }

    # Grade distribution
    grade_dist = []
    for label, lo, hi in GRADE_BUCKETS:
        bucket = {"bucket": label, "accepted": 0, "rejected": 0, "waitlisted": 0, "deferred": 0}
        for decision, grade, _, _ in rows:
            if lo <= grade <= hi and decision:
                key = decision.lower()
                if key in bucket:
                    bucket[key] += 1
        grade_dist.append(bucket)

    # EC breakdown (accepted students only)
    from collections import Counter
    ec_counter = Counter()
    accepted_count = 0
    accepted_grades = []

    for decision, grade, ec_tags_str, source in rows:
        if decision == "ACCEPTED":
            accepted_count += 1
            accepted_grades.append(grade)
            if ec_tags_str:
                try:
                    tags = _json.loads(ec_tags_str)
                    for tag in tags:
                        if tag not in ("NONE", "OTHER"):
                            ec_counter[tag] += 1
                except (_json.JSONDecodeError, TypeError):
                    pass

    ec_breakdown = [
        {"tag": tag, "count": count, "pct": round(count / accepted_count * 100)}
        for tag, count in ec_counter.most_common()
    ] if accepted_count > 0 else []

    # Data sources
    source_counter = Counter(source for _, _, _, source in rows)

    return {
        "school": school,
        "program": program_category,
        "grade_distribution": grade_dist,
        "ec_breakdown": ec_breakdown,
        "total_records": len(rows),
        "accepted_count": accepted_count,
        "avg_admitted_grade": round(sum(accepted_grades) / len(accepted_grades), 1) if accepted_grades else None,
        "grade_range": {
            "min": round(min(accepted_grades), 1),
            "max": round(max(accepted_grades), 1),
        } if accepted_grades else None,
        "data_sources": dict(source_counter),
    }


def list_programs(min_records: int = 10) -> list[dict]:
    """
    Returns all school+program combos with at least min_records,
    sorted by total descending.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT school_normalized, program_category, COUNT(*) as cnt, "
        "SUM(CASE WHEN decision = 'ACCEPTED' THEN 1 ELSE 0 END) as accepted "
        "FROM students "
        "WHERE school_normalized IS NOT NULL AND program_category IS NOT NULL "
        "AND core_avg IS NOT NULL "
        "GROUP BY school_normalized, program_category "
        "HAVING cnt >= ? "
        "ORDER BY cnt DESC",
        (min_records,),
    ).fetchall()
    conn.close()

    return [
        {
            "school": school,
            "program": program,
            "total": total,
            "accepted": accepted,
        }
        for school, program, total, accepted in rows
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_program_stats.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Add FastAPI endpoints**

Add to `server/main.py`:

```python
from core.recommend import program_stats, list_programs

@app.get("/programs")
def get_programs():
    return list_programs(min_records=10)


@app.get("/programs/{school}/{program}")
def get_program_stats(school: str, program: str):
    result = program_stats(school, program.upper())
    if result["total_records"] == 0:
        return {"error": "no_data"}
    return result
```

- [ ] **Step 6: Commit**

```bash
git add core/recommend.py server/main.py tests/test_program_stats.py
git commit -m "feat: add program_stats API for grade distributions and EC breakdowns"
```

---

## Task 7: Add submission endpoint

Anonymous submission form that feeds through the existing pipeline.

**Files:**
- Modify: `server/main.py`
- Create: `tests/test_submit.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_submit.py
import pytest
from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)


def test_submit_valid_outcome():
    """Valid submission returns success."""
    response = client.post("/submit-outcome", json={
        "school": "UBC",
        "program": "Engineering",
        "grade": 94.5,
        "decision": "Accepted",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_submit_invalid_grade_rejected():
    """Grade outside 50-100 is rejected."""
    response = client.post("/submit-outcome", json={
        "school": "UBC",
        "program": "Engineering",
        "grade": 105,
        "decision": "Accepted",
    })
    assert response.status_code == 422 or response.json().get("error")


def test_submit_invalid_decision_rejected():
    """Invalid decision string is rejected."""
    response = client.post("/submit-outcome", json={
        "school": "UBC",
        "program": "Engineering",
        "grade": 90,
        "decision": "Maybe",
    })
    assert response.status_code == 422 or response.json().get("error")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_submit.py -v`
Expected: FAIL — `/submit-outcome` endpoint doesn't exist

- [ ] **Step 3: Implement the endpoint**

Add to `server/main.py`:

```python
from typing import Literal, Optional
from pipeline.normalize import normalize_school, normalize_decision, normalize_province, normalize_citizenship
from pipeline.extract_fields import tag_program, tag_ec, tag_circumstances
from database.models import Student, init_db
from sqlalchemy.orm import Session
import json


class SubmitOutcomeRequest(BaseModel):
    school: str
    program: str
    grade: float
    decision: Literal["Accepted", "Rejected", "Waitlisted", "Deferred"]
    ecs: Optional[str] = None
    province: Optional[str] = None


_engine = None

def _get_engine():
    global _engine
    if _engine is None:
        _engine = init_db()
    return _engine


@app.post("/submit-outcome")
def submit_outcome(req: SubmitOutcomeRequest):
    # Validate grade range
    if not (50 <= req.grade <= 100):
        return {"error": "grade_out_of_range"}

    # Normalize school
    school_normalized, multi = normalize_school(req.school)
    if school_normalized is None:
        return {"error": "unknown_school"}

    # Normalize fields
    decision = normalize_decision(req.decision)
    province = normalize_province(req.province) if req.province else None
    program_category = tag_program(req.program)
    ec_tags = json.dumps(tag_ec(req.ecs)) if req.ecs else json.dumps(["NONE"])
    circumstance_tags = json.dumps(["NONE"])

    student = Student(
        source="USER_SUBMITTED",
        school_raw=req.school,
        school_normalized=school_normalized,
        multi_school_flag=multi,
        program_raw=req.program,
        program_category=program_category,
        decision=decision,
        core_avg=req.grade,
        ec_raw=req.ecs,
        ec_tags=ec_tags,
        circumstance_tags=circumstance_tags,
        province=province,
    )

    engine = _get_engine()
    with Session(engine) as session:
        session.add(student)
        session.commit()

    return {"status": "ok", "school_normalized": school_normalized, "program_category": program_category}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_submit.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/main.py tests/test_submit.py
git commit -m "feat: add anonymous /submit-outcome endpoint"
```

---

## Task 8: Rewrite frontend home page (browse grid)

Replace the odds calculator landing page with a browsable grid of program cards.

**Files:**
- Rewrite: `frontend/app/page.tsx`
- Create: `frontend/components/ProgramCard.tsx`
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/app/layout.tsx`

**Important:** Read `node_modules/next/dist/docs/` before writing any Next.js code — this is Next.js 16 with possible breaking changes from training data.

- [ ] **Step 1: Check Next.js 16 docs for app router conventions**

Run: `ls frontend/node_modules/next/dist/docs/` and read any relevant files for data fetching and routing patterns.

- [ ] **Step 2: Add new types**

Add to `frontend/lib/types.ts`:

```typescript
export interface ProgramSummary {
  school: string
  program: string
  total: number
  accepted: number
}

export interface GradeBucket {
  bucket: string
  accepted: number
  rejected: number
  waitlisted: number
  deferred: number
}

export interface ECEntry {
  tag: string
  count: number
  pct: number
}

export interface ProgramStats {
  school: string
  program: string
  grade_distribution: GradeBucket[]
  ec_breakdown: ECEntry[]
  total_records: number
  accepted_count: number
  avg_admitted_grade: number | null
  grade_range: { min: number; max: number } | null
  data_sources: Record<string, number>
}
```

- [ ] **Step 3: Create ProgramCard component**

```tsx
// frontend/components/ProgramCard.tsx
import Link from 'next/link'

interface Props {
  school: string
  program: string
  total: number
  accepted: number
}

const PROGRAM_LABELS: Record<string, string> = {
  ENGINEERING: 'Engineering',
  SCIENCE: 'Science',
  BUSINESS: 'Business',
  COMPUTER_SCIENCE: 'Computer Science',
  HEALTH: 'Health Sciences',
  ARTS: 'Arts',
}

export default function ProgramCard({ school, program, total, accepted }: Props) {
  const acceptRate = total > 0 ? Math.round((accepted / total) * 100) : 0
  const slug = `${encodeURIComponent(school)}/${encodeURIComponent(program)}`

  return (
    <Link
      href={`/program/${slug}`}
      className="block p-5 rounded-xl border border-white/10 bg-white/[0.03]
                 hover:bg-white/[0.06] hover:border-white/20 transition-all duration-200"
    >
      <p className="text-xs text-white/40 uppercase tracking-wide mb-1">{school}</p>
      <h3 className="text-lg font-medium text-[#f5f5f0] mb-3">
        {PROGRAM_LABELS[program] ?? program}
      </h3>
      <div className="flex items-center gap-4 text-sm text-white/50">
        <span>{total} records</span>
        <span>{acceptRate}% accepted</span>
      </div>
    </Link>
  )
}
```

- [ ] **Step 4: Rewrite the home page**

```tsx
// frontend/app/page.tsx
import ProgramCard from '@/components/ProgramCard'
import { ProgramSummary } from '@/lib/types'

const API_URL = process.env.PYTHON_API_URL ?? 'http://localhost:8000'

async function getPrograms(): Promise<ProgramSummary[]> {
  const res = await fetch(`${API_URL}/programs`, { cache: 'no-store' })
  if (!res.ok) return []
  return res.json()
}

export default async function Home() {
  const programs = await getPrograms()

  return (
    <div className="min-h-screen flex flex-col bg-[#0a0a0a]">
      <div className="flex-1 px-4 pt-16 pb-16 max-w-4xl mx-auto w-full">
        <div className="mb-10">
          <h1 className="font-display text-3xl text-[#f5f5f0] leading-tight">
            See what it actually takes.
          </h1>
          <p className="mt-2 text-sm text-[#f5f5f0]/45">
            Grade distributions and EC patterns from real Canadian applicants.
          </p>
        </div>

        {programs.length === 0 ? (
          <p className="text-white/40">No program data available yet.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {programs.map((p) => (
              <ProgramCard
                key={`${p.school}|${p.program}`}
                school={p.school}
                program={p.program}
                total={p.total}
                accepted={p.accepted}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Update layout metadata**

In `frontend/app/layout.tsx`, change:
```typescript
export const metadata: Metadata = {
  title:       'UniPath — See What It Actually Takes',
  description: 'Grade distributions and EC patterns from real Canadian university applicants.',
}
```

- [ ] **Step 6: Verify it builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds. (Runtime data fetch will fail without the server running, but build should pass.)

- [ ] **Step 7: Commit**

```bash
git add frontend/app/page.tsx frontend/components/ProgramCard.tsx frontend/lib/types.ts frontend/app/layout.tsx
git commit -m "feat: replace odds calculator with program browse grid"
```

---

## Task 9: Build Program Intelligence Page

The core feature — one page per school+program combo showing grade distribution, EC breakdown, and key stats.

**Files:**
- Create: `frontend/app/program/[school]/[program]/page.tsx`
- Create: `frontend/components/GradeDistribution.tsx`
- Create: `frontend/components/ECBreakdown.tsx`

- [ ] **Step 1: Check Next.js 16 dynamic route conventions**

Read the relevant Next.js docs for dynamic `[param]` routes in app router. Verify `params` access patterns haven't changed.

- [ ] **Step 2: Create GradeDistribution component**

```tsx
// frontend/components/GradeDistribution.tsx
'use client'

import { GradeBucket } from '@/lib/types'

interface Props {
  buckets: GradeBucket[]
}

const COLORS = {
  accepted: '#22c55e',
  rejected: '#ef4444',
  waitlisted: '#f59e0b',
  deferred: '#8b5cf6',
}

export default function GradeDistribution({ buckets }: Props) {
  const maxCount = Math.max(
    ...buckets.flatMap(b => [b.accepted, b.rejected, b.waitlisted, b.deferred]),
    1
  )

  return (
    <div>
      <h2 className="text-lg font-medium text-[#f5f5f0] mb-4">Grade Distribution</h2>
      <div className="space-y-3">
        {buckets.map((bucket) => {
          const total = bucket.accepted + bucket.rejected + bucket.waitlisted + bucket.deferred
          if (total === 0) return null
          return (
            <div key={bucket.bucket} className="flex items-center gap-3">
              <span className="text-sm text-white/50 w-16 text-right shrink-0">
                {bucket.bucket}
              </span>
              <div className="flex-1 flex gap-0.5 h-7">
                {(['accepted', 'rejected', 'waitlisted', 'deferred'] as const).map((decision) => {
                  const count = bucket[decision]
                  if (count === 0) return null
                  const widthPct = (count / maxCount) * 100
                  return (
                    <div
                      key={decision}
                      className="h-full rounded-sm flex items-center justify-center text-xs font-medium"
                      style={{
                        width: `${widthPct}%`,
                        minWidth: count > 0 ? '20px' : '0',
                        backgroundColor: COLORS[decision],
                      }}
                    >
                      {count > 0 && count}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
      <div className="flex gap-4 mt-4 text-xs text-white/40">
        {Object.entries(COLORS).map(([label, color]) => (
          <div key={label} className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: color }} />
            <span className="capitalize">{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create ECBreakdown component**

```tsx
// frontend/components/ECBreakdown.tsx
'use client'

import { ECEntry } from '@/lib/types'

interface Props {
  entries: ECEntry[]
  acceptedCount: number
}

const TAG_LABELS: Record<string, string> = {
  SPORTS: 'Sports',
  ARTS: 'Arts & Music',
  LEADERSHIP: 'Leadership',
  COMMUNITY_SERVICE: 'Community Service',
  WORK_EXPERIENCE: 'Work Experience',
  ACADEMIC_COMPETITION: 'Competitions',
  RESEARCH: 'Research',
  ENTREPRENEURSHIP: 'Entrepreneurship',
}

export default function ECBreakdown({ entries, acceptedCount }: Props) {
  if (entries.length === 0) return null

  const maxPct = Math.max(...entries.map(e => e.pct), 1)

  return (
    <div>
      <h2 className="text-lg font-medium text-[#f5f5f0] mb-1">
        What admitted students did
      </h2>
      <p className="text-xs text-white/30 mb-4">
        EC tags among {acceptedCount} accepted applicants
      </p>
      <div className="space-y-2.5">
        {entries.map((entry) => (
          <div key={entry.tag} className="flex items-center gap-3">
            <span className="text-sm text-white/60 w-32 text-right shrink-0">
              {TAG_LABELS[entry.tag] ?? entry.tag}
            </span>
            <div className="flex-1 h-6 bg-white/[0.03] rounded-sm overflow-hidden">
              <div
                className="h-full bg-[#3b82f6]/70 rounded-sm flex items-center px-2"
                style={{ width: `${(entry.pct / maxPct) * 100}%` }}
              >
                <span className="text-xs font-medium text-white/90">{entry.pct}%</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Create the Program Intelligence Page**

```tsx
// frontend/app/program/[school]/[program]/page.tsx
import GradeDistribution from '@/components/GradeDistribution'
import ECBreakdown from '@/components/ECBreakdown'
import Link from 'next/link'
import { ProgramStats } from '@/lib/types'

const API_URL = process.env.PYTHON_API_URL ?? 'http://localhost:8000'

const PROGRAM_LABELS: Record<string, string> = {
  ENGINEERING: 'Engineering',
  SCIENCE: 'Science',
  BUSINESS: 'Business',
  COMPUTER_SCIENCE: 'Computer Science',
  HEALTH: 'Health Sciences',
  ARTS: 'Arts',
}

async function getStats(school: string, program: string): Promise<ProgramStats | null> {
  const res = await fetch(
    `${API_URL}/programs/${encodeURIComponent(school)}/${encodeURIComponent(program)}`,
    { cache: 'no-store' }
  )
  if (!res.ok) return null
  const data = await res.json()
  if (data.error) return null
  return data
}

export default async function ProgramPage({
  params,
}: {
  params: Promise<{ school: string; program: string }>
}) {
  const { school: rawSchool, program: rawProgram } = await params
  const school = decodeURIComponent(rawSchool)
  const program = decodeURIComponent(rawProgram)
  const stats = await getStats(school, program)

  if (!stats || stats.total_records === 0) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-[#0a0a0a] px-4">
        <p className="text-white/40 mb-4">No data available for this program.</p>
        <Link href="/" className="text-[#3b82f6] hover:underline text-sm">
          Back to browse
        </Link>
      </div>
    )
  }

  const sourceTotal = Object.values(stats.data_sources).reduce((a, b) => a + b, 0)
  const sourceLabel = Object.entries(stats.data_sources)
    .map(([src, count]) => {
      if (src === 'REDDIT_SCRAPED') return `${count} Reddit posts`
      if (src === 'USER_SUBMITTED') return `${count} submissions`
      return `${count} ${src} records`
    })
    .join(' + ')

  return (
    <div className="min-h-screen flex flex-col bg-[#0a0a0a]">
      <div className="flex-1 px-4 pt-12 pb-16 max-w-3xl mx-auto w-full">
        {/* Back link */}
        <Link href="/" className="text-sm text-white/30 hover:text-white/50 transition-colors">
          &larr; All programs
        </Link>

        {/* Header */}
        <div className="mt-6 mb-10">
          <p className="text-xs text-white/40 uppercase tracking-wide mb-1">{school}</p>
          <h1 className="font-display text-3xl text-[#f5f5f0]">
            {PROGRAM_LABELS[program] ?? program}
          </h1>
        </div>

        {/* Key stats */}
        <div className="grid grid-cols-3 gap-4 mb-10">
          <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03]">
            <p className="text-2xl font-medium text-[#f5f5f0]">{stats.total_records}</p>
            <p className="text-xs text-white/40 mt-1">Records</p>
          </div>
          {stats.avg_admitted_grade && (
            <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03]">
              <p className="text-2xl font-medium text-[#f5f5f0]">{stats.avg_admitted_grade}%</p>
              <p className="text-xs text-white/40 mt-1">Avg admitted grade</p>
            </div>
          )}
          {stats.grade_range && (
            <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03]">
              <p className="text-2xl font-medium text-[#f5f5f0]">
                {stats.grade_range.min}–{stats.grade_range.max}%
              </p>
              <p className="text-xs text-white/40 mt-1">Admitted range</p>
            </div>
          )}
        </div>

        {/* Grade distribution */}
        <div className="mb-10 p-6 rounded-xl border border-white/10 bg-white/[0.03]">
          <GradeDistribution buckets={stats.grade_distribution} />
        </div>

        {/* EC breakdown */}
        {stats.ec_breakdown.length > 0 && (
          <div className="mb-10 p-6 rounded-xl border border-white/10 bg-white/[0.03]">
            <ECBreakdown entries={stats.ec_breakdown} acceptedCount={stats.accepted_count} />
          </div>
        )}

        {/* Data provenance */}
        <div className="text-xs text-white/20 text-center mt-8">
          Based on {sourceLabel}
          {stats.total_records < 20 && (
            <span className="block mt-1 text-yellow-500/50">
              Limited data — take insights with a grain of salt
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Verify it builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/program/ frontend/components/GradeDistribution.tsx frontend/components/ECBreakdown.tsx
git commit -m "feat: add Program Intelligence Page with grade distribution and EC breakdown"
```

---

## Task 10: Add "Where Do You Stand?" section

Collapsible section on the Program Intelligence Page where students enter their grade and see where they fall.

**Files:**
- Create: `frontend/components/WhereDoYouStand.tsx`
- Modify: `frontend/app/program/[school]/[program]/page.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/components/WhereDoYouStand.tsx
'use client'

import { useState } from 'react'

interface Props {
  avgAdmittedGrade: number | null
  gradeRange: { min: number; max: number } | null
  totalRecords: number
}

export default function WhereDoYouStand({ avgAdmittedGrade, gradeRange, totalRecords }: Props) {
  const [open, setOpen] = useState(false)
  const [grade, setGrade] = useState('')

  const gradeNum = parseFloat(grade)
  const valid = !isNaN(gradeNum) && gradeNum >= 50 && gradeNum <= 100

  let position: string | null = null
  if (valid && avgAdmittedGrade && gradeRange) {
    if (gradeNum >= gradeRange.max) {
      position = 'above the highest admitted grade on record'
    } else if (gradeNum >= avgAdmittedGrade) {
      position = 'above the average admitted grade'
    } else if (gradeNum >= gradeRange.min) {
      position = 'within the admitted range, but below average'
    } else {
      position = 'below the lowest admitted grade on record'
    }
  }

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-white/[0.02] transition-colors"
      >
        <span className="text-sm font-medium text-[#f5f5f0]">Where do you stand?</span>
        <span className="text-white/30 text-lg">{open ? '−' : '+'}</span>
      </button>

      {open && (
        <div className="px-6 pb-6 pt-2">
          <p className="text-xs text-white/40 mb-3">
            Enter your grade to see where you fall among admitted students.
          </p>
          <input
            type="number"
            min={50}
            max={100}
            step={0.1}
            value={grade}
            onChange={(e) => setGrade(e.target.value)}
            placeholder="Your average (e.g. 92.5)"
            className="w-full px-4 py-3 rounded-lg bg-white/[0.05] border border-white/10
                       text-[#f5f5f0] text-sm placeholder:text-white/20
                       focus:outline-none focus:border-white/30 transition-colors"
          />

          {valid && position && (
            <div className="mt-4 p-4 rounded-lg bg-white/[0.03] border border-white/10">
              <p className="text-sm text-[#f5f5f0]">
                With a <strong>{gradeNum}%</strong> average, you&apos;re {position}.
              </p>
              {avgAdmittedGrade && (
                <p className="text-xs text-white/30 mt-2">
                  Average admitted grade: {avgAdmittedGrade}%
                  {gradeRange && ` (range: ${gradeRange.min}–${gradeRange.max}%)`}
                </p>
              )}
            </div>
          )}

          {totalRecords < 20 && (
            <p className="text-xs text-yellow-500/50 mt-3">
              Based on limited data ({totalRecords} records). Results may not be representative.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Add to Program Intelligence Page**

In `frontend/app/program/[school]/[program]/page.tsx`, add after the EC breakdown section:

```tsx
import WhereDoYouStand from '@/components/WhereDoYouStand'

// ... inside the return, after the EC breakdown div:
        {/* Where Do You Stand */}
        <div className="mb-10">
          <WhereDoYouStand
            avgAdmittedGrade={stats.avg_admitted_grade}
            gradeRange={stats.grade_range}
            totalRecords={stats.total_records}
          />
        </div>
```

- [ ] **Step 3: Verify it builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/WhereDoYouStand.tsx frontend/app/program/
git commit -m "feat: add 'Where Do You Stand?' collapsible section to program page"
```

---

## Task 11: Add submission form (inline + standalone)

**Files:**
- Create: `frontend/components/SubmitOutcomeForm.tsx`
- Create: `frontend/app/submit/page.tsx`
- Modify: `frontend/app/program/[school]/[program]/page.tsx`

- [ ] **Step 1: Create the form component**

```tsx
// frontend/components/SubmitOutcomeForm.tsx
'use client'

import { useState } from 'react'

interface Props {
  defaultSchool?: string
  defaultProgram?: string
}

const API_URL = process.env.NEXT_PUBLIC_PYTHON_API_URL ?? 'http://localhost:8000'

export default function SubmitOutcomeForm({ defaultSchool, defaultProgram }: Props) {
  const [school, setSchool] = useState(defaultSchool ?? '')
  const [program, setProgram] = useState(defaultProgram ?? '')
  const [grade, setGrade] = useState('')
  const [decision, setDecision] = useState('')
  const [ecs, setEcs] = useState('')
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle')

  const gradeNum = parseFloat(grade)
  const canSubmit = school && program && !isNaN(gradeNum) && gradeNum >= 50 && gradeNum <= 100 && decision

  async function handleSubmit() {
    if (!canSubmit) return
    setStatus('submitting')
    try {
      const res = await fetch(`${API_URL}/submit-outcome`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          school,
          program,
          grade: gradeNum,
          decision,
          ecs: ecs || undefined,
        }),
      })
      const data = await res.json()
      if (data.error) throw new Error(data.error)
      setStatus('success')
    } catch {
      setStatus('error')
    }
  }

  if (status === 'success') {
    return (
      <div className="p-6 rounded-xl border border-green-500/20 bg-green-500/[0.05] text-center">
        <p className="text-sm text-green-400">Thanks for contributing! Your data helps future applicants.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium text-[#f5f5f0]">Got your result? Add your outcome.</h3>
      <p className="text-xs text-white/30">Anonymous. Helps future applicants.</p>

      <div className="grid grid-cols-2 gap-3">
        <input
          type="text"
          value={school}
          onChange={(e) => setSchool(e.target.value)}
          placeholder="School (e.g. UBC)"
          className="px-3 py-2.5 rounded-lg bg-white/[0.05] border border-white/10
                     text-sm text-[#f5f5f0] placeholder:text-white/20
                     focus:outline-none focus:border-white/30"
        />
        <input
          type="text"
          value={program}
          onChange={(e) => setProgram(e.target.value)}
          placeholder="Program (e.g. Engineering)"
          className="px-3 py-2.5 rounded-lg bg-white/[0.05] border border-white/10
                     text-sm text-[#f5f5f0] placeholder:text-white/20
                     focus:outline-none focus:border-white/30"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <input
          type="number"
          min={50}
          max={100}
          step={0.1}
          value={grade}
          onChange={(e) => setGrade(e.target.value)}
          placeholder="Your average (50-100)"
          className="px-3 py-2.5 rounded-lg bg-white/[0.05] border border-white/10
                     text-sm text-[#f5f5f0] placeholder:text-white/20
                     focus:outline-none focus:border-white/30"
        />
        <select
          value={decision}
          onChange={(e) => setDecision(e.target.value)}
          className="px-3 py-2.5 rounded-lg bg-white/[0.05] border border-white/10
                     text-sm text-[#f5f5f0]
                     focus:outline-none focus:border-white/30"
        >
          <option value="">Decision...</option>
          <option value="Accepted">Accepted</option>
          <option value="Rejected">Rejected</option>
          <option value="Waitlisted">Waitlisted</option>
          <option value="Deferred">Deferred</option>
        </select>
      </div>

      <textarea
        value={ecs}
        onChange={(e) => setEcs(e.target.value)}
        placeholder="Extracurriculars (optional — e.g. robotics club, volunteering, varsity basketball)"
        rows={2}
        className="w-full px-3 py-2.5 rounded-lg bg-white/[0.05] border border-white/10
                   text-sm text-[#f5f5f0] placeholder:text-white/20
                   focus:outline-none focus:border-white/30 resize-none"
      />

      <button
        onClick={handleSubmit}
        disabled={!canSubmit || status === 'submitting'}
        className="w-full py-3 rounded-lg bg-[#3b82f6] text-white text-sm font-medium
                   hover:bg-[#2563eb] disabled:opacity-30 disabled:cursor-not-allowed
                   transition-all duration-150"
      >
        {status === 'submitting' ? 'Submitting...' : 'Submit outcome'}
      </button>

      {status === 'error' && (
        <p className="text-xs text-red-400/70">Something went wrong. Try again.</p>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Create standalone submit page**

```tsx
// frontend/app/submit/page.tsx
import SubmitOutcomeForm from '@/components/SubmitOutcomeForm'
import Link from 'next/link'

export default function SubmitPage() {
  return (
    <div className="min-h-screen flex flex-col bg-[#0a0a0a]">
      <div className="flex-1 px-4 pt-16 pb-16 max-w-lg mx-auto w-full">
        <Link href="/" className="text-sm text-white/30 hover:text-white/50 transition-colors">
          &larr; Browse programs
        </Link>
        <div className="mt-6 mb-8">
          <h1 className="font-display text-2xl text-[#f5f5f0]">Share your outcome</h1>
          <p className="mt-2 text-sm text-white/40">
            Help future applicants by contributing your admission result. Anonymous, no account needed.
          </p>
        </div>
        <SubmitOutcomeForm />
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Add inline form to Program Intelligence Page**

In `frontend/app/program/[school]/[program]/page.tsx`, add after the "Where Do You Stand?" section:

```tsx
import SubmitOutcomeForm from '@/components/SubmitOutcomeForm'

// ... inside the return, after WhereDoYouStand:
        {/* Submit form */}
        <div className="mb-10 p-6 rounded-xl border border-white/10 bg-white/[0.03]">
          <SubmitOutcomeForm defaultSchool={school} defaultProgram={program} />
        </div>
```

- [ ] **Step 4: Verify it builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/SubmitOutcomeForm.tsx frontend/app/submit/ frontend/app/program/
git commit -m "feat: add anonymous submission form (inline + standalone)"
```

---

## Task 12: Clean up old components and run full integration test

Remove components from the old probability-first design that are no longer used.

**Files:**
- Delete: `frontend/components/LoadingScreen.tsx`
- Delete: `frontend/components/SummaryBar.tsx`
- Delete: `frontend/components/SupplementalCards.tsx`
- Delete: `frontend/components/ResultView.tsx`
- Delete: `frontend/components/SchoolProgramSelector.tsx`
- Delete: `frontend/components/GradeInput.tsx`
- Modify: `frontend/lib/types.ts` (remove unused types)
- Modify: `frontend/lib/constants.ts` (remove unused exports)

- [ ] **Step 1: Delete unused components**

```bash
rm frontend/components/LoadingScreen.tsx
rm frontend/components/SummaryBar.tsx
rm frontend/components/SupplementalCards.tsx
rm frontend/components/ResultView.tsx
rm frontend/components/SchoolProgramSelector.tsx
rm frontend/components/GradeInput.tsx
```

- [ ] **Step 2: Clean up types.ts**

Remove `FormState`, `BaseProbabilityResult`, `FinalProbabilityResult`, `SchoolResult`, `AppView`, `EssayPair`, `SupplementalType` if no longer imported anywhere. Keep `SimilarStudents` only if still used. Keep the new types added in Task 8.

- [ ] **Step 3: Clean up constants.ts**

Remove `ADMITTED_PROFILE_KEYS`, `hasAdmittedProfile`, `getPersonalityLine`, `SUPPLEMENTAL_LABEL`, `PROGRAMS_BY_SCHOOL` if no longer imported. The `PROGRAM_LABELS` export can stay if other components import it (check), otherwise inline it where needed.

- [ ] **Step 4: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no import errors.

- [ ] **Step 5: Run the full stack locally**

Terminal 1: `cd /Users/jshum/Desktop/unipath-ai && uvicorn server.main:app --reload`
Terminal 2: `cd /Users/jshum/Desktop/unipath-ai/frontend && npm run dev`

Verify:
1. Home page loads with program cards
2. Clicking a card opens the Program Intelligence Page
3. Grade distribution chart renders with real data
4. EC breakdown shows tag percentages
5. "Where Do You Stand?" expands and shows position
6. Submission form submits successfully
7. `/submit` standalone page works

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: remove old probability-first components, clean up types and constants"
```

---

## Task 13: Run the expanded scraper

After eval is complete and model is selected, run the scraper with the new configuration.

**Files:**
- Reference: `pipeline/reddit_agent.py` (already modified in Task 5)

- [ ] **Step 1: Ensure Ollama is running with the selected model**

```bash
ollama list  # verify the selected model is available
```

- [ ] **Step 2: Run the scraper**

```bash
python3 -m pipeline.reddit_agent
```

Expected: Scrapes `r/OntarioGrade12s`, `r/BCGrade12s`, and `r/AlbertaGrade12s`. Progress file skips already-completed queries. New posts get structured extraction.

- [ ] **Step 3: Verify data growth**

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('database/unipath.db')
total = conn.execute('SELECT COUNT(*) FROM students').fetchone()[0]
by_source = conn.execute('SELECT source, COUNT(*) FROM students GROUP BY source').fetchall()
print(f'Total: {total}')
for s in by_source: print(f'  {s[0]}: {s[1]}')
conn.close()
"
```

- [ ] **Step 4: Commit the updated database**

```bash
git add database/unipath.db
git commit -m "data: run expanded scraper with structured output + AlbertaGrade12s"
```
