# URA Guidance Assistant

Production-oriented Phase 1 MVP for an authenticated Uganda tax guidance app with Postgres FTS RAG, deterministic calculators, and Postgres-only abuse controls.

## Monorepo layout

- `apps/web`: Next.js App Router frontend (docs vault UI + BetterAuth + Ask URA Tax widget)
- `apps/api`: FastAPI backend (RAG, quotas, calculators, citations)
- `docs`: source registry + glossary + tiny fixtures (no full corpus committed)
- `scripts/ingest`: source fetch/parse/chunk/load utility for Postgres seeding

## Phase status

- Phase 1 (implemented): Postgres FTS retriever (`RETRIEVER_MODE=fts`)
- Phase 2 (stub): `PgVectorRetriever` adapter scaffold
- Phase 3 (planned): Learning mode (flash cards + quizzes by level)
- Phase 4 (stub): `QdrantRetriever` adapter scaffold

## Public access behavior

- `/` is a public landing page.
- `/docs` is publicly browseable.
- Guests (not signed in) can use Ask URA Tax with reduced quotas and no conversation history.
- Signed-in users get higher quotas and conversation history.

## Auth boundary (Option A)

- Next.js uses BetterAuth for user sessions.
- Next.js mints short-lived API JWTs (`/api/tax/token`) for authenticated users.
- Browser calls FastAPI with `Authorization: Bearer <jwt>`.
- FastAPI validates issuer/audience/signature and uses `sub` as `user_id`.

## Requirements

- Node.js 20+
- Python 3.11+
- Postgres 15+ (local) or Neon Postgres (production)

## Environment setup

### Web (`apps/web/.env.local`)

Copy `apps/web/.env.example` and set:

- `DATABASE_URL`
- `BETTER_AUTH_SECRET`
- `BETTER_AUTH_URL` (for local: `http://localhost:3000`)
- `API_JWT_SECRET` (must match API secret)
- `API_JWT_ISSUER` (default: `ura-guidance-web`)
- `API_JWT_AUDIENCE` (default: `ura-guidance-api`)
- `API_JWT_EXPIRES_SECONDS` (default: `900`)
- `NEXT_PUBLIC_API_BASE_URL` (for local: `http://localhost:8000`)

### API (`apps/api/.env`)

Copy `apps/api/.env.example` and set:

- `DATABASE_URL`
- `API_JWT_SECRET` (same value as web)
- `API_JWT_ISSUER`
- `API_JWT_AUDIENCE`
- `RETRIEVER_MODE=fts`
- `GEMINI_ENABLED=false` for mock mode, `true` with `GEMINI_API_KEY`
- Optional guest quota overrides:
  - `GUEST_QUOTA_DAILY_REQUESTS`
  - `GUEST_QUOTA_DAILY_OUTPUT_TOKENS`
  - `GUEST_QUOTA_MINUTE_REQUESTS`

## Neon configuration

Use a single Neon `DATABASE_URL` and include SSL requirement:

- Example: `postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require`

Neon has connection limits. This API is configured with low defaults:

- `DB_POOL_SIZE=3`
- `DB_MAX_OVERFLOW=2`

Keep transactions short (quota updates are small and indexed) to avoid exhausting serverless connections.

## Local run (Phase 1, no docker-compose)

### 1) Install dependencies

```bash
cd apps/web
npm install

cd ../api
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Run API

```bash
cd apps/api
uvicorn app.main:app --reload --port 8000
```

### 3) Run ingest

```bash
# from repo root
# full pipeline (recommended)
python scripts/ingest/main.py seed --database-url $DATABASE_URL

# or run stages separately
python scripts/ingest/main.py fetch
python scripts/ingest/main.py ingest --database-url $DATABASE_URL
python scripts/ingest/main.py ingest --database-url $DATABASE_URL --fetch-if-missing
python scripts/ingest/main.py verify --database-url $DATABASE_URL
```

Command behavior:
- `seed`: fetch -> parse -> chunk -> load -> report -> verify
- `fetch`: download `acquisition=fetch` sources to `.tmp/ingest/raw/{source_id}/...`
- `ingest`: parse/chunk/load available local raw files (use `--fetch-if-missing` to auto-fetch missing fetch sources)
- `verify`: checks DB counts and fails if `source_chunks == 0` or fetch pipeline appears broken

### 4) Run web

```bash
cd apps/web
npm run dev
```

Open `http://localhost:3000`.

