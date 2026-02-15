You are Claude Code acting as a senior backend/data engineer.

Build a runnable ingestion + database seeding pipeline for a “Uganda Tax Law + URA Guidance Assistant”.

PRIMARY GOAL
Populate a Postgres database (Neon in prod, local Postgres in dev) with chunked, citation-ready text for these categories:
VAT, PAYE, WHT, EFRIS, registration, penalties.

IMPORTANT CONSTRAINTS
- DO NOT store full Acts or large PDFs in git. The repo should contain only:
  - docs/sources.yaml (registry)
  - docs/glossary/lg-UG.yaml (glossary)
  - tiny fixtures under docs/fixtures/ for tests (<= 50KB)
  - generated artifacts must go into .tmp/ingest/ (gitignored)
- Fetchable sources (ULII HTML, Parliament PDFs) MUST be downloaded automatically by the pipeline.
- URA PDFs may be hard to fetch; support acquisition=manual_download gracefully:
  - If manual file missing, mark as PENDING and continue.
- Provide a single command “seed” that runs the whole pipeline end-to-end.

TARGET STACK
- Python 3.11+
- requests or httpx for HTTP fetching
- beautifulsoup4 or lxml for HTML parsing
- pypdf or pdfplumber for PDF extraction
- psycopg (or asyncpg) for Postgres inserts OR SQLAlchemy (your choice, but keep it simple)
- Postgres Full Text Search (FTS): tsvector + GIN index

DATABASE
Use DATABASE_URL env var (Neon URL includes sslmode=require). Support:
- --database-url CLI override
- autoload from .env if present

SCHEMA (MUST CREATE VIA SQL MIGRATION)
Create SQL migration under migrations/ or scripts/migrate.sql that creates:
1) sources
- id uuid pk
- source_id text unique
- title text
- publisher text
- category text (VAT|PAYE|WHT|EFRIS|registration|penalties)
- doc_type text (act|amendment|guidance|manual|technical)
- source_type text (html|pdf)
- url text nullable
- effective_from date nullable
- effective_to date nullable
- language_code text default 'en-UG'
- acquisition text (fetch|manual_download)
- content_hash text nullable
- created_at timestamptz default now()

2) source_chunks
- id uuid pk
- source_id uuid fk -> sources.id
- doc_path text
- title text
- section_ref text nullable
- page_ref text nullable
- chunk_text text not null
- chunk_hash text unique
- chunk_language_code text default 'en-UG'
- chunk_tsvector tsvector generated or stored (populate in ingest)
- created_at timestamptz default now()

Indexes:
- GIN index on chunk_tsvector
- btree index on sources.category
- btree index on source_chunks.source_id

SOURCES REGISTRY
Create docs/sources.yaml and seed it with these fetchable sources:

VAT:
- Value Added Tax Act (Cap 349) ULII HTML:
  https://ulii.org/akn/ug/act/statute/1996/8/eng%402000-12-31
- VAT (Amendment) Act, 2024 Parliament PDF:
  https://bills.parliament.ug/attachments/Value%20Added%20Tax%20%28Amendment%29%20Act%2C%202024.pdf

PAYE/WHT:
- Income Tax Act (Cap 340) ULII HTML:
  https://ulii.org/akn/ug/act/1997/11
- Income Tax (Amendment) Act, 2024 Parliament PDF:
  https://bills.parliament.ug/attachments/Income%20Tax%20%28Amendment%29%20Act%2C%202024.pdf

Registration/Penalties:
- Tax Procedures Code Act, 2014 ULII HTML:
  https://ulii.org/akn/ug/act/2014/14
- Tax Procedures Code (Amendment) Act, 2024 Parliament PDF:
  https://bills.parliament.ug/attachments/Tax%20Procedures%20Code%20%28Amendment%29%20Act%2C%202024.pdf

EFRIS + URA guidance placeholders (manual_download entries, do not fail if missing):
- URA VAT guide -> docs/raw/ura/vat/ura_vat_guide.pdf
- URA PAYE guide -> docs/raw/ura/paye/ura_paye_guide.pdf
- URA WHT guide -> docs/raw/ura/wht/ura_withholding_tax_guide.pdf
- URA registration guide -> docs/raw/ura/registration/ura_tin_etax_registration_guide.pdf
- URA penalties/interest guide -> docs/raw/ura/penalties/ura_penalties_interest_guide.pdf
- URA EFRIS user manual -> docs/raw/ura/efris/ura_efris_user_manual.pdf
- URA EFRIS API docs -> docs/raw/ura/efris/ura_efris_api_docs.pdf

LUGANDA FROM DAY ONE
Create docs/glossary/lg-UG.yaml with a starter Luganda glossary of tax terms.
Implement “Luganda-aware query support” in the pipeline metadata:
- store language_code per source/chunk (default en-UG)
- (Phase 1) we mostly ingest English docs, but keep language fields ready for lg-UG docs later
- do NOT translate whole Acts into Luganda during ingest (too costly); just support Luganda metadata now

PIPELINE COMMANDS (MUST IMPLEMENT)
Implement scripts/ingest/main.py with subcommands:

1) fetch
- reads docs/sources.yaml
- for acquisition=fetch:
  downloads into .tmp/ingest/raw/{source_id}/
  - HTML saved as source.html
  - PDF saved as source.pdf
  writes .tmp/ingest/raw/{source_id}/_hash.txt
  is idempotent: if hash matches, skip download
- for acquisition=manual_download:
  do nothing

2) ingest
- parses raw files and manual files if present
- outputs normalized markdown to .tmp/ingest/normalized/{source_id}.md
- heading-aware chunking (800–1200 chars max)
- computes chunk_hash = sha256(source_id + section_ref + chunk_text)
- loads into Postgres (upsert sources and chunks)
- populates chunk_tsvector using:
  - 'english' config for en-UG
  - 'simple' config for unknown/lg-UG

3) verify
- prints counts:
  - total sources
  - total chunks
  - counts by category
  - counts by language_code
- exits 1 if total chunks == 0
- exits 0 if chunks exist even if manual sources are pending

4) seed
- runs fetch -> ingest -> verify in order
- creates .tmp/ingest directories automatically
- generates .tmp/ingest/reports/{timestamp}.md summarizing:
  - fetched OK / FAILED
  - manual PENDING / OK
  - sources_upserted, chunks_upserted
  - counts by category

ERROR HANDLING REQUIREMENTS
- Fetch failures must not crash whole run; mark that source FAILED and continue.
- Missing manual_download files must not crash; mark PENDING and continue.
- If ALL fetch sources fail AND no chunks inserted, verify must fail (exit 1).

TESTS (MANDATORY)
Add pytest tests that use a tiny fixture (docs/fixtures/tiny_vat_fixture.html + docs/fixtures/sources.fixture.yaml):
- test_seed_smoke loads fixture into a temporary/local Postgres and asserts:
  source_chunks count > 0
- test_chunk_hash_determinism
- test_verify_fails_on_empty_db

USAGE (README)
Document:
- how to set DATABASE_URL for Neon with sslmode=require
- how to run:
  python scripts/ingest/main.py seed --database-url "$DATABASE_URL"
- how to add URA PDFs manually to docs/raw/ura/... and re-run ingest

DELIVER OUTPUT
Produce complete code (no pseudocode) implementing:
- docs/sources.yaml
- docs/glossary/lg-UG.yaml
- scripts/ingest/main.py and supporting modules
- SQL migration file
- pytest tests + fixtures
- README instructions

Start by generating the files and code now.


++++++++++
  2. Ingest Luganda docs   
     You have Luganda-language source documents to add to sources.yaml and ingest 
     separately.