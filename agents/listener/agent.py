"""
Pickled Eggs Co — Community Listener Agent
==========================================
Monitors Reddit for posts mentioning our bars or dive bar nostalgia.
Drafts authentic replies using Claude and queues them for human review.

Run directly:
  python -m agents.listener.agent           # scan + queue results
  python -m agents.listener.agent --limit 50

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
# REDDIT SCANNER
# ─────────────────────────────────────────────

def scan_reddit(limit_per_sub: int = 100):
    print(f"\n{'='*50}")
    print(f"Community Listener — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    init_db()

    found = 0
    queued = 0

    for sub_name in SUBREDDITS:
        print(f"\n  r/{sub_name} ...", end=" ", flush=True)
        try:
            url = f"https://www.reddit.com/r/{sub_name}/new.json?limit={limit_per_sub}"
            response = requests.get(url, headers=REDDIT_HEADERS, timeout=10)

            if response.status_code != 200:
                print(f"error: HTTP {response.status_code}")
                time.sleep(2)
                continue

            posts = response.json().get("data", {}).get("children", [])
            posts_checked = 0

            for child in posts:
                post = child.get("data", {})
                posts_checked += 1
                full_text = f"{post.get('title', '')} {post.get('selftext', '')}"
                matched_bars, matched_triggers = find_matches(full_text)

                if not matched_bars and not matched_triggers:
                    continue

                found += 1
                post_id = f"reddit_{post['id']}"

                if post_exists(post_id):
                    continue

                title = post.get("title", "")
                body = post.get("selftext", "")
                permalink = post.get("permalink", "")
                author = post.get("author", "[deleted]")
                created_utc = post.get("created_utc", 0)

                print(f"\n    Found: {title[:60]}...")
                result = score_and_draft(
                    post_title=title,
                    post_body=body,
                    matched_bars=matched_bars,
                    matched_triggers=matched_triggers,
                    post_url=f"https://reddit.com{permalink}",
                )

                score = result.get("score", 0)
                print(f"    Score: {score}/10 — {result.get('reason', '')}")

                if score >= MIN_RELEVANCE_SCORE:
                    queued += 1
                    save_post({
                        "id": post_id,
                        "platform": "reddit",
                        "subreddit": sub_name,
                        "title": title,
                        "body": body[:2000],
                        "url": f"https://reddit.com{permalink}",
                        "author": author,
                        "created_at": datetime.fromtimestamp(
                            created_utc, tz=timezone.utc
                        ).isoformat(),
                        "matched_bar": ", ".join(matched_bars),
                        "matched_triggers": ", ".join(matched_triggers),
                        "relevance_score": score,
                        "relevance_reason": result.get("reason", ""),
                        "draft_reply": result.get("draft", ""),
                        "scanned_at": datetime.now().isoformat(),
                    })

            print(f"checked {posts_checked} posts")
            time.sleep(2)  # Stay within Reddit's unauthenticated rate limit

        except Exception as e:
            print(f"error: {e}")
            time.sleep(2)

    print(f"\nDone. Found {found} candidate posts, queued {queued} for review.")
    return queued


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Community Listener — scan Reddit for relevant posts")
    parser.add_argument("--limit", type=int, default=100, help="Posts to check per subreddit")
    args = parser.parse_args()
    scan_reddit(limit_per_sub=args.limit)