## API endpoints

- `POST /v1/chat`
- `GET /v1/conversations`
- `GET /v1/conversations/{id}`
- `GET /v1/docs/tree`
- `GET /v1/docs/page?path=...`

OpenAPI docs are available at FastAPI defaults:

- `http://localhost:8000/docs`

## Quotas and anti-abuse (Postgres only)

Implemented without Redis:

- `usage_daily (user_id, day)`
- `usage_minute (user_id, minute_ts)`
- `inflight_requests (user_id)`

Enforced limits:

- 25 requests/day
- 2000 output tokens/day (best-effort estimate)
- 10 requests/minute
- 1 concurrent in-flight request/user

Guest limits:

- 8 requests/day
- 600 output tokens/day (best-effort estimate)
- 3 requests/minute
- 1 concurrent in-flight request/user

On limit exceeded, API returns `429` with retry hints.

## Deterministic calculators

- VAT calculator (inclusive/exclusive)
- PAYE placeholder calculator (structure + validation; configure real brackets before production)

`POST /v1/chat` can include `calculation` in the response when a computation is requested.

## Testing

Backend minimal tests:

```bash
cd apps/api
pytest -q
```

Covered:

- quota enforcement guard
- FTS retriever mapping
- VAT calculator correctness

## BetterAuth callback URLs

For local development:

- App origin: `http://localhost:3000`
- Auth routes: `/api/auth/*`

Ensure BetterAuth base URL/env values match the deployed web origin in production.

## Deploy web on Vercel (Phase 1)

Create a Vercel project with root directory `apps/web`, then set these environment variables in Vercel.

| Variable | Set in Vercel? | Value source | Example |
| --- | --- | --- | --- |
| `DATABASE_URL` | Yes | Same Postgres/Neon DB used by BetterAuth user/session tables | `postgresql://...` |
| `BETTER_AUTH_SECRET` | Yes | Strong random secret | `long-random-string` |
| `BETTER_AUTH_URL` | Yes | Your Vercel web URL | `https://ura-guidance-assistant.vercel.app` |
| `API_JWT_SECRET` | Yes | Shared secret with FastAPI service | `same-as-api-secret` |
| `API_JWT_ISSUER` | Yes | Must match API issuer validation | `ura-guidance-web` |
| `API_JWT_AUDIENCE` | Yes | Must match API audience validation | `ura-guidance-api` |
| `API_JWT_EXPIRES_SECONDS` | Yes | JWT lifetime in seconds | `900` |
| `NEXT_PUBLIC_API_BASE_URL` | Yes | Public URL of deployed FastAPI service | `https://api.yourdomain.com` |

Notes:
- Set each variable for `Production`, `Preview`, and `Development` as needed.
- `API_JWT_SECRET`, `API_JWT_ISSUER`, and `API_JWT_AUDIENCE` must exactly match values configured in `apps/api/.env`.
- Update `BETTER_AUTH_URL` whenever your Vercel primary domain changes.

Quick Vercel UI checklist:
1. Vercel Dashboard -> `Add New...` -> `Project` -> import this repository.
2. In project setup, set `Root Directory` to `apps/web`.
3. Go to `Project Settings` -> `Environment Variables` and add all variables from the table above.
4. Go to `Project Settings` -> `Domains` and confirm the production domain.
5. Re-deploy from `Deployments` after any environment variable changes.

## Deployment notes

- Deploy `apps/web` and `apps/api` as separate services/containers.
- Point both services to Neon `DATABASE_URL` with `sslmode=require`.
- Keep API pool sizes small for Neon.
- Run ingestion as a one-off job using `python scripts/ingest/main.py seed --database-url $DATABASE_URL`.

## Future phase note

`docker-compose.yml` is intentionally not included in Phase 1 per plan; it is a Phase 3 optional deliverable.


TASK: Seed the Uganda Tax Assistant app with authoritative documents for these categories:
(VAT, PAYE, WHT, EFRIS, registration, penalties)
AND include Luganda (lg-UG) support from day one.

GOAL:
Create a repeatable content pipeline and a starter corpus that can answer questions with citations.
Phase 1 retrieval uses Postgres Full-Text Search (FTS).
Because most official sources are English, Luganda support initially works via:
- Luganda user input -> translation/query rewrite to English -> retrieve English evidence -> answer in Luganda (with citations)
Also add a Luganda glossary on day one and wire it into translation prompts.

