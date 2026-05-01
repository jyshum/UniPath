# Canonical Program Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `canadian_programs.json` the source of truth for program normalization, Reddit extraction/search guidance, and database backfill.

**Architecture:** Keep the JSON taxonomy editable and load it through `pipeline/program_names.py`. Expose stable helper functions so existing pipeline, CUDO, Reddit, and API code can use canonical names without knowing JSON internals. Resolve taxonomy conflicts first, then wire the normalizer into Reddit and backfill existing DB rows.

**Tech Stack:** Python 3.13-compatible code, pytest, SQLite, SQLAlchemy, FastAPI, Next.js frontend using existing API responses.

---

### Task 1: Resolve Taxonomy Conflicts

**Files:**
- Modify: `canadian_programs.json`
- Test: `tests/test_program_names.py`

- [ ] **Step 1: Write failing taxonomy validation tests**

Add these tests to `tests/test_program_names.py`:

```python
def test_taxonomy_has_no_duplicate_canonical_name_categories():
    from pipeline.program_names import validate_program_taxonomy

    errors = validate_program_taxonomy()

    assert not [e for e in errors if "duplicate canonical" in e.lower()]


def test_biomedical_sciences_is_science():
    assert normalize_program_name("biomed sci", school="University of Waterloo") == "Biomedical Sciences"
    assert get_program_category("Biomedical Sciences") == "SCIENCE"
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
pytest tests/test_program_names.py::test_taxonomy_has_no_duplicate_canonical_name_categories tests/test_program_names.py::test_biomedical_sciences_is_science -v
```

Expected: fail because `validate_program_taxonomy` does not exist and `Biomedical Sciences` is duplicated in JSON.

- [ ] **Step 3: Edit `canadian_programs.json`**

Resolve the duplicate `Biomedical Sciences` entries:

```json
{
  "canonical_name": "Biomedical Sciences",
  "category": "SCIENCE",
  "schools": ["University of Waterloo", "University of Ottawa", "University of Calgary"],
  "aliases": ["biomed sci", "biomedical science"],
  "admission_type": {
    "University of Waterloo": "direct",
    "University of Ottawa": "direct",
    "University of Calgary": "direct"
  }
}
```

Remove the second duplicate health-category entry. Keep `Biomedical Engineering` separate under `ENGINEERING`.

- [ ] **Step 4: Implement minimal validation stubs in `pipeline/program_names.py`**

Add imports and a first version of `validate_program_taxonomy()` that loads JSON and checks duplicate canonical/category conflicts.

```python
import json
from functools import lru_cache
from pathlib import Path

TAXONOMY_PATH = Path(__file__).parent.parent / "canadian_programs.json"
SUPPORTED_CATEGORIES = {"ENGINEERING", "SCIENCE", "BUSINESS", "COMPUTER_SCIENCE", "HEALTH", "ARTS"}


@lru_cache(maxsize=1)
def _taxonomy_data() -> dict:
    with TAXONOMY_PATH.open() as f:
        return json.load(f)


def validate_program_taxonomy() -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}
    for program in _taxonomy_data().get("programs", []):
        name = program.get("canonical_name")
        category = program.get("category")
        if not name:
            errors.append("missing canonical_name")
            continue
        if category not in SUPPORTED_CATEGORIES:
            errors.append(f"unsupported category for {name}: {category}")
        if name in seen and seen[name] != category:
            errors.append(f"duplicate canonical name in multiple categories: {name}")
        seen[name] = category
    return errors
```

- [ ] **Step 5: Run tests**

Run:

```bash
pytest tests/test_program_names.py -v
```

Expected: existing tests may still fail until Task 2 completes, but duplicate-canonical validation should no longer report `Biomedical Sciences`.

- [ ] **Step 6: Commit**

```bash
git add canadian_programs.json pipeline/program_names.py tests/test_program_names.py
git commit -m "feat: validate canonical program taxonomy"
```

### Task 2: Replace Hand-Written Program Normalizer With JSON-Backed API

**Files:**
- Modify: `pipeline/program_names.py`
- Test: `tests/test_program_names.py`

- [ ] **Step 1: Add failing tests for JSON-backed matching**

