from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.core.config import settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual',
    tags TEXT NOT NULL DEFAULT '',
    group_name TEXT NOT NULL DEFAULT '',
    core_persona INTEGER NOT NULL DEFAULT 0,
    source_url TEXT,
    checksum TEXT NOT NULL DEFAULT '',
    source_key TEXT NOT NULL DEFAULT '',
    source_enabled INTEGER NOT NULL DEFAULT 1,
    last_synced_at TEXT,
    sync_status TEXT NOT NULL DEFAULT 'ready',
    sync_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    role_title TEXT NOT NULL DEFAULT 'Workspace operator',
    avatar_url TEXT,
    bio TEXT NOT NULL DEFAULT '',
    timezone TEXT NOT NULL DEFAULT '',
    notifications_enabled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    google_sub TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT '',
    username TEXT NOT NULL DEFAULT '',
    picture_url TEXT,
    bio TEXT NOT NULL DEFAULT '',
    ai_nickname TEXT NOT NULL DEFAULT 'HajiHaz AI',
    personality TEXT NOT NULL DEFAULT 'balanced',
    theme TEXT NOT NULL DEFAULT 'dark',
    memory_enabled INTEGER NOT NULL DEFAULT 1,
    ai_mode TEXT NOT NULL DEFAULT 'auto',
    answer_mode TEXT NOT NULL DEFAULT 'balanced',
    notifications_enabled INTEGER NOT NULL DEFAULT 0,
    email_verified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS request_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    duration_ms REAL NOT NULL,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'system',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS health_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS backup_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    archive_name TEXT NOT NULL,
    archive_path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'ready',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    route TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT '',
    prompt_length INTEGER NOT NULL DEFAULT 0,
    answer_length INTEGER NOT NULL DEFAULT 0,
    citation_count INTEGER NOT NULL DEFAULT 0,
    provider TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS metric_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cpu_load_1 REAL NOT NULL DEFAULT 0,
    cpu_load_5 REAL NOT NULL DEFAULT 0,
    cpu_load_15 REAL NOT NULL DEFAULT 0,
    memory_used_bytes INTEGER NOT NULL DEFAULT 0,
    memory_total_bytes INTEGER NOT NULL DEFAULT 0,
    disk_used_bytes INTEGER NOT NULL DEFAULT 0,
    disk_total_bytes INTEGER NOT NULL DEFAULT 0,
    ollama_reachable INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    title TEXT NOT NULL DEFAULT '',
    answer_mode TEXT NOT NULL DEFAULT 'balanced',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT '',
    notice TEXT,
    citations_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_documents_group_name ON documents(group_name)",
    "CREATE INDEX IF NOT EXISTS idx_documents_core_persona ON documents(core_persona)",
    "CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source)",
    "CREATE INDEX IF NOT EXISTS idx_documents_source_key ON documents(source_key)",
    "CREATE INDEX IF NOT EXISTS idx_documents_source_enabled ON documents(source_enabled)",
    "CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id)",
    "CREATE INDEX IF NOT EXISTS idx_admins_email ON admins(email)",
    "CREATE INDEX IF NOT EXISTS idx_users_google_sub ON users(google_sub)",
    "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
    "CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_request_logs_created_at ON request_logs(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_health_checks_created_at ON health_checks(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_backup_runs_created_at ON backup_runs(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_usage_events_created_at ON usage_events(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_usage_events_route ON usage_events(route)",
    "CREATE INDEX IF NOT EXISTS idx_metric_snapshots_created_at ON metric_snapshots(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at ON chat_sessions(updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id)",
]