-----------------------------------------
0) Language fundamentals (Day 1)
-----------------------------------------
- Add language_code everywhere: en-UG and lg-UG.
- Store user language preference (default en-UG).
- In ingestion metadata, store chunk_language_code (default "en-UG" for fetched Acts/guidance).
- In retrieval, allow searching only English chunks initially but always return answers in the user’s language_code.
- Add a “LanguageAgent” module for:
  - translate_to_english(text, glossary)
  - translate_to_luganda(text, glossary)
  - rewrite_query(text, glossary)

Create:
docs/glossary/lg-UG.yaml
Seed it with initial tax/legal terminology and allow later edits.

Example seed glossary content (must create this file):

vat: "omusolo ku byamaguzi"
value_added_tax: "omusolo ku byamaguzi"
income_tax: "omusolo ku nnyingiza"
withholding_tax: "omusolo ogusigala (withholding)"
paye: "PAYE (omusolo ku bakozi)"
taxpayer: "omusuubuzi/omusolooza"
return: "fayiro y'omusolo"
invoice: "fakito"
efris: "EFRIS (sistemu y'ebyokulonda fakito)"
registration: "okw'ewandiisa"
tin: "TIN"
penalty: "ekibonerezo"
interest: "amabanja (interest)"

Use this glossary in translation/rewrite prompts.

-----------------------------------------
1) Create docs/sources.yaml (seed registry)
-----------------------------------------
Create docs/sources.yaml entries with fields:
- id
- title
- publisher
- category: VAT|PAYE|WHT|EFRIS|registration|penalties
- doc_type: act|amendment|regulation|guidance|manual|technical
- source_type: html|pdf
- url (nullable if manual)
- acquisition: fetch|manual_download
- local_path (required if manual_download)
- effective_from / effective_to (nullable)
- notes
- language_code (default "en-UG" for official sources)

Add these authoritative FETCH sources (exact URLs):

VAT (law)
- Value Added Tax Act (Cap 349) — ULII HTML:
  https://ulii.org/akn/ug/act/statute/1996/8/eng%402000-12-31  (publisher: ULII/Laws.Africa)
- VAT (Amendment) Act, 2024 — Parliament PDF:
  https://bills.parliament.ug/attachments/Value%20Added%20Tax%20%28Amendment%29%20Act%2C%202024.pdf

PAYE + WHT (law)
- Income Tax Act (Cap 340) — ULII HTML:
  https://ulii.org/akn/ug/act/1997/11
- Income Tax (Amendment) Act, 2024 — Parliament PDF:
  https://bills.parliament.ug/attachments/Income%20Tax%20%28Amendment%29%20Act%2C%202024.pdf

Registration + Penalties (tax admin)
- Tax Procedures Code Act, 2014 — ULII HTML:
  https://ulii.org/akn/ug/act/2014/14
- Tax Procedures Code (Amendment) Act, 2024 — Parliament PDF:
  https://bills.parliament.ug/attachments/Tax%20Procedures%20Code%20%28Amendment%29%20Act%2C%202024.pdf

EFRIS (URA materials likely manual)
Create manual placeholders:
- URA EFRIS User Manual (manual_download)
- URA EFRIS API Documentation (manual_download; only if you have official copy)

URA Guidance placeholders (manual_download) for each category:
VAT:
  docs/raw/ura/vat/ura_vat_guide.pdf
PAYE:
  docs/raw/ura/paye/ura_paye_guide.pdf
WHT:
  docs/raw/ura/wht/ura_withholding_tax_guide.pdf
Registration:
  docs/raw/ura/registration/ura_tin_etax_registration_guide.pdf
Penalties:
  docs/raw/ura/penalties/ura_penalties_interest_guide.pdf
EFRIS:
  docs/raw/ura/efris/ura_efris_user_manual.pdf
  docs/raw/ura/efris/ura_efris_api_docs.pdf

For each placeholder, set language_code: en-UG and note “manual download”.

OPTIONAL: Create placeholders for future Luganda docs (not required now):
- doc_type: guidance
- language_code: lg-UG
- local_path under docs/raw/lg-UG/... (empty until you add content)

-----------------------------------------
2) Implement scripts/ingest pipeline (repeatable)
-----------------------------------------
Create scripts/ingest modules:

