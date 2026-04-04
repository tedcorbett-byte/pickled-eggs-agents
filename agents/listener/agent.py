"""
Pickled Eggs Co — Community Listener Agent
==========================================
Monitors Reddit for posts mentioning our bars or dive bar nostalgia.
Uses the Arctic Shift public API (no credentials required) so it works
from any IP including Railway's cloud servers.

Drafts authentic replies using Claude and queues them for human review.

Run directly:
  python -m agents.listener.agent           # scan + queue results
  python -m agents.listener.agent --days 14  # look back 14 days (default 7)

Or via scheduler.py / Railway cron.
"""
import argparse
import time
from datetime import datetime, timezone

import requests

from shared.bars import BARS, SUBREDDITS, TRIGGER_PHRASES, BARS_SUMMARY, bar_url_for
from shared.claude_client import complete_json
from shared.config import REDDIT_USER_AGENT, MIN_RELEVANCE_SCORE
from shared.db import get_conn, execute, fetchone

REDDIT_HEADERS = {"User-Agent": REDDIT_USER_AGENT or "PickledEggsCo-Listener/1.0"}

ARCTIC_BASE   = "https://arctic-shift.photon-reddit.com/api/posts/search"
ARCTIC_FIELDS = "id,title,author,subreddit,created_utc,selftext,url,permalink"

# Simple keyword queries for Phase 2 subreddit searches.
# Each is sent as a separate request — keeps Arctic Shift happy.
KEY_QUERIES = [
    "dive bar closed",
    "bar shirt gift",
    "miss that bar",
    "gay bar closed",
    "used to drink there",
]


# ─────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────

def init_db():
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                platform TEXT,
                subreddit TEXT,
                title TEXT,
                body TEXT,
                url TEXT,
                author TEXT,
                created_at TEXT,
                matched_bar TEXT,
                matched_triggers TEXT,
                relevance_score INTEGER,
                relevance_reason TEXT,
                draft_reply TEXT,
                status TEXT DEFAULT 'pending',
                reviewed_at TEXT,
                scanned_at TEXT
            )
        """)


# ─────────────────────────────────────────────
# DATABASE HELPERS
# ─────────────────────────────────────────────

def save_post(post: dict):
    with get_conn() as conn:
        execute(conn, """
            INSERT OR IGNORE INTO posts (
                id, platform, subreddit, title, body, url, author,
                created_at, matched_bar, matched_triggers,
                relevance_score, relevance_reason, draft_reply, scanned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            post["id"], post["platform"], post["subreddit"],
            post["title"], post["body"], post["url"], post["author"],
            post["created_at"], post["matched_bar"], post["matched_triggers"],
            post["relevance_score"], post["relevance_reason"],
            post["draft_reply"], post["scanned_at"],
        ))


def post_exists(post_id: str) -> bool:
    with get_conn() as conn:
        return fetchone(conn, "SELECT 1 FROM posts WHERE id = ?", (post_id,)) is not None


# ─────────────────────────────────────────────
# MATCHING
# ─────────────────────────────────────────────

def find_matches(text: str) -> tuple[list, list]:
    text_lower = text.lower()
    matched_bars     = [b["name"] for b in BARS if b["name"].lower() in text_lower]
    matched_triggers = [t for t in TRIGGER_PHRASES if t.lower() in text_lower]
    return matched_bars, matched_triggers


# ─────────────────────────────────────────────
# ARCTIC SHIFT FETCHER
# ─────────────────────────────────────────────

def arctic_search(query: str, subreddit: str = None, days_back: int = 7, limit: int = 25) -> list:
    """Fetch posts from Arctic Shift matching a keyword query."""
    params = {
        "query":  query,
        "after":  f"{days_back}d",
        "limit":  limit,
        "sort":   "desc",
        "fields": ARCTIC_FIELDS,
    }
    if subreddit:
        params["subreddit"] = subreddit

    try:
        resp = requests.get(ARCTIC_BASE, params=params, headers=REDDIT_HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"    Arctic Shift HTTP {resp.status_code} for query '{query}'")
            return []
        return resp.json().get("data", [])
    except Exception as e:
        print(f"    Arctic Shift error: {e}")
        return []


# ─────────────────────────────────────────────
# SCORING + REPLY DRAFTING
# ─────────────────────────────────────────────

