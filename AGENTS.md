## Repository Agent Instructions

- Follow `implementation-plan.md` as the primary implementation source for this repository.
- Current approved architecture decisions:
  - Auth boundary: Option A (Next.js mints short-lived API JWTs; FastAPI validates bearer JWT).
  - Docker-compose: Phase 3 optional; not required for Phase 1 local setup.
- Keep retrieval mode defaulted to `fts` and preserve Phase 2/3 retriever adapters as disabled stubs.
- Keep abuse controls Postgres-only (no Redis).