A) fetch.py
- Read docs/sources.yaml.
- For acquisition=fetch:
  - download HTML/PDF to docs/raw/fetch/{source_id}/...
  - store content hash for change detection

B) parse_html.py (ULII Acts)
- Extract headings/sections from ULII HTML.
- Preserve section numbering.
- Output normalized markdown to docs/normalized/{source_id}.md

C) parse_pdf.py (Parliament Amendment Acts + URA PDFs)
- Extract text; preserve page numbers if possible
- Output normalized markdown to docs/normalized/{source_id}.md
- store page_ref per chunk when possible

D) chunk.py
- Heading-aware chunking; max chunk size ~800–1200 chars
- Deterministic chunk_hash = sha256(source_id + section_ref + chunk_text)
- Keep section_ref + heading_title
- Store chunk_language_code from source.language_code

E) load_pg.py
- Upsert into Postgres:
  sources(...)
  source_chunks(..., chunk_language_code, chunk_tsvector)
- For Phase 1, build FTS vectors using English config for en-UG chunks:
  chunk_tsvector = to_tsvector('english', chunk_text)
- For future Luganda chunks, still store chunk_tsvector using 'simple' config:
  to_tsvector('simple', chunk_text)
- Ensure idempotency (no duplicate chunks)

F) report.py
- Generate ingest report markdown with:
  - new/changed sources
  - chunk adds/removals
  - counts by category AND language_code

-----------------------------------------
3) Retrieval + Luganda handling (Phase 1 behavior)
-----------------------------------------
Implement retrieval pipeline that supports Luganda queries Day 1:

If user_language_code == lg-UG:
1) LanguageAgent.translate_to_english(question, glossary)
2) LanguageAgent.rewrite_query(english_question, glossary) (optional)
3) Retrieve evidence from English chunks (chunk_language_code == en-UG) using Postgres FTS
4) Answer generation:
   - produce answer in Luganda
   - include citations referencing English sources (title + section/page + snippet)
5) If no evidence found:
   - respond in Luganda asking a clarifying question, and state “no matching source found”

If user_language_code == en-UG:
- normal English flow.

IMPORTANT:
- All substantive answers must include citations.
- If evidence is missing, ask clarifying questions rather than hallucinating.

-----------------------------------------
4) Database seeding targets (what to extract)
-----------------------------------------
Ensure the corpus includes at minimum the following topics by category:

VAT:
- registration rules/threshold references
- charge to tax / taxable supply definitions
- invoicing/records requirements where present
- filing/payment obligations where present
- penalties (some in TPC)

PAYE:
- employment income + withholding obligations (Income Tax Act)
- employer obligations (placeholders from URA guide)

WHT:
- withholding obligations (Income Tax Act + amendments)
- rate schedules references where available (exact numbers may be in schedules; capture citations)

Registration:
- TIN registration procedures (TPC Act)
- return filing procedures (TPC Act)
- URA registration guide placeholder

Penalties:
- interest + penalties + enforcement + objections/appeals procedures (TPC Act)
- URA penalties guide placeholder

EFRIS:
- workflow and compliance basics (manual placeholders)
- later: API docs

Every chunk must carry metadata:
category, doc_type, title, section_ref, page_ref(optional), effective dates, chunk_language_code.

-----------------------------------------
5) Seed rate tables (minimal Phase 1)
-----------------------------------------
Create /apps/api/data/rates/ versioned YAML:
- vat_rates.yaml (include standard rate + effective_from)
- paye_bands.yaml (placeholder; “TBD—populate from authoritative schedule once added”)
- wht_rates.yaml (placeholder; “TBD—populate from authoritative schedule once added”)

VAT calculator must work in Phase 1 using vat_rates.yaml.
PAYE/WHT calculators remain stubs until authoritative rates are added.

-----------------------------------------
6) Output: what success looks like
-----------------------------------------
After running:
  python scripts/ingest/main.py seed --database-url $DATABASE_URL

We should have:
- sources and source_chunks populated in Postgres
- ingest report generated
- FTS works for English queries
- Luganda queries work via translation->FTS->answer-in-Luganda with citations
- URA guidance/EFRIS docs represented as manual placeholders that activate once PDFs are added

Do not build aggressive scrapers for URA portals that require sessions.
Instead, support manual_download workflow robustly.

Implement these instructions now.
