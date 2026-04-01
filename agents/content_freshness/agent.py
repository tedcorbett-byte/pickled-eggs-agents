"""
Pickled Eggs Co — Content Freshness Agent
==========================================
Pulls all Shopify product pages, finds ones not updated in 60+ days,
generates fresh copy using Claude, and queues the updates for human review
before pushing back to Shopify.

Run directly:
  python -m agents.content_freshness.agent

Or via scheduler.py / Railway cron (recommended: daily at 9am).
"""
from datetime import datetime, timedelta, timezone

from shared.claude_client import complete
from shared.db import execute, fetchall, get_conn
from shared.shopify_client import get_products, update_product_description

STALE_DAYS = 60


# ─────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────

def init_db():
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS freshness_queue (
                id TEXT PRIMARY KEY,
                shopify_product_id TEXT NOT NULL,
                product_title TEXT,
                product_url TEXT,
                old_description TEXT,
                new_description TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                reviewed_at TEXT
            )
        """)


# ─────────────────────────────────────────────
# STALENESS CHECK
# ─────────────────────────────────────────────

def find_stale_products() -> list[dict]:
    """Return Shopify products not updated in STALE_DAYS days."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=STALE_DAYS)
    products = get_products()
    stale = []
    for p in products:
        updated_str = p.get("updated_at", "")
        if not updated_str:
            stale.append(p)
            continue
        try:
            updated = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
            if updated < cutoff:
                stale.append(p)
        except ValueError:
            stale.append(p)
    return stale


# ─────────────────────────────────────────────
# COPY REFRESH
# ─────────────────────────────────────────────

def refresh_description(product: dict) -> str:
    """Use Claude to generate fresh product copy for a bar shirt."""
    title = product.get("title", "")
    old_body = product.get("body_html", "")

    prompt = f"""You are writing product copy for Pickled Eggs Co (pickledeggsco.com),
a print-on-demand apparel brand that makes graphic t-shirts memorializing closed bars —
dive bars, gay bars, and neighborhood taverns — across Seattle and Denver.
Founded by brothers Ted and Andy Corbett.

Product: {title}
Current description:
{old_body[:1000]}

Write a fresh product description (150-200 words) that:
- Opens with the emotional hook: why people miss this specific place
- Names the bar and city
- Describes the shirt as a way to keep the memory alive
- Mentions it makes a great gift for locals and former regulars
- Closes with a gentle call to action
- Sounds warm and human, not like marketing copy
- Is formatted as plain HTML paragraphs (<p> tags only, no headers)

Return only the HTML, no explanation."""

    return complete(prompt, max_tokens=400)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run():
    print(f"\n{'='*50}")
    print(f"Content Freshness Agent — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    init_db()
    stale = find_stale_products()
    print(f"Found {len(stale)} products not updated in {STALE_DAYS}+ days.")

    queued = 0
    for product in stale:
        product_id = str(product["id"])
        title = product.get("title", product_id)
        print(f"\n  Refreshing: {title}...")

        # Skip if already queued and pending
        with get_conn() as conn:
            existing = fetchall(
                conn,
                "SELECT id FROM freshness_queue WHERE shopify_product_id = ? AND status = 'pending'",
                (product_id,),
            )
        if existing:
            print(f"  Already queued, skipping.")
            continue

        new_desc = refresh_description(product)
        queue_id = f"freshness_{product_id}_{int(datetime.now().timestamp())}"

        with get_conn() as conn:
            execute(conn, """
                INSERT INTO freshness_queue
                    (id, shopify_product_id, product_title, old_description, new_description, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (queue_id, product_id, title, product.get("body_html", ""), new_desc,
                  datetime.now().isoformat()))

        queued += 1
        print(f"  Queued for review.")

    print(f"\nDone. {queued} products queued for review in the dashboard.")
    return queued


if __name__ == "__main__":
    run()
