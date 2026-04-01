"""
Pickled Eggs Co — Content Multiplier Agent
==========================================
Takes each bar in the catalog and generates three ready-to-use content pieces:
  1. Instagram caption (with hashtags)
  2. Reddit post draft (organic, community-style)
  3. Email angle (subject line + 2-3 sentence hook for the newsletter)

Outputs are queued for human review in the dashboard before use.

Run directly:
  python -m agents.content_multiplier.agent
  python -m agents.content_multiplier.agent --bar "Jade Pagoda"

Or via scheduler.py / Railway cron (recommended: weekly).
"""
import argparse
from datetime import datetime

from shared.bars import BARS
from shared.claude_client import complete_json
from shared.db import execute, fetchall, get_conn


# ─────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────

def init_db():
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS content_drafts (
                id TEXT PRIMARY KEY,
                bar_name TEXT NOT NULL,
                bar_city TEXT,
                content_type TEXT NOT NULL,
                draft TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                reviewed_at TEXT
            )
        """)


# ─────────────────────────────────────────────
# CONTENT GENERATION
# ─────────────────────────────────────────────

def generate_content(bar: dict) -> dict:
    """Generate Instagram, Reddit, and email content for a single bar."""
    prompt = f"""You are writing social content for Pickled Eggs Co (pickledeggsco.com),
a brand that makes graphic t-shirts memorializing closed bars — dive bars, gay bars,
and neighborhood taverns. Founded by brothers Ted and Andy Corbett in Seattle.

Bar: {bar['name']}
City: {bar['city']}, {bar['state']}
Product URL: {bar['url']}

Generate three content pieces. Keep the voice warm, nostalgic, and community-first —
never corporate or salesy. Real people who miss these places should feel seen.

1. INSTAGRAM CAPTION (150-200 chars + 5-8 hashtags on a new line)
   - Lead with the emotional hook, mention the shirt naturally
   - End with the URL or "link in bio"

2. REDDIT POST DRAFT (title + body, community subreddit style)
   - Title: sounds like a real person sharing something, not an ad
   - Body: 3-4 sentences of genuine nostalgia, mention Pickled Eggs Co as a
     natural aside, include the product URL at the end

3. EMAIL ANGLE (subject line + 2-3 sentence hook for a newsletter)
   - Subject: curiosity-driven, under 50 chars
   - Hook: speaks directly to someone who misses this bar

Respond in this exact JSON format:
{{
  "instagram": "<caption with hashtags>",
  "reddit_title": "<post title>",
  "reddit_body": "<post body>",
  "email_subject": "<subject line>",
  "email_hook": "<2-3 sentence hook>"
}}"""

    return complete_json(prompt, max_tokens=800)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run(bar_name: str | None = None):
    print(f"\n{'='*50}")
    print(f"Content Multiplier Agent — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    init_db()

    bars_to_process = BARS
    if bar_name:
        bars_to_process = [b for b in BARS if b["name"].lower() == bar_name.lower()]
        if not bars_to_process:
            print(f"Bar not found: {bar_name}")
            return

    queued = 0
    for bar in bars_to_process:
        print(f"\n  {bar['name']} ({bar['city']})...")

        # Skip if we already have recent pending drafts for this bar
        with get_conn() as conn:
            existing = fetchall(
                conn,
                "SELECT id FROM content_drafts WHERE bar_name = ? AND status = 'pending'",
                (bar["name"],),
            )
        if existing:
            print(f"  Already has {len(existing)} pending drafts, skipping.")
            continue

        try:
            content = generate_content(bar)
        except Exception as e:
            print(f"  Claude error: {e}")
            continue

        now = datetime.now().isoformat()
        ts = int(datetime.now().timestamp())

        content_pieces = [
            ("instagram",     content.get("instagram", "")),
            ("reddit",        f"{content.get('reddit_title', '')}\n\n{content.get('reddit_body', '')}"),
            ("email",         f"{content.get('email_subject', '')}\n\n{content.get('email_hook', '')}"),
        ]

        with get_conn() as conn:
            for content_type, draft in content_pieces:
                execute(conn, """
                    INSERT INTO content_drafts (id, bar_name, bar_city, content_type, draft, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (f"{content_type}_{bar['name'].lower().replace(' ', '_')}_{ts}",
                      bar["name"], bar["city"], content_type, draft, now))

        queued += 3
        print(f"  Queued: Instagram caption, Reddit post, email angle.")

    print(f"\nDone. {queued} content pieces queued for review.")
    return queued


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Content Multiplier — generate social content for each bar")
    parser.add_argument("--bar", type=str, default=None, help="Process a single bar by name")
    args = parser.parse_args()
    run(bar_name=args.bar)
