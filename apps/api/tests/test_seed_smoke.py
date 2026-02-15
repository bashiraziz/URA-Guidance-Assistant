from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = PROJECT_ROOT / "apps" / "api" / "migrations"
FIXTURE_SOURCES = PROJECT_ROOT / "docs" / "fixtures" / "sources.fixture.yaml"


def _get_test_db_url() -> str | None:
    """Return a dedicated test DB URL, or None to skip.

    Prefers TEST_DATABASE_URL.  Falls back to DATABASE_URL ONLY if it
    clearly points to a local/test instance (contains 'localhost',
    '127.0.0.1', or 'test').  This prevents accidentally wiping a
    production Neon database.
    """
    test_url = os.getenv("TEST_DATABASE_URL")
    if test_url:
        return test_url
    db_url = os.getenv("DATABASE_URL", "")
    safe_indicators = ("localhost", "127.0.0.1", "test")
    if any(indicator in db_url.lower() for indicator in safe_indicators):
        return db_url
    return None


def _run_migrations(database_url: str) -> None:
    files = sorted([path for path in MIGRATIONS_DIR.glob("*.sql") if path.is_file()])
    with psycopg.connect(database_url, autocommit=False) as conn:
        with conn.cursor() as cur:
            for migration_file in files:
                sql = migration_file.read_text(encoding="utf-8")
                statements = [statement.strip() for statement in sql.split(";") if statement.strip()]
                for statement in statements:
                    cur.execute(statement)
        conn.commit()


@pytest.mark.integration
def test_seed_smoke_ingest_fixture_populates_source_chunks():
    database_url = _get_test_db_url()
    if not database_url:
        pytest.skip("TEST_DATABASE_URL not set (skipping to protect production DB).")

    _run_migrations(database_url)
    with psycopg.connect(database_url, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM source_chunks WHERE doc_path = %s", ("docs/fixtures/tiny_vat_fixture.html",))
            cur.execute("DELETE FROM sources WHERE source_key = %s", ("tiny_vat_fixture",))
            cur.execute("DELETE FROM source_documents WHERE doc_path = %s", ("docs/fixtures/tiny_vat_fixture.html",))
        conn.commit()

    subprocess.run(
        [
            sys.executable,
            "scripts/ingest/main.py",
            "ingest",
            "--sources-file",
            str(FIXTURE_SOURCES),
            "--database-url",
            database_url,
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )

    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM source_chunks WHERE doc_path = %s", ("docs/fixtures/tiny_vat_fixture.html",))
            chunks_count = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM sources WHERE source_key = %s", ("tiny_vat_fixture",))
            sources_count = int(cur.fetchone()[0])

    assert sources_count >= 1
    assert chunks_count > 0


def test_chunk_hash_determinism():
    """Chunking the same content twice must produce identical hashes."""
    sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "ingest"))
    from main import SourceRecord, chunk_markdown

    source = SourceRecord(
        id="hash_test",
        title="Hash Test",
        publisher="Test",
        category="VAT",
        doc_type="act",
        source_type="html",
        url=None,
        acquisition="manual_download",
        local_path=None,
        effective_from=None,
        effective_to=None,
        notes=None,
        language_code="en-UG",
    )
    content = "---\ntitle: \"Test\"\n---\n\n# Section One\n\nSome body text that is long enough to form a chunk. " * 5

    chunks_a = chunk_markdown(source, content)
    chunks_b = chunk_markdown(source, content)

    assert len(chunks_a) > 0
    assert len(chunks_a) == len(chunks_b)
    for a, b in zip(chunks_a, chunks_b):
        assert a["chunk_hash"] == b["chunk_hash"], "chunk_hash must be deterministic"
        assert a["id"] == b["id"], "chunk id must be deterministic"


@pytest.mark.integration
def test_verify_fails_on_empty_db():
    """verify must exit 1 when source_chunks is empty."""
    database_url = _get_test_db_url()
    if not database_url:
        pytest.skip("TEST_DATABASE_URL not set (skipping to protect production DB).")

    sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "ingest"))
    from main import SourceRecord, verify_seed

    _run_migrations(database_url)
    # Clear all chunks to simulate empty DB
    with psycopg.connect(database_url, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM source_chunks")
        conn.commit()

    dummy_sources = [
        SourceRecord(
            id="dummy",
            title="Dummy",
            publisher="Test",
            category="VAT",
            doc_type="act",
            source_type="html",
            url="https://example.com",
            acquisition="fetch",
            local_path=None,
            effective_from=None,
            effective_to=None,
            notes=None,
            language_code="en-UG",
        )
    ]

    result = verify_seed(database_url, dummy_sources, PROJECT_ROOT / ".tmp" / "ingest")
    assert result == 1, "verify must return 1 when source_chunks is empty"
