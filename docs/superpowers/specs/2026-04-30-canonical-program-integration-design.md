# Canonical Program Integration Design

## Goal

Integrate `canadian_programs.json` end-to-end as UniPath's source of truth for program normalization, Reddit extraction guidance, Reddit search coverage, and database backfill.

The outcome should be a consistent program taxonomy across:

- `pipeline/program_names.py`
- `pipeline/reddit_agent.py`
- `program_normalized` and `program_category` in `students`
- CUDO program normalization
- Program browse/detail API results

## Current State

The project has a strong taxonomy artifact at `canadian_programs.json`:

- 111 program entries
- 11 schools
- broad categories: `ENGINEERING`, `SCIENCE`, `BUSINESS`, `COMPUTER_SCIENCE`, `HEALTH`, `ARTS`
- aliases for Reddit slang and abbreviations
- per-school admission type metadata: `faculty`, `direct`, and some mixed notes

The current Python normalizer is still a small hand-written map in `pipeline/program_names.py`. It normalizes broad names like `engineering -> Engineering`, but does not use the JSON artifact, does not expose admission metadata, and does not provide alias/query generation for Reddit scraping.

The Reddit agent prompt also has a hand-written flat program list. Search queries are broad and do not yet use sub-program aliases like `SYDE`, `Nano`, `AFM`, `FARM`, `EngSci`, or `tron`.

## Key Decision

`Biomedical Sciences` will be canonicalized as `SCIENCE`.

The duplicate health-category entry in `canadian_programs.json` must be resolved before integration:

- If the health-side entry represents a distinct real admissions program, rename it to `Biomedical Health Sciences`.
- If it does not represent a distinct admissions program, merge/remove it.
- Aliases such as `biomed`, `biomedical`, and `biomed sci` must be handled carefully because they can also collide with `Biomedical Engineering`.

The normalizer must not allow the same `canonical_name` to map to multiple categories.

## Architecture

Use a hybrid source-of-truth design:

- `canadian_programs.json` remains the editable taxonomy source.
- `pipeline/program_names.py` loads and validates the JSON.
- Existing callers keep stable helper functions.
- New helper functions expose metadata needed by the Reddit agent and future frontend/API tasks.

This avoids duplicating the taxonomy in Python while keeping the rest of the codebase insulated behind small helper APIs.

## Program Names API

`pipeline/program_names.py` should expose:

- `load_program_taxonomy() -> ProgramTaxonomy`
- `normalize_program_name(raw: str | None, school: str | None = None) -> str | None`
- `get_program_category(canonical_name: str) -> str`
- `get_admission_type(canonical_name: str, school: str) -> str | None`
- `get_admission_note(school: str, category_or_program: str | None = None) -> str | None`
- `program_aliases_for_prompt(max_items: int | None = None) -> str`
- `program_search_terms() -> list[str]`
- `validate_program_taxonomy() -> list[str]`

`normalize_program_name()` should remain backward compatible for existing calls that pass only `raw`.

When `school` is provided, school-specific matching should be preferred. This matters for aliases that collide across programs.

## Matching Rules

The matcher should apply rules in this order:

1. Exact canonical name match, case-insensitive.
2. Exact alias match, case-insensitive.
3. School-aware exact alias/canonical match when `school` is provided.
4. Legacy broad-faculty fallback for existing data:
   - `Engineering`, `Applied Science`, `APSC` -> `Engineering`
   - `Science`, `Bachelor of Science`, `BSc`, `Sciences` -> `Science`
   - `Arts`, `Bachelor of Arts`, `Humanities` -> `Arts`
   - `Commerce`, `Sauder`, `BCom` -> `Commerce`
   - `Ivey`, `Ivey AEO` -> `Business Administration`
5. If still unknown, return the stripped raw value rather than dropping data.

For ambiguous aliases:

- Prefer school-specific candidates when exactly one candidate exists for the school.
- If multiple candidates remain, use a conservative fallback to the broad category or raw value.
- Do not silently pick a direct-entry sub-program when the text only says a broad faculty name.

Examples:

- `SYDE` + Waterloo -> `Systems Design Engineering`
- `tron` + Waterloo -> `Mechatronics Engineering`
- `EngSci` + UofT -> `Engineering Science`
- `biomed` + context mentioning engineering -> `Biomedical Engineering`
- `biomed sci` -> `Biomedical Sciences`
- `Engineering` + UBC -> `Engineering`, not `Mechanical Engineering`