DOCUMENT_COLUMN_MIGRATIONS = {
    "group_name": "ALTER TABLE documents ADD COLUMN group_name TEXT NOT NULL DEFAULT ''",
    "core_persona": "ALTER TABLE documents ADD COLUMN core_persona INTEGER NOT NULL DEFAULT 0",
    "source_url": "ALTER TABLE documents ADD COLUMN source_url TEXT",
    "checksum": "ALTER TABLE documents ADD COLUMN checksum TEXT NOT NULL DEFAULT ''",
    "source_key": "ALTER TABLE documents ADD COLUMN source_key TEXT NOT NULL DEFAULT ''",
    "source_enabled": "ALTER TABLE documents ADD COLUMN source_enabled INTEGER NOT NULL DEFAULT 1",
    "last_synced_at": "ALTER TABLE documents ADD COLUMN last_synced_at TEXT",
    "sync_status": "ALTER TABLE documents ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'ready'",
    "sync_error": "ALTER TABLE documents ADD COLUMN sync_error TEXT NOT NULL DEFAULT ''",
}

CHUNK_COLUMN_MIGRATIONS = {
    "token_count": "ALTER TABLE chunks ADD COLUMN token_count INTEGER NOT NULL DEFAULT 0",
}

CHAT_SESSION_COLUMN_MIGRATIONS = {
    "user_id": "ALTER TABLE chat_sessions ADD COLUMN user_id INTEGER",
}

USER_COLUMN_MIGRATIONS = {
    "username": "ALTER TABLE users ADD COLUMN username TEXT NOT NULL DEFAULT ''",
    "bio": "ALTER TABLE users ADD COLUMN bio TEXT NOT NULL DEFAULT ''",
    "ai_nickname": "ALTER TABLE users ADD COLUMN ai_nickname TEXT NOT NULL DEFAULT 'HajiHaz AI'",
    "personality": "ALTER TABLE users ADD COLUMN personality TEXT NOT NULL DEFAULT 'balanced'",
    "theme": "ALTER TABLE users ADD COLUMN theme TEXT NOT NULL DEFAULT 'dark'",
    "memory_enabled": "ALTER TABLE users ADD COLUMN memory_enabled INTEGER NOT NULL DEFAULT 1",
    "ai_mode": "ALTER TABLE users ADD COLUMN ai_mode TEXT NOT NULL DEFAULT 'auto'",
    "answer_mode": "ALTER TABLE users ADD COLUMN answer_mode TEXT NOT NULL DEFAULT 'balanced'",
    "notifications_enabled": "ALTER TABLE users ADD COLUMN notifications_enabled INTEGER NOT NULL DEFAULT 0",
}

ADMIN_COLUMN_MIGRATIONS = {
    "display_name": "ALTER TABLE admins ADD COLUMN display_name TEXT NOT NULL DEFAULT ''",
    "role_title": "ALTER TABLE admins ADD COLUMN role_title TEXT NOT NULL DEFAULT 'Workspace operator'",
    "avatar_url": "ALTER TABLE admins ADD COLUMN avatar_url TEXT",
    "bio": "ALTER TABLE admins ADD COLUMN bio TEXT NOT NULL DEFAULT ''",
    "timezone": "ALTER TABLE admins ADD COLUMN timezone TEXT NOT NULL DEFAULT ''",
    "notifications_enabled": "ALTER TABLE admins ADD COLUMN notifications_enabled INTEGER NOT NULL DEFAULT 0",
}


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row[1]) for row in rows}


def _ensure_columns(conn: sqlite3.Connection, table: str, migrations: dict[str, str]) -> None:
    existing = _table_columns(conn, table)
    for name, statement in migrations.items():
        if name not in existing:
            conn.execute(statement)


def init_db() -> None:
    db_path = settings.database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA)
        _ensure_columns(conn, "documents", DOCUMENT_COLUMN_MIGRATIONS)
        _ensure_columns(conn, "chunks", CHUNK_COLUMN_MIGRATIONS)
        _ensure_columns(conn, "chat_sessions", CHAT_SESSION_COLUMN_MIGRATIONS)
        _ensure_columns(conn, "users", USER_COLUMN_MIGRATIONS)
        _ensure_columns(conn, "admins", ADMIN_COLUMN_MIGRATIONS)
        for statement in INDEX_STATEMENTS:
            conn.execute(statement)
        conn.commit()


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    db_path = settings.database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()
