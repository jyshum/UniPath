# Project State

Last updated: 2026-04-30

UniPath AI is currently a Canadian university admissions outcomes tool with a Python/FastAPI data sidecar and a Next.js frontend.

## Current Data State

- SQLite DB: `database/unipath.db`
- Current row count: 949 student rows
- Sources: 508 `REDDIT_SCRAPED`, 218 `BC_2025`, 216 `BC`, 7 `USER_SUBMITTED`
- Reddit rows keep grade-only records for grade analytics; EC analytics only use rows with real EC tags.
- Existing Reddit `ec_tags` and `circumstance_tags` were cleaned from double-encoded JSON.
- `program_normalized` has been backfilled across existing student rows so the program browse/detail pages can see community data.
- CUDO Windsor business rows were normalized from `Commerce/Mgmt/Business Admin` to `Commerce` / `BUSINESS`.

## Frontend State

- Browse page now returns 35 programs across category filters.
- Program detail pages render for normal names and slash-containing names.
- Next route changed to `frontend/app/program/[school]/[...program]/page.tsx`.
- FastAPI detail route now accepts slash-containing program names via `/programs/{school}/{program_name:path}`.
- Local dev requires both servers:
  - Backend: `uvicorn server.main:app --host 127.0.0.1 --port 8000`
  - Frontend: `cd frontend && npm run dev`

## Recent Verification

- `pytest tests/test_cudo_api.py tests/test_reddit_agent.py tests/test_program_names.py tests/test_program_stats.py -v` passes.
- `npm run build` in `frontend/` compiles successfully.
- `npm run lint` has one warning: `programCategory` is unused in `ProgramCard.tsx`.

## Known Caveats

- Full pytest suite still has existing calibration test failures around interview multiplier expectations, separate from the frontend/data fixes.
- Next build emits an existing Turbopack warning involving `frontend/lib/pythonBridge.ts` tracing through API routes.
