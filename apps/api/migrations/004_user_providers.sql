CREATE TABLE IF NOT EXISTS user_providers (
  user_id    TEXT NOT NULL,
  provider   TEXT NOT NULL CHECK (provider IN ('gemini', 'anthropic', 'openai')),
  api_key_encrypted TEXT NOT NULL,
  model_name TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, provider)
);
