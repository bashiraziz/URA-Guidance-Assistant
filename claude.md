You are a full-stack engineer. Build a content ingestion pipeline that:
- Reads docs/sources.yaml
- Fetches URLs for ULII/Parliament tax Acts automatically
- Converts HTML/PDF into normalized markdown
- Chunks and loads into Neon Postgres
- Includes language_code (en-UG + lg-UG)
- Supports postgresql full-text search
- Implements fetch/ingest/verify CLI commands

Do not store full documents in the repository.
Ensure network access works and that scraping does not require manual downloads.

Seed the database with:
- VAT Act (ULII)
- VAT Amendment Act 2024 (Parliament PDF)
- Income Tax Act (ULII)
- Income Tax Amendment 2024 (Parliament PDF)
- Tax Procedures Code Act 2014 (ULII)
- Tax Procedures Code Amendment Act 2024 (Parliament PDF)

Provide sample code + README instructions.

