## Repository Agent Instructions

- Follow `implementation-plan.md` as the primary implementation source for this repository.
- Current approved architecture decisions:
  - Auth boundary: Option A (Next.js mints short-lived API JWTs; FastAPI validates bearer JWT).
  - Docker-compose: Phase 3 optional; not required for Phase 1 local setup.
- Keep retrieval mode defaulted to `fts` and preserve Phase 2/3 retriever adapters as disabled stubs.
- Keep abuse controls Postgres-only (no Redis).

Codex: You are doing the wrong thing if you add the full URA/Act documents to the repository. The repository must NOT be used as the database. The repository only holds:
- `docs/sources.yaml` (registry)
- small test fixtures (a few KB max)
- optionally normalized markdown outputs for inspection (small)

All real corpus content MUST be loaded into Postgres tables for retrieval (`source_chunks`), and the application must query Postgres, not files, at runtime.

HARD RULES:
1. Do NOT commit large PDFs or full Acts into git. Only commit:
   - `docs/sources.yaml`
   - `docs/glossary/lg-UG.yaml`
   - tiny sample fixtures (<= 50KB)
2. Seeding means ingest into Postgres (Neon/local), creating rows in:
   - `sources`
   - `source_chunks` (with `chunk_tsvector`)
3. Implement a CLI ingest command that:
   - fetches allowed sources OR uses `manual_download` `local_path`
   - normalizes, chunks, and UPSERTS into Postgres
   - outputs an ingest report
4. Implement a verification command (or test) that fails if DB has no chunks.

MANDATORY DELIVERABLES:
- `scripts/ingest/main.py` commands:
  - `python scripts/ingest/main.py fetch`
  - `python scripts/ingest/main.py ingest`
  - `python scripts/ingest/main.py verify`
- Postgres schema + indexes:
  - `sources(...)`
  - `source_chunks(..., chunk_tsvector tsvector)`
  - GIN index on `chunk_tsvector`
- A seed smoke test:
  - pytest test that runs ingest on a tiny fixture and asserts `SELECT count(*) FROM source_chunks > 0`.

ACCEPTANCE CRITERIA:
1. Running
   `python scripts/ingest/main.py ingest --database-url $DATABASE_URL`
   results in:
   - >= 1 row in `sources`
   - >= 10 rows in `source_chunks`
2. Running
   `python scripts/ingest/main.py verify --database-url $DATABASE_URL`
   prints counts by category (VAT, PAYE, WHT, EFRIS, registration, penalties) and exits 0.
3. App retrieval path uses Postgres FTS queries only (no reading markdown files for answers).