def score_and_draft(post_title, post_body, matched_bars, matched_triggers, post_url):
    bars_context = ""
    if matched_bars:
        urls = "\n".join(f"  - {b}: {bar_url_for(b)}" for b in matched_bars)
        bars_context = f"\nMatched bars (we have shirts for these):\n{urls}"

    prompt = f"""You are helping Pickled Eggs Co (pickledeggsco.com) find Reddit conversations
where their products are genuinely relevant.

About Pickled Eggs Co:
Pickled Eggs Co is an American apparel brand that preserves and reimagines the culture of
defunct dive bars — the neighborhood taverns, working-class watering holes, and forgotten
local institutions that shaped American social life. Founded by two brothers, Ted and Andy
Corbett, raised in Denver and living in Seattle. The brand produces graphic t-shirts that
honor specific closed bars, their regulars, and the broader culture of unpretentious drinking
in America. Pickled Eggs Co operates at the intersection of cultural preservation, nostalgia,
and wearable storytelling — offering a tangible connection to places that exist now only in memory.

Their bars (with histories):
{BARS_SUMMARY}

Reddit post to evaluate:
Title: {post_title}
Body: {post_body[:800]}
{bars_context}
Matched trigger phrases: {', '.join(matched_triggers) if matched_triggers else 'none'}

Task 1 — Score relevance 0-10:
- 9-10: Post directly mentions one of our bars OR is asking for exactly the kind of gift we sell
- 7-8: Strong dive bar / closed bar nostalgia, or mourning a specific closed bar, high purchase intent
- 5-6: General nostalgia or bar culture, loosely relevant
- 0-4: Not relevant, or would feel forced/spammy to reply

Task 2 — If score >= 6, draft a reply (max 120 words):
- Sound like a genuine person who also cares about this stuff, not a brand
- Reference the specific bar's history or the feeling they mentioned — use the bar descriptions above
- Mention Pickled Eggs Co naturally, not as an ad
- Include the product URL only if a specific bar matches — otherwise link to pickledeggsco.com
- Never say "I work for" or "I'm the owner" — just "we make shirts" or "there's a brand called Pickled Eggs Co"
- If score < 6, return empty string for draft

Respond in this exact JSON format:
{{
  "score": <integer 0-10>,
  "reason": "<one sentence explaining the score>",
  "draft": "<reply text or empty string>"
}}"""

    try:
        return complete_json(prompt, max_tokens=600)
    except Exception as e:
        print(f"  Claude error: {e}")
        return {"score": 0, "reason": "Claude API error", "draft": ""}


# ─────────────────────────────────────────────
# PROCESS A SINGLE POST
# ─────────────────────────────────────────────

def process_post(post: dict, queued_count: int) -> int:
    """Score, draft, and save a single raw Arctic Shift post dict. Returns updated queued count."""
    title    = post.get("title", "")
    body     = post.get("selftext", "")
    author   = post.get("author", "[deleted]")
    sub      = post.get("subreddit", "")
    url      = post.get("url") or f"https://reddit.com{post.get('permalink', '')}"
    post_id  = f"reddit_{post['id']}"
    created  = post.get("created_utc", 0)

    if post_exists(post_id):
        return queued_count

    full_text = f"{title} {body}"
    matched_bars, matched_triggers = find_matches(full_text)

    print(f"\n    Found: {title[:70]}...")
    result = score_and_draft(
        post_title=title,
        post_body=body,
        matched_bars=matched_bars,
        matched_triggers=matched_triggers,
        post_url=url,
    )

    score = result.get("score", 0)
    print(f"    Score: {score}/10 — {result.get('reason', '')}")

    if score >= MIN_RELEVANCE_SCORE:
        queued_count += 1
        save_post({
            "id":               post_id,
            "platform":         "reddit",
            "subreddit":        sub,
            "title":            title,
            "body":             body[:2000],
            "url":              url,
            "author":           author,
            "created_at":       datetime.fromtimestamp(created, tz=timezone.utc).isoformat(),
            "matched_bar":      ", ".join(matched_bars),
            "matched_triggers": ", ".join(matched_triggers),
            "relevance_score":  score,
            "relevance_reason": result.get("reason", ""),
            "draft_reply":      result.get("draft", ""),
            "scanned_at":       datetime.now().isoformat(),
        })

    return queued_count


# ─────────────────────────────────────────────
# MAIN SCANNER
# ─────────────────────────────────────────────

def scan_reddit(days_back: int = 7):
    print(f"\n{'='*50}")
    print(f"Community Listener (Arctic Shift) — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Looking back {days_back} days")
    print(f"{'='*50}")

    init_db()

    seen_ids = set()   # deduplicate across searches
    queued   = 0

    # ── Phase 1: Search each bar name across all of Reddit ──────────────────
    print(f"\n[Phase 1] Searching {len(BARS)} bar names across Reddit...")
    for bar in BARS:
        print(f"  \"{bar['name']}\" ...", end=" ", flush=True)
        posts = arctic_search(f'"{bar["name"]}"', days_back=days_back, limit=25)
        new_posts = [p for p in posts if p["id"] not in seen_ids]
        seen_ids.update(p["id"] for p in posts)
        print(f"{len(new_posts)} new posts")
        for post in new_posts:
            queued = process_post(post, queued)
        time.sleep(1)

    # ── Phase 2: Trigger queries in target subreddits ───────────────────────
    print(f"\n[Phase 2] Searching {len(KEY_QUERIES)} queries across {len(SUBREDDITS)} subreddits...")
    for sub in SUBREDDITS:
        for query in KEY_QUERIES:
            print(f"  r/{sub} | \"{query}\" ...", end=" ", flush=True)
            posts = arctic_search(query, subreddit=sub, days_back=days_back, limit=25)
            new_posts = [p for p in posts if p["id"] not in seen_ids]
            seen_ids.update(p["id"] for p in posts)
            print(f"{len(new_posts)} new posts")
            for post in new_posts:
                queued = process_post(post, queued)
            time.sleep(0.5)

    print(f"\nDone. Scanned {len(seen_ids)} unique posts, queued {queued} for review.")
    return queued


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Community Listener — scan Reddit via Arctic Shift")
    parser.add_argument("--days", type=int, default=7, help="How many days back to search (default 7)")
    args = parser.parse_args()
    scan_reddit(days_back=args.days)