Add tests:

```python
def test_school_aware_engineering_aliases():
    assert normalize_program_name("SYDE", school="University of Waterloo") == "Systems Design Engineering"
    assert normalize_program_name("tron", school="University of Waterloo") == "Mechatronics Engineering"
    assert normalize_program_name("EngSci", school="University of Toronto") == "Engineering Science"


def test_broad_faculty_names_stay_broad():
    assert normalize_program_name("Engineering", school="UBC Vancouver") == "Engineering"
    assert normalize_program_name("Applied Science", school="UBC Vancouver") == "Engineering"
    assert normalize_program_name("Science", school="UBC Vancouver") == "Science"


def test_admission_metadata_helpers():
    from pipeline.program_names import get_admission_type, get_admission_note

    assert get_admission_type("Systems Design Engineering", "University of Waterloo") == "direct"
    assert get_admission_type("Engineering", "UBC Vancouver") == "faculty"
    assert "Engineering" in get_admission_note("UBC Vancouver")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_program_names.py -v
```

Expected: fail because school-aware matching and metadata helpers are incomplete.

- [ ] **Step 3: Implement data structures**

Replace the old static maps with a JSON-backed loader. Keep legacy CUDO aliases as fallback entries if missing from JSON.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ProgramEntry:
    canonical_name: str
    category: str
    schools: tuple[str, ...]
    aliases: tuple[str, ...]
    admission_type: dict[str, str]


@dataclass(frozen=True)
class ProgramTaxonomy:
    programs: tuple[ProgramEntry, ...]
    admission_notes: dict
```

Build helper indexes inside `load_program_taxonomy()`:

```python
@lru_cache(maxsize=1)
def load_program_taxonomy() -> ProgramTaxonomy:
    data = _taxonomy_data()
    programs = tuple(
        ProgramEntry(
            canonical_name=p["canonical_name"],
            category=p["category"],
            schools=tuple(p.get("schools", [])),
            aliases=tuple(p.get("aliases", [])),
            admission_type=dict(p.get("admission_type", {})),
        )
        for p in data.get("programs", [])
    )
    return ProgramTaxonomy(
        programs=programs,
        admission_notes=data.get("metadata", {}).get("admission_notes", {}),
    )
```

- [ ] **Step 4: Implement normalization helpers**

Implement these functions:

```python
def _key(value: str) -> str:
    return " ".join(value.strip().lower().replace("&", "and").split())


def _candidate_names(raw: str) -> list[str]:
    raw = raw.strip()
    return [raw, raw.replace("/", " "), raw.replace("-", " ")]


def normalize_program_name(raw: str | None, school: str | None = None) -> str | None:
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None

    broad = _normalize_broad_faculty(raw)
    if broad:
        return broad

    taxonomy = load_program_taxonomy()
    matches = []
    keys = {_key(v) for candidate in _candidate_names(raw) for v in [candidate]}
    for program in taxonomy.programs:
        program_keys = {_key(program.canonical_name), *(_key(a) for a in program.aliases)}
        if keys & program_keys:
            matches.append(program)

    if school:
        school_matches = [p for p in matches if school in p.schools]
        if len(school_matches) == 1:
            return school_matches[0].canonical_name

    if len(matches) == 1:
        return matches[0].canonical_name

    return raw
```

Implement `_normalize_broad_faculty()` with existing broad mappings for `Engineering`, `Science`, `Arts`, `Commerce`, `Ivey`, and CUDO names.

- [ ] **Step 5: Implement category and metadata helpers**

```python
def get_program_category(canonical_name: str) -> str:
    for program in load_program_taxonomy().programs:
        if program.canonical_name == canonical_name:
            return program.category
    broad = _normalize_broad_faculty(canonical_name)
    if broad and broad != canonical_name:
        return get_program_category(broad)
    return "OTHER"


def get_admission_type(canonical_name: str, school: str) -> str | None:
    for program in load_program_taxonomy().programs:
        if program.canonical_name == canonical_name:
            return program.admission_type.get(school)
    notes = load_program_taxonomy().admission_notes.get(school, {})
    category = get_program_category(canonical_name).lower()
    return notes.get(category) or notes.get("all")


