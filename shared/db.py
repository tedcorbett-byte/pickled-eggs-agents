"""
Database abstraction layer.

- Local dev: SQLite, stored at data/pickled_eggs.db
- Railway / production: Postgres, via DATABASE_URL env var

All agents use get_conn(), execute(), fetchall(), and fetchone() from here
instead of calling sqlite3 or psycopg2 directly.
"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Prefer the public URL when running locally (railway run injects the internal
# hostname which is only resolvable within Railway's network).
DATABASE_URL = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL", "")


@contextmanager
def get_conn():
    """Context manager that yields a DB connection and commits on clean exit."""
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        Path("data").mkdir(exist_ok=True)
        conn = sqlite3.connect("data/pickled_eggs.db")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def execute(conn, sql: str, params: tuple = ()):
    """
    Execute SQL against either backend.
    Uses ? placeholders in SQL; automatically converts to %s for Postgres.
    Returns a cursor (psycopg2) or sqlite3.Cursor.
    """
    if DATABASE_URL:
        sql = sql.replace("?", "%s")
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur
    return conn.execute(sql, params)


def fetchall(conn, sql: str, params: tuple = ()) -> list[dict]:
    """Execute a SELECT and return all rows as plain dicts."""
    cur = execute(conn, sql, params)
    return [dict(r) for r in cur.fetchall()]


def fetchone(conn, sql: str, params: tuple = ()) -> dict | None:
    """Execute a SELECT and return the first row as a plain dict, or None."""
    cur = execute(conn, sql, params)
    row = cur.fetchone()
    return dict(row) if row else None


def run_migrations():
    """
    Idempotent schema migrations. Safe to call at every startup.
    Adds columns that may not exist on older installs.
    ALTER TABLE ... ADD COLUMN is not IF-NOT-EXISTS compatible across SQLite
    and PostgreSQL, so we wrap each in try/except and ignore
    duplicate-column errors.
    """
    migrations = [
        "ALTER TABLE bar_candidates ADD COLUMN category TEXT DEFAULT 'bar'",
        "ALTER TABLE posts ADD COLUMN category TEXT DEFAULT 'bar'",
        """CREATE TABLE IF NOT EXISTS outreach_drafts (
            id TEXT PRIMARY KEY,
            source_post_id TEXT UNIQUE NOT NULL,
            subreddit TEXT,
            post_title TEXT,
            bar_name TEXT,
            product_url TEXT,
            draft_text TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            created_at TEXT
        )""",
    ]
    with get_conn() as conn:
        for sql in migrations:
            try:
                execute(conn, sql)
            except Exception as e:
                msg = str(e).lower()
                if (
                    "duplicate column" in msg      # SQLite: column already exists
                    or "already exists" in msg     # PostgreSQL: column already exists
                    or "no such table" in msg      # fresh local install, table not yet created
                    or "does not exist" in msg     # PostgreSQL: table not yet created
                ):
                    pass
                else:
                    raise
