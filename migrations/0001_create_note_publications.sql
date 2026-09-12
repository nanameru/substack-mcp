CREATE TABLE IF NOT EXISTS note_publications (
  attempt_id TEXT PRIMARY KEY,
  content_hash TEXT NOT NULL UNIQUE,
  content TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending', 'published', 'unknown')),
  note_id TEXT,
  note_url TEXT,
  attempted_at TEXT NOT NULL,
  published_at TEXT,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_note_publications_attempted_at
  ON note_publications(attempted_at DESC);