def get_admission_note(school: str, category_or_program: str | None = None) -> str | None:
    notes = load_program_taxonomy().admission_notes.get(school)
    if not notes:
        return None
    return notes.get("note")
```

- [ ] **Step 6: Run tests**

Run:

```bash
pytest tests/test_program_names.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add pipeline/program_names.py tests/test_program_names.py
git commit -m "feat: load program taxonomy from json"
```

### Task 3: Add Reddit Prompt And Search Helpers

**Files:**
- Modify: `pipeline/program_names.py`
- Modify: `pipeline/reddit_agent.py`
- Test: `tests/test_program_names.py`
- Test: `tests/test_reddit_agent.py`

- [ ] **Step 1: Write failing helper tests**

Add to `tests/test_program_names.py`:

```python
def test_program_aliases_for_prompt_includes_high_signal_aliases():
    from pipeline.program_names import program_aliases_for_prompt

    prompt = program_aliases_for_prompt(max_items=80)

    assert "SYDE" in prompt or "syde" in prompt
    assert "EngSci" in prompt or "engsci" in prompt
    assert "AFM" in prompt or "afm" in prompt
    assert "Sauder" in prompt or "sauder" in prompt


def test_program_search_terms_are_bounded_and_targeted():
    from pipeline.program_names import program_search_terms

    terms = program_search_terms()

    assert "Waterloo SYDE accepted" in terms
    assert "UofT EngSci accepted" in terms
    assert "Western Ivey AEO" in terms
    assert len(terms) <= 250
```

- [ ] **Step 2: Add Reddit agent prompt test**

Add to `tests/test_reddit_agent.py`:

```python
def test_reddit_prompt_uses_taxonomy_guidance():
    from pipeline.reddit_agent import EXTRACTION_PROMPT

    assert "{program_guidance}" not in EXTRACTION_PROMPT
    assert "SYDE" in EXTRACTION_PROMPT or "syde" in EXTRACTION_PROMPT
    assert "Do NOT infer program from the search query" in EXTRACTION_PROMPT
```

- [ ] **Step 3: Run tests to verify failure**

```bash
pytest tests/test_program_names.py tests/test_reddit_agent.py -v
```

Expected: fail because helper functions and prompt integration are missing.

- [ ] **Step 4: Implement helper functions in `program_names.py`**

```python
HIGH_SIGNAL_ALIASES = {
    "syde", "nano", "afm", "farm", "engsci", "tron", "mte",
    "sauder", "ivey", "aeo", "rotman", "schulich", "beedie",
}


def program_aliases_for_prompt(max_items: int | None = None) -> str:
    rows = []
    for program in load_program_taxonomy().programs:
        aliases = [a for a in program.aliases if _key(a) in HIGH_SIGNAL_ALIASES]
        if aliases:
            rows.append(f'- {", ".join(aliases)} -> {program.canonical_name}')
    rows.sort()
    if max_items is not None:
        rows = rows[:max_items]
    return "\n".join(rows)


def program_search_terms() -> list[str]:
    terms = {
        "Waterloo SYDE accepted",
        "Waterloo nano accepted",
        "Waterloo AFM accepted",
        "Waterloo FARM accepted",
        "Waterloo tron accepted",
        "UofT EngSci accepted",
        "UBC Sauder accepted",
        "Western Ivey AEO",
        "McMaster health sci accepted",
    }
    for program in load_program_taxonomy().programs:
        for alias in program.aliases:
            if _key(alias) in HIGH_SIGNAL_ALIASES:
                for school in program.schools[:2]:
                    short = school.replace("University of ", "").replace("UBC Vancouver", "UBC")
                    terms.add(f"{short} {alias} accepted")
    return sorted(terms)[:250]
```

- [ ] **Step 5: Wire helpers into `reddit_agent.py`**

Import:

```python
from pipeline.program_names import program_aliases_for_prompt, program_search_terms
```

Build `SEARCH_QUERIES` as:

```python
BASE_SEARCH_QUERIES = [
    "accepted engineering",
    "rejected engineering",
    "engineering admission",
    "accepted computer science",
    "rejected computer science",
    "accepted commerce",
    "Ivey AEO",
    "accepted science",
    "health sci accepted",
    "accepted arts",
]

