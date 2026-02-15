CREATE TABLE IF NOT EXISTS sources (
  id UUID PRIMARY KEY,
  source_key TEXT NOT NULL UNIQUE,
  doc_path TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  publisher TEXT,
  category TEXT NOT NULL,
  doc_type TEXT,
  source_type TEXT,
  source_url TEXT,
  acquisition TEXT,
  local_path TEXT,
  effective_from DATE,
  effective_to DATE,
  notes TEXT,
  language_code TEXT NOT NULL DEFAULT 'en-UG',
  content_hash TEXT,
  content_md TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE source_chunks
  ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'General',
  ADD COLUMN IF NOT EXISTS doc_type TEXT,
  ADD COLUMN IF NOT EXISTS heading_title TEXT,
  ADD COLUMN IF NOT EXISTS effective_from DATE,
  ADD COLUMN IF NOT EXISTS effective_to DATE,
  ADD COLUMN IF NOT EXISTS chunk_language_code TEXT NOT NULL DEFAULT 'en-UG';

DROP INDEX IF EXISTS idx_source_chunks_tsv;
ALTER TABLE source_chunks DROP COLUMN IF EXISTS chunk_tsvector;
ALTER TABLE source_chunks
  ADD COLUMN chunk_tsvector TSVECTOR GENERATED ALWAYS AS (
    CASE
      WHEN chunk_language_code = 'en-UG' THEN to_tsvector('english', COALESCE(chunk_text, ''))
      ELSE to_tsvector('simple', COALESCE(chunk_text, ''))
    END
  ) STORED;

CREATE INDEX IF NOT EXISTS idx_source_chunks_tsv ON source_chunks USING GIN (chunk_tsvector);
CREATE INDEX IF NOT EXISTS idx_source_chunks_scope ON source_chunks(scope);
CREATE INDEX IF NOT EXISTS idx_source_chunks_category ON source_chunks(category);
CREATE INDEX IF NOT EXISTS idx_source_chunks_language ON source_chunks(chunk_language_code);
