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

DATABASE_URL = os.getenv("DATABASE_URL", "")


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