SEARCH_QUERIES = sorted(set(BASE_SEARCH_QUERIES + program_search_terms()))
```

Build `EXTRACTION_PROMPT` with taxonomy guidance:

```python
PROGRAM_GUIDANCE = program_aliases_for_prompt(max_items=80)

EXTRACTION_PROMPT = f"""You are extracting Canadian university admissions data from a Reddit post.

Extract school, program, decision, core average, ECs, province, and citizenship only when clearly present.

High-signal program aliases:
{PROGRAM_GUIDANCE}

Do NOT infer program from the search query or surrounding context.
Do NOT guess a sub-program from school name alone.

Post text:
{{post_text}}"""
```

Keep the existing rules that forbid inference from search query context.

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_program_names.py tests/test_reddit_agent.py -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add pipeline/program_names.py pipeline/reddit_agent.py tests/test_program_names.py tests/test_reddit_agent.py
git commit -m "feat: use program taxonomy in reddit agent"
```

### Task 4: School-Aware Backfill

**Files:**
- Modify: `scripts/backfill_program_normalized.py`
- Test: `tests/test_program_backfill.py`

- [ ] **Step 1: Write failing backfill tests**

Create `tests/test_program_backfill.py`:

```python
import sqlite3

from scripts.backfill_program_normalized import backfill_program_normalized


def test_backfill_uses_school_aware_taxonomy_and_preserves_sources(tmp_path):
    db_path = tmp_path / "programs.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE students (
            id INTEGER PRIMARY KEY,
            source TEXT,
            school_normalized TEXT,
            program_raw TEXT,
            program_normalized TEXT,
            program_category TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "REDDIT_SCRAPED", "University of Waterloo", "SYDE", None, None),
            (2, "USER_SUBMITTED", "UBC Vancouver", "Applied Science", None, None),
            (3, "BC", "UBC Vancouver", "Science", None, None),
        ],
    )
    conn.commit()
    conn.close()

    result = backfill_program_normalized(db_path)

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT source, program_normalized, program_category FROM students ORDER BY id"
    ).fetchall()
    conn.close()

    assert result["checked"] == 3
    assert rows == [
        ("REDDIT_SCRAPED", "Systems Design Engineering", "ENGINEERING"),
        ("USER_SUBMITTED", "Engineering", "ENGINEERING"),
        ("BC", "Science", "SCIENCE"),
    ]
```

- [ ] **Step 2: Run failing test**

```bash
pytest tests/test_program_backfill.py -v
```

Expected: fail because `backfill_program_normalized()` does not exist.

- [ ] **Step 3: Refactor script into callable function**

In `scripts/backfill_program_normalized.py`, implement:

```python
from pathlib import Path
import sqlite3

from pipeline.program_names import get_program_category, normalize_program_name

DB_PATH = Path("database/unipath.db")


def backfill_program_normalized(db_path: str | Path = DB_PATH) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, school_normalized, program_raw, program_normalized, program_category "
        "FROM students WHERE program_raw IS NOT NULL"
    ).fetchall()
    checked = 0
    changed = 0
    for row_id, school, raw, current_name, current_category in rows:
        checked += 1
        normalized = normalize_program_name(raw, school=school)
        category = get_program_category(normalized) if normalized else current_category
        if normalized != current_name or category != current_category:
            conn.execute(
                "UPDATE students SET program_normalized = ?, program_category = ? WHERE id = ?",
                (normalized, category, row_id),
            )
            changed += 1
    conn.commit()
    conn.close()
    return {"checked": checked, "changed": changed}
```

