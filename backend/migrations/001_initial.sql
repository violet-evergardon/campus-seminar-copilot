-- SQLite reference migration. Runtime also calls SQLAlchemy create_all for a keyless local start.
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, username VARCHAR(80) NOT NULL UNIQUE, role VARCHAR(20) NOT NULL,
  interest_tags JSON NOT NULL, created_at DATETIME NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY, title VARCHAR(300) NOT NULL, speaker VARCHAR(160), speaker_affiliation VARCHAR(240),
  start_time DATETIME, end_time DATETIME, location VARCHAR(300), location_mode VARCHAR(20) NOT NULL,
  organizer VARCHAR(240), field_tags JSON NOT NULL, abstract TEXT, source_url VARCHAR(1000),
  source_type VARCHAR(40) NOT NULL, source_site VARCHAR(160), status VARCHAR(20) NOT NULL,
  extraction_confidence FLOAT NOT NULL, quality_score FLOAT NOT NULL, fingerprint VARCHAR(64) NOT NULL UNIQUE,
  extraction_evidence JSON NOT NULL, indexed_at DATETIME, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
);
CREATE TABLE IF NOT EXISTS favorites (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), event_id INTEGER NOT NULL REFERENCES events(id), created_at DATETIME NOT NULL, UNIQUE(user_id,event_id));
CREATE TABLE IF NOT EXISTS feedback (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), event_id INTEGER REFERENCES events(id), feedback_type VARCHAR(40) NOT NULL, content TEXT, created_at DATETIME NOT NULL);
CREATE TABLE IF NOT EXISTS bad_cases (id INTEGER PRIMARY KEY, query TEXT NOT NULL, wrong_result TEXT, expected_result TEXT, error_type VARCHAR(60) NOT NULL, status VARCHAR(20) NOT NULL, created_at DATETIME NOT NULL);
CREATE TABLE IF NOT EXISTS crawl_sources (id INTEGER PRIMARY KEY, name VARCHAR(160) NOT NULL UNIQUE, base_url VARCHAR(1000) NOT NULL, adapter VARCHAR(80) NOT NULL, enabled BOOLEAN NOT NULL, last_cursor VARCHAR(500), last_success_at DATETIME, created_at DATETIME NOT NULL);
CREATE TABLE IF NOT EXISTS crawl_runs (id INTEGER PRIMARY KEY, source_id INTEGER REFERENCES crawl_sources(id), status VARCHAR(20) NOT NULL, mode VARCHAR(20) NOT NULL, items_seen INTEGER NOT NULL, items_created INTEGER NOT NULL, items_duplicate INTEGER NOT NULL, error_message TEXT, started_at DATETIME NOT NULL, finished_at DATETIME);
CREATE TABLE IF NOT EXISTS admin_reviews (id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL REFERENCES events(id), reviewer VARCHAR(80) NOT NULL, action VARCHAR(30) NOT NULL, note TEXT, snapshot JSON NOT NULL, created_at DATETIME NOT NULL);

