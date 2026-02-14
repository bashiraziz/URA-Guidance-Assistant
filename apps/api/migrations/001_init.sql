CREATE TABLE IF NOT EXISTS source_documents (
  id UUID PRIMARY KEY,
  doc_path TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'General',
  content_md TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS source_chunks (
  id UUID PRIMARY KEY,
  source_id UUID REFERENCES source_documents(id) ON DELETE CASCADE,
  doc_path TEXT NOT NULL,
  title TEXT NOT NULL,
  section_ref TEXT,
  page_ref TEXT,
  chunk_text TEXT NOT NULL,
  chunk_tsvector TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', COALESCE(chunk_text, ''))) STORED,
  chunk_hash TEXT NOT NULL UNIQUE,
  scope TEXT NOT NULL DEFAULT 'global',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_source_chunks_tsv ON source_chunks USING GIN (chunk_tsvector);
CREATE INDEX IF NOT EXISTS idx_source_chunks_scope ON source_chunks(scope);

CREATE TABLE IF NOT EXISTS conversations (
  id UUID PRIMARY KEY,
  user_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_conversations_user_updated ON conversations(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
  id UUID PRIMARY KEY,
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
  content_md TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_created ON messages(conversation_id, created_at);

CREATE TABLE IF NOT EXISTS tool_calls (
  id UUID PRIMARY KEY,
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  tool_name TEXT NOT NULL,
  payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS usage_daily (
  user_id TEXT NOT NULL,
  day DATE NOT NULL,
  req_count INTEGER NOT NULL DEFAULT 0,
  token_in INTEGER NOT NULL DEFAULT 0,
  token_out INTEGER NOT NULL DEFAULT 0,
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, day)
);

CREATE TABLE IF NOT EXISTS usage_minute (
  user_id TEXT NOT NULL,
  minute_ts TIMESTAMPTZ NOT NULL,
  req_count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, minute_ts)
);

CREATE TABLE IF NOT EXISTS inflight_requests (
  user_id TEXT PRIMARY KEY,
  started_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS qa_cache (
  question_hash TEXT NOT NULL,
  language_code TEXT NOT NULL,
  answer_md TEXT NOT NULL,
  citations_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  hits INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (question_hash, language_code)
);