## Reddit Agent Integration

The Reddit agent should use the taxonomy in two places.

### Extraction Prompt

Replace the hardcoded flat program mapping in `EXTRACTION_PROMPT` with generated compact guidance from the taxonomy.

The prompt should still enforce:

- Only extract a program if explicitly present in the Reddit post.
- Do not infer program from the search query.
- Do not guess a sub-program from a school name alone.
- Return the user-mentioned program/faculty, then let `normalize_program_name()` canonicalize it.

The generated prompt section should include high-signal examples, not the full 111-entry taxonomy if that makes the prompt too long. It should prioritize aliases and programs commonly seen on Reddit.

### Search Queries

Expand `SEARCH_QUERIES` using `program_search_terms()`.

The expansion should be curated and bounded:

- include high-signal direct-entry aliases and sub-programs
- include school-specific phrases for competitive programs
- avoid generating thousands of low-value combinations
- keep broad existing queries for recall

Examples:

- `Waterloo SYDE accepted`
- `Waterloo nano accepted`
- `Waterloo AFM accepted`
- `UofT EngSci accepted`
- `UBC Sauder accepted`
- `Western Ivey AEO`
- `McMaster health sci accepted`

## Database Backfill

After taxonomy integration, rerun a backfill for all existing `students` rows:

- update `program_normalized` from `program_raw` using the new school-aware normalizer
- update `program_category` from the canonical program category where reliable
- preserve existing `REDDIT_SCRAPED` and `USER_SUBMITTED` rows
- do not clear or reload Reddit/user-submitted data

Backfill should print a before/after summary:

- total rows checked
- rows changed
- top normalized programs
- unresolved raw program names
- category distribution

## CUDO Integration

CUDO scraping should continue to normalize CUDO names through `normalize_program_name()`.

Existing CUDO names like `Commerce/Mgmt/Business Admin` must continue to resolve to `Commerce` / `BUSINESS`.

If the JSON taxonomy contains CUDO-style names as aliases, the custom CUDO mappings in Python should be reduced or removed where possible.

## Frontend/API Impact

No major frontend redesign is required.

The existing frontend and API should benefit from better `program_normalized` values:

- browse page should show more precise program cards
- category filters should continue to work
- detail pages should resolve canonical program names
- slash-containing program names should continue to work through the existing catch-all route and FastAPI path route

Admission metadata must be available through helper functions. This integration does not add new UI.

## Error Handling

Taxonomy validation should fail tests if:

- the same canonical name appears in multiple categories
- an alias maps to multiple categories and has no school-aware disambiguation strategy
- required fields are missing from a program entry
- category is outside the supported set
- admission type is outside `faculty`, `direct`, `mixed`, or an explicitly accepted value

Runtime normalization should be forgiving:

- unknown raw names return stripped raw names
- missing JSON should produce a clear exception in tests/development
- production code should not silently collapse unknown programs to `OTHER` unless category lookup is explicitly requested for an unknown canonical name

## Testing Strategy

Add tests for:

- taxonomy loads from JSON
- taxonomy validation catches duplicate canonical/category conflicts
- `Biomedical Sciences` resolves to `SCIENCE`
- school-aware alias matching for Waterloo, UofT, UBC, Western, and McMaster examples
- ambiguous aliases avoid unsafe direct-entry guesses
- CUDO aliases still normalize correctly
- Reddit prompt helper includes high-signal aliases
- Reddit search term helper includes targeted sub-program queries
- backfill updates `program_normalized` and preserves Reddit/user-submitted rows
- API program listing still returns category-filtered programs after backfill

## Out Of Scope

- Redesigning the frontend program pages
- Changing the probability model
- Re-scraping Reddit automatically
- Deleting existing Reddit or user-submitted rows
- Adding admission-note UI to program pages
- Replacing CUDO scraping with a new data source

## Success Criteria

- `canadian_programs.json` is the source of truth for program taxonomy.
- `program_names.py` no longer relies primarily on a small hand-maintained map.
- No duplicate canonical name maps to multiple categories.
- Reddit extraction and search query generation use taxonomy helpers.
- Existing DB rows are backfilled with improved canonical names.
- Program browse/detail pages continue to render.
- Relevant tests pass for normalization, Reddit agent helpers, backfill, and program stats/API behavior.