Keep `run()` as a wrapper that prints summary and calls `backfill_program_normalized()`.

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_program_backfill.py -v
```

Expected: pass.

- [ ] **Step 5: Run real DB backfill**

```bash
python -m scripts.backfill_program_normalized
```

Expected: prints checked/changed counts and top normalized programs. It must not delete rows.

- [ ] **Step 6: Verify DB counts preserved**

```bash
sqlite3 database/unipath.db "SELECT source, COUNT(*) FROM students GROUP BY source ORDER BY source;"
```

Expected: source row counts unchanged except any user-added rows since the last check.

- [ ] **Step 7: Commit**

```bash
git add scripts/backfill_program_normalized.py tests/test_program_backfill.py database/unipath.db
git commit -m "feat: backfill programs from canonical taxonomy"
```

### Task 5: CUDO And API Regression Coverage

**Files:**
- Modify: `pipeline/cudo_scraper.py`
- Test: `tests/test_cudo_scraper.py`
- Test: `tests/test_cudo_api.py`
- Test: `tests/test_program_stats.py`

- [ ] **Step 1: Add regression tests**

Add to `tests/test_cudo_scraper.py`:

```python
def test_cudo_business_name_uses_taxonomy():
    from pipeline.program_names import get_program_category, normalize_program_name

    canonical = normalize_program_name("Commerce/Mgmt/Business Admin")

    assert canonical == "Commerce"
    assert get_program_category(canonical) == "BUSINESS"
```

Add to `tests/test_cudo_api.py`:

```python
def test_programs_business_filter_has_results():
    response = client.get("/programs?category=BUSINESS")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert all(item["program_category"] == "BUSINESS" for item in data)
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_cudo_scraper.py tests/test_cudo_api.py tests/test_program_stats.py -v
```

Expected: pass after Tasks 2 and 4. If this fails because `pipeline/cudo_scraper.py` stores raw names, change its parse/load path so every CUDO program uses:

```python
program_name = normalize_program_name(program_raw)
program_category = get_program_category(program_name)
```

- [ ] **Step 3: Verify API program list locally**

Run:

```bash
python - <<'PY'
from core.recommend import list_programs
print("all", len(list_programs()))
for category in ["ENGINEERING", "SCIENCE", "BUSINESS", "COMPUTER_SCIENCE", "HEALTH", "ARTS"]:
    print(category, len(list_programs(category=category)))
PY
```

Expected: every listed category returns at least one program.

- [ ] **Step 4: Commit**

```bash
git add pipeline/cudo_scraper.py tests/test_cudo_scraper.py tests/test_cudo_api.py tests/test_program_stats.py
git commit -m "test: cover taxonomy-backed program APIs"
```

### Task 6: Final Verification And Documentation Update

**Files:**
- Modify: `project_state.md`
- Modify: `README.md` only if its current setup/status section contradicts the new taxonomy state.

- [ ] **Step 1: Run targeted test suite**

```bash
pytest tests/test_program_names.py tests/test_reddit_agent.py tests/test_program_backfill.py tests/test_cudo_scraper.py tests/test_cudo_api.py tests/test_program_stats.py -v
```

Expected: all selected tests pass.

- [ ] **Step 2: Run frontend build**

```bash
cd frontend && npm run build
```

Expected: build exits 0. If the existing Turbopack trace warning appears without failing the build, record it under residual risks rather than changing unrelated frontend API code.

- [ ] **Step 3: Verify DB state**

```bash
sqlite3 database/unipath.db "SELECT source, COUNT(*) FROM students GROUP BY source ORDER BY source;"
sqlite3 database/unipath.db "SELECT program_category, COUNT(*) FROM students GROUP BY program_category ORDER BY COUNT(*) DESC;"
```

Expected: Reddit and user-submitted rows are preserved; category distribution is populated.

- [ ] **Step 4: Update `project_state.md`**

Add a brief note:

```markdown
## Canonical Program Taxonomy

- `canadian_programs.json` is now the source of truth for program names, aliases, categories, and admission metadata.
- Existing student rows were backfilled through the taxonomy.
- Reddit extraction prompt and search queries now use taxonomy helpers.
```

- [ ] **Step 5: Commit**

```bash
git add project_state.md README.md
git commit -m "docs: update project state after taxonomy integration"
```

- [ ] **Step 6: Report residual risks**

Mention:

- any unresolved alias collisions that validation allows only because school-aware matching resolves them
- any full-suite failures unrelated to taxonomy integration
- whether Reddit was re-scraped or only prepared for future runs
