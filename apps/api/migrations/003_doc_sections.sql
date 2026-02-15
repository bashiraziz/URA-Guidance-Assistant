CREATE TABLE IF NOT EXISTS doc_sections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID REFERENCES sources(id) ON DELETE CASCADE,
  parent_id UUID REFERENCES doc_sections(id) ON DELETE CASCADE,
  slug TEXT NOT NULL,
  full_path TEXT NOT NULL UNIQUE,
  section_ref TEXT,
  title TEXT NOT NULL,
  content_md TEXT NOT NULL DEFAULT '',
  sort_order INT NOT NULL DEFAULT 0,
  level INT NOT NULL DEFAULT 0,
  word_count INT NOT NULL DEFAULT 0,
  reading_time_minutes INT NOT NULL DEFAULT 0,
  is_placeholder BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_doc_sections_parent ON doc_sections(parent_id);
CREATE INDEX IF NOT EXISTS idx_doc_sections_source ON doc_sections(source_id);
CREATE INDEX IF NOT EXISTS idx_doc_sections_slug ON doc_sections(slug);
CREATE INDEX IF NOT EXISTS idx_doc_sections_level ON doc_sections(level);
