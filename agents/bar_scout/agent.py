"""
Pickled Eggs Co — Bar Scout Agent  [FUTURE / NOT YET ACTIVE]
=============================================================
Finds closed bars worth memorializing by scanning news articles,
Reddit posts, and local history sites. Surfaces candidates with enough
community attachment to justify a new product.

This agent is stubbed out — the schema and scaffolding are in place,
but the scanning logic is not yet implemented.

Planned data sources:
  - Reddit: r/SeattleWA, r/Denver, r/gaybars — posts about closures
  - Google News RSS: "{city} bar closed", "{city} dive bar closes"
  - Local news sites: The Stranger, Westword, Denver Post

Run directly (once implemented):
  python -m agents.bar_scout.agent

Or via scheduler.py / Railway cron (recommended: weekly).
"""
from datetime import datetime

from shared.db import execute, get_conn


# ─────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────

def init_db():
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS bar_candidates (
                id TEXT PRIMARY KEY,
                bar_name TEXT NOT NULL,
                city TEXT,
                state TEXT,
                source_url TEXT,
                source_type TEXT,
                evidence TEXT,
                community_signal TEXT,
                recommendation TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                reviewed_at TEXT
            )
        """)


# ─────────────────────────────────────────────
# MAIN  (stub)
# ─────────────────────────────────────────────

def run():
    print(f"\n{'='*50}")
    print(f"Bar Scout Agent — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")
    print("Bar Scout is not yet implemented. Coming soon.")
    init_db()


if __name__ == "__main__":
    run()
