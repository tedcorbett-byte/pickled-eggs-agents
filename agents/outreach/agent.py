"""
Pickled Eggs Co — Outreach Agent
=================================
Scans the posts table for high-relevance pending listener items and
generates polished outreach drafts for human review.

Run directly:
  python -m agents.outreach.agent           # process up to 20 posts
  python -m agents.outreach.agent --limit 5 # process up to 5 posts

Or via scheduler.py (Wednesdays 9am PT).
"""
import argparse
import uuid
from datetime import datetime

from shared.bars import BARS, bar_url_for
from shared.claude_client import complete_json
from shared.db import execute, fetchall, fetchone, get_conn


MIN_SCORE = 6  # only process posts with relevance_score >= this


def init_db():
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS outreach_drafts (
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
            )
        """)


def already_drafted(source_post_id: str) -> bool:
    with get_conn() as conn:
        return fetchone(conn,
            "SELECT 1 FROM outreach_drafts WHERE source_post_id = ?",
            (source_post_id,),
        ) is not None


def save_draft(draft: dict):
    with get_conn() as conn:
        execute(conn, """
            INSERT INTO outreach_drafts (
                id, source_post_id, subreddit, post_title,
                bar_name, product_url, draft_text, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (source_post_id) DO NOTHING
        """, (
            draft["id"],
            draft["source_post_id"],
            draft["subreddit"],
            draft["post_title"],
            draft["bar_name"],
            draft["product_url"],
            draft["draft_text"],
            draft["created_at"],
        ))


def generate_draft(post: dict) -> str:
    """Ask Claude to write a polished outreach reply for a high-relevance post."""
    bar_name = post.get("matched_bar", "")
    product_url = bar_url_for(bar_name) if bar_name else "https://pickledeggsco.com"

    bar_detail = ""
    if bar_name:
        bar = next((b for b in BARS if b["name"] == bar_name), None)
        if bar:
            bar_detail = f"\nBar history: {bar.get('description', '')}\nProduct URL: {bar['url']}"

    prompt = f"""You are writing a Reddit reply for Pickled Eggs Co (pickledeggsco.com),
an American apparel brand that makes graphic t-shirts honoring specific defunct dive bars,
music venues, restaurants, and roller rinks.

Write a genuine, warm reply to this Reddit post. Sound like a person who cares about the
same things — not a brand account. Max 120 words.

Post title: {post.get('title', '')}
Subreddit: r/{post.get('subreddit', '')}
Post body (excerpt): {(post.get('body') or '')[:600]}
Matched bar: {bar_name or 'none'}
Relevance reason: {post.get('relevance_reason', '')}
{bar_detail}

Guidelines:
- Reference the specific bar, venue, or feeling they mentioned if possible
- Mention Pickled Eggs Co naturally ("there's a brand called Pickled Eggs Co" or "we make shirts")
- Never say "I work for" or "I'm the owner"
- Include the product URL {product_url} only if a specific bar matches, otherwise pickledeggsco.com
- If no bar match, keep it more conversational and link to the main site

Return JSON:
{{
  "draft": "<reply text>"
}}"""

    try:
        result = complete_json(prompt, max_tokens=400)
        return result.get("draft", "")
    except Exception as e:
        print(f"  Claude error: {e}")
        return ""


def run(limit: int = 20):
    print(f"\n{'='*50}")
    print(f"Outreach Agent — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Processing up to {limit} high-relevance posts")
    print(f"{'='*50}")

    init_db()

    with get_conn() as conn:
        posts = fetchall(conn, """
            SELECT id, subreddit, title, body, url, matched_bar,
                   relevance_score, relevance_reason
            FROM posts
            WHERE relevance_score >= ?
              AND status = 'pending'
            ORDER BY relevance_score DESC, scanned_at DESC
            LIMIT ?
        """, (MIN_SCORE, limit))

    print(f"\nFound {len(posts)} qualifying posts.")

    drafted = 0
    skipped = 0
    for post in posts:
        post_id = post["id"]

        if already_drafted(post_id):
            skipped += 1
            continue

        bar_name = post.get("matched_bar", "")
        product_url = bar_url_for(bar_name) if bar_name else "https://pickledeggsco.com"

        print(f"\n  [{post.get('relevance_score')}/10] {(post.get('title') or '')[:70]}...")
        draft_text = generate_draft(post)

        if not draft_text:
            print("    No draft generated — skipping.")
            continue

        save_draft({
            "id":             str(uuid.uuid4()),
            "source_post_id": post_id,
            "subreddit":      post.get("subreddit", ""),
            "post_title":     post.get("title", ""),
            "bar_name":       bar_name,
            "product_url":    product_url,
            "draft_text":     draft_text,
            "created_at":     datetime.now().isoformat(),
        })
        drafted += 1
        print(f"    Draft saved. ({len(draft_text)} chars)")

    print(f"\nDone. Drafted {drafted} new outreach items. Skipped {skipped} already drafted.")
    return drafted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Outreach Agent — draft replies for high-relevance posts")
    parser.add_argument("--limit", type=int, default=20, help="Max posts to process (default 20)")
    args = parser.parse_args()
    run(limit=args.limit)
