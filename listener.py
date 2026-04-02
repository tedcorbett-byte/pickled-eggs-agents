"""
Pickled Eggs Co — Community Listener Agent
==========================================
Monitors Reddit for posts mentioning your bars or dive bar nostalgia.
Drafts authentic replies using Claude for your review.

Setup:
  pip install praw anthropic flask

Run:
  python listener.py          # scan + launch review UI
  python listener.py --scan   # scan only, no UI
  python listener.py --ui     # launch UI with existing results only
"""

import argparse
import json
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import praw
from flask import Flask, jsonify, render_template_string, request

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

REDDIT_CLIENT_ID     = os.getenv("REDDIT_CLIENT_ID", "YOUR_REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "YOUR_REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT    = os.getenv("REDDIT_USER_AGENT", "PickledEggsCo-Listener/1.0")
ANTHROPIC_API_KEY    = os.getenv("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY")

SUBREDDITS = [
    "SeattleWA", "Seattle", "Denver", "Colorado",
    "gaybars", "divebars", "nostalgia", "Bars",
    "AskSeattle", "AskDenver",
    "LGBTQ", "gay", "LGBTHistory",
    "whatisthisplace",
]

BARS = [
    {"name": "Frontier Room",               "city": "Seattle",  "url": "https://pickledeggsco.com/products/frontier-room-seattle"},
    {"name": "Jade Pagoda",                 "city": "Seattle",  "url": "https://pickledeggsco.com/products/jade-pagoda-seattle"},
    {"name": "Manray",                      "city": "Seattle",  "url": "https://pickledeggsco.com/products/manray-seattle"},
    {"name": "Purr Cocktail Lounge",        "city": "Seattle",  "url": "https://pickledeggsco.com/products/purr-seattle"},
    {"name": "R Place",                     "city": "Seattle",  "url": "https://pickledeggsco.com/products/r-place-seattle"},
    {"name": "Re-Bar",                      "city": "Seattle",  "url": "https://pickledeggsco.com/products/re-bar-seattle"},
    {"name": "Red Door",                    "city": "Seattle",  "url": "https://pickledeggsco.com/products/the-red-door-seattle"},
    {"name": "Glacier Lanes",               "city": "Everett",  "url": "https://pickledeggsco.com/products/glacier-lanes-everett-wa"},
    {"name": "Bonnie Brae Tavern",          "city": "Denver",   "url": "https://pickledeggsco.com/products/bonnie-brae-denver"},
    {"name": "Rock Island",                 "city": "Denver",   "url": "https://pickledeggsco.com/products/rock-island-denver"},
    {"name": "Ogden Street South",          "city": "Denver",   "url": "https://pickledeggsco.com/products/ogden-st-south-denver"},
    {"name": "Rainbow Music Hall",          "city": "Denver",   "url": "https://pickledeggsco.com/products/rainbow-music-hall-seattle"},
    {"name": "Fabulous Matterhorn Supper Club", "city": "Boulder", "url": "https://pickledeggsco.com/products/unisex-softstyle-t-shirt"},
]

TRIGGER_PHRASES = [
    "miss that bar", "miss that place", "remember when", "whatever happened to",
    "does anyone remember", "rip to", "closed down", "used to go to",
    "back in the day", "that place is gone", "they closed", "it closed",
    "looking for a gift", "gift for someone who", "gift idea", "dive bar gift",
    "bar shirt", "bar tshirt", "bar t-shirt", "bar merch",
    "gay bar closed", "lesbian bar closed", "queer bar closed",
    "Capitol Hill bar", "Pike Pine bar", "Belltown bar",
    "Colfax bar", "Denver bar", "Boulder bar",
    "dive bar nostalgia", "old seattle", "old denver",
    "neighborhood bar gone", "bar is gone", "used to drink at",
]

MIN_SCORE = 6
DB_PATH = Path("listener.db")


# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
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
    conn.commit()
    conn.close()


def save_post(post: dict):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT OR IGNORE INTO posts (
                id, platform, subreddit, title, body, url, author,
                created_at, matched_bar, matched_triggers,
                relevance_score, relevance_reason, draft_reply, scanned_at
            ) VALUES (
                :id, :platform, :subreddit, :title, :body, :url, :author,
                :created_at, :matched_bar, :matched_triggers,
                :relevance_score, :relevance_reason, :draft_reply, :scanned_at
            )
        """, post)
        conn.commit()
    finally:
        conn.close()


def get_posts(status=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    q = "SELECT * FROM posts"
    if status:
        q += f" WHERE status = '{status}'"
    q += " ORDER BY relevance_score DESC, scanned_at DESC"
    rows = conn.execute(q).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_status(post_id, status):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE posts SET status=?, reviewed_at=? WHERE id=?",
        (status, datetime.now().isoformat(), post_id)
    )
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# MATCHING
# ─────────────────────────────────────────────

def find_matches(text: str) -> tuple[list, list]:
    text_lower = text.lower()
    matched_bars = [b["name"] for b in BARS if b["name"].lower() in text_lower]
    matched_triggers = [t for t in TRIGGER_PHRASES if t.lower() in text_lower]
    return matched_bars, matched_triggers


def bar_url_for(bar_name: str) -> str:
    for b in BARS:
        if b["name"].lower() == bar_name.lower():
            return b["url"]
    return "https://pickledeggsco.com"


# ─────────────────────────────────────────────
# CLAUDE SCORING + REPLY DRAFTING
# ─────────────────────────────────────────────

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

BARS_SUMMARY = "\n".join(f"- {b['name']} ({b['city']}): {b['url']}" for b in BARS)


def score_and_draft(post_title, post_body, matched_bars, matched_triggers, post_url):
    bars_context = ""
    if matched_bars:
        urls = "\n".join(f"  - {b}: {bar_url_for(b)}" for b in matched_bars)
        bars_context = f"\nMatched bars (we have shirts for these):\n{urls}"

    prompt = f"""You are helping Pickled Eggs Co (pickledeggsco.com) find Reddit conversations
where their products are genuinely relevant. Pickled Eggs Co makes graphic t-shirts that
memorialize specific closed bars — dive bars, gay bars, neighborhood taverns — across
Seattle and Denver. Founded by two brothers, Ted and Andy Corbett.

Their bars:
{BARS_SUMMARY}

Reddit post to evaluate:
Title: {post_title}
Body: {post_body[:800]}
{bars_context}
Matched trigger phrases: {', '.join(matched_triggers) if matched_triggers else 'none'}

Task 1 — Score relevance 0-10:
- 9-10: Post directly mentions one of our bars OR is asking for exactly the kind of gift we sell
- 7-8: Strong dive bar / closed bar nostalgia, or Seattle/Denver bar mourning, high purchase intent
- 5-6: General nostalgia or bar culture, loosely relevant
- 0-4: Not relevant, or would feel forced/spammy to reply

Task 2 — If score >= 6, draft a reply (max 120 words):
- Sound like a genuine person who also cares about this stuff, not a brand
- Reference the specific bar or feeling they mentioned
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
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        return json.loads(text)
    except Exception as e:
        print(f"  Claude error: {e}")
        return {"score": 0, "reason": "Claude API error", "draft": ""}


# ─────────────────────────────────────────────
# REDDIT SCANNER
# ─────────────────────────────────────────────

def scan_reddit(limit_per_sub: int = 100):
    print(f"\n{'='*50}")
    print(f"Scanning Reddit — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )

    found = 0
    queued = 0

    for sub_name in SUBREDDITS:
        print(f"\n  r/{sub_name} ...", end=" ", flush=True)
        try:
            sub = reddit.subreddit(sub_name)
            posts_checked = 0

            for submission in sub.new(limit=limit_per_sub):
                posts_checked += 1
                full_text = f"{submission.title} {submission.selftext}"
                matched_bars, matched_triggers = find_matches(full_text)

                if not matched_bars and not matched_triggers:
                    continue

                found += 1
                post_id = f"reddit_{submission.id}"

                conn = sqlite3.connect(DB_PATH)
                exists = conn.execute("SELECT 1 FROM posts WHERE id=?", (post_id,)).fetchone()
                conn.close()
                if exists:
                    continue

                print(f"\n    Found: {submission.title[:60]}...")
                result = score_and_draft(
                    post_title=submission.title,
                    post_body=submission.selftext,
                    matched_bars=matched_bars,
                    matched_triggers=matched_triggers,
                    post_url=f"https://reddit.com{submission.permalink}",
                )

                score = result.get("score", 0)
                print(f"    Score: {score}/10 — {result.get('reason', '')}")

                if score >= MIN_SCORE:
                    queued += 1
                    save_post({
                        "id": post_id,
                        "platform": "reddit",
                        "subreddit": sub_name,
                        "title": submission.title,
                        "body": submission.selftext[:2000],
                        "url": f"https://reddit.com{submission.permalink}",
                        "author": str(submission.author),
                        "created_at": datetime.fromtimestamp(
                            submission.created_utc, tz=timezone.utc
                        ).isoformat(),
                        "matched_bar": ", ".join(matched_bars),
                        "matched_triggers": ", ".join(matched_triggers),
                        "relevance_score": score,
                        "relevance_reason": result.get("reason", ""),
                        "draft_reply": result.get("draft", ""),
                        "scanned_at": datetime.now().isoformat(),
                    })

                time.sleep(0.5)

            print(f"checked {posts_checked} posts")

        except Exception as e:
            print(f"error: {e}")

    print(f"\nDone. Found {found} candidate posts, queued {queued} for review.")
    return queued


# ─────────────────────────────────────────────
# FLASK WEB UI
# ─────────────────────────────────────────────

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pickled Eggs Co — Community Listener</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'IBM Plex Mono', 'Courier New', monospace; background: #0e0c09; color: #e8dcc8; min-height: 100vh; }
  header { background: #181410; border-bottom: 1px solid #2e2720; padding: 1rem 2rem; display: flex; align-items: baseline; gap: 1rem; }
  .logo { font-size: 20px; font-weight: 700; color: #d4820a; letter-spacing: 0.1em; }
  .logo span { color: #7a6e60; font-size: 13px; font-weight: 400; margin-left: 8px; }
  .stats { margin-left: auto; display: flex; gap: 1.5rem; font-size: 12px; color: #7a6e60; }
  .stat strong { color: #d4820a; }
  .filters { background: #181410; border-bottom: 1px solid #2e2720; padding: 0.75rem 2rem; display: flex; gap: 8px; }
  .filter-btn { background: transparent; border: 1px solid #2e2720; border-radius: 4px; padding: 5px 12px; color: #7a6e60; font-size: 12px; cursor: pointer; font-family: inherit; }
  .filter-btn:hover { border-color: #3d3028; color: #e8dcc8; }
  .filter-btn.active { border-color: #d4820a; color: #d4820a; }
  main { max-width: 900px; margin: 0 auto; padding: 1.5rem 2rem; }
  .empty { text-align: center; padding: 4rem; color: #7a6e60; font-size: 13px; }
  .post-card { background: #181410; border: 1px solid #2e2720; border-radius: 6px; margin-bottom: 16px; overflow: hidden; }
  .post-card.approved { border-left: 3px solid #2d6a2d; }
  .post-card.skipped  { border-left: 3px solid #3d3028; opacity: 0.5; }
  .post-head { padding: 14px 16px; border-bottom: 1px solid #2e2720; display: flex; align-items: flex-start; gap: 12px; }
  .score-badge { font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 3px; white-space: nowrap; flex-shrink: 0; }
  .score-high { background: #2d6a2d; color: #6fcf6f; }
  .score-med  { background: #5a4a10; color: #d4a820; }
  .post-title { font-size: 14px; color: #e8dcc8; flex: 1; line-height: 1.4; }
  .post-meta  { font-size: 11px; color: #7a6e60; margin-top: 4px; }
  .post-meta a { color: #d4820a; text-decoration: none; }
  .matched    { font-size: 11px; color: #d4820a; margin-top: 4px; }
  .post-excerpt { font-size: 12px; color: #5F5E5A; padding: 0 16px 10px; white-space: pre-wrap; cursor: pointer; }
  .post-body  { padding: 12px 16px; font-size: 12px; color: #7a6e60; line-height: 1.6; border-bottom: 1px solid #2e2720; display: none; }
  .post-body.open { display: block; }
  .reply-section { padding: 12px 16px; }
  .reply-label { font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: #7a6e60; margin-bottom: 8px; }
  .reply-reason { font-size: 11px; color: #7a6e60; margin-bottom: 8px; font-style: italic; }
  textarea { width: 100%; background: #0e0c09; border: 1px solid #2e2720; border-radius: 4px; padding: 10px; color: #e8dcc8; font-size: 13px; font-family: inherit; resize: vertical; line-height: 1.6; min-height: 100px; }
  textarea:focus { outline: none; border-color: #d4820a; }
  .action-row { display: flex; gap: 8px; margin-top: 10px; align-items: center; }
  .btn { padding: 8px 16px; border-radius: 4px; font-size: 13px; font-family: inherit; cursor: pointer; border: 1px solid; }
  .btn-approve { background: #2d6a2d; border-color: #2d6a2d; color: #6fcf6f; }
  .btn-skip { background: transparent; border-color: #3d3028; color: #7a6e60; }
  .btn-copy { background: transparent; border-color: #3d3028; color: #7a6e60; margin-left: auto; }
  .btn-copy:hover { border-color: #d4820a; color: #d4820a; }
  .char-count { font-size: 11px; color: #7a6e60; }
  .status-pill { font-size: 11px; padding: 3px 10px; border-radius: 10px; }
  .pill-approved { background: #2d6a2d; color: #6fcf6f; }
  .pill-skipped  { background: #2e2720; color: #7a6e60; }
</style>
</head>
<body>
<header>
  <div class="logo">Pickled Eggs Co <span>// Community Listener</span></div>
  <div class="stats">
    <span><strong id="cnt-pending">—</strong> pending</span>
    <span><strong id="cnt-approved">—</strong> approved</span>
    <span><strong id="cnt-skipped">—</strong> skipped</span>
  </div>
</header>
<div class="filters">
  <button class="filter-btn active" onclick="setFilter('pending')">Pending</button>
  <button class="filter-btn" onclick="setFilter('approved')">Approved</button>
  <button class="filter-btn" onclick="setFilter('skipped')">Skipped</button>
  <button class="filter-btn" onclick="setFilter('all')">All</button>
</div>
<main>
  <div id="post-list"></div>
</main>
<script>
let allPosts = [];
let currentFilter = 'pending';

async function load() {
  const r = await fetch('/api/posts');
  allPosts = await r.json();
  updateCounts();
  render();
}

function updateCounts() {
  document.getElementById('cnt-pending').textContent  = allPosts.filter(p=>p.status==='pending').length;
  document.getElementById('cnt-approved').textContent = allPosts.filter(p=>p.status==='approved').length;
  document.getElementById('cnt-skipped').textContent  = allPosts.filter(p=>p.status==='skipped').length;
}

function setFilter(f) {
  currentFilter = f;
  document.querySelectorAll('.filter-btn').forEach(b => {
    b.classList.toggle('active', b.textContent.toLowerCase()===f);
  });
  render();
}

function esc(s) { const d=document.createElement('div');d.textContent=s||'';return d.innerHTML; }

function render() {
  const posts = currentFilter === 'all' ? allPosts : allPosts.filter(p => p.status === currentFilter);
  const el = document.getElementById('post-list');
  if (!posts.length) { el.innerHTML = '<div class="empty">No ' + currentFilter + ' posts.</div>'; return; }
  el.innerHTML = posts.map(p => {
    const isReviewed = p.status !== 'pending';
    const excerpt = (p.body||'').slice(0,200).replace(/\\n/g,' ');
    const scoreClass = p.relevance_score >= 8 ? 'score-high' : 'score-med';
    return `
    <div class="post-card ${isReviewed ? p.status : ''}" id="card-${p.id}">
      <div class="post-head">
        <span class="score-badge ${scoreClass}">${p.relevance_score}/10</span>
        <div style="flex:1">
          <div class="post-title">${esc(p.title)}</div>
          <div class="post-meta">r/${esc(p.subreddit)} · ${esc(p.author)} · <a href="${esc(p.url)}" target="_blank">view on Reddit</a></div>
          ${p.matched_bar ? `<div class="matched">Bar match: ${esc(p.matched_bar)}</div>` : ''}
        </div>
        ${isReviewed ? `<span class="status-pill pill-${p.status}">${p.status}</span>` : ''}
      </div>
      ${excerpt ? `<div class="post-excerpt" onclick="toggleBody('${p.id}')">${esc(excerpt)}${(p.body||'').length>200?'…':''}</div>` : ''}
      <div class="post-body" id="body-${p.id}"><strong>Full post:</strong><br>${esc(p.body)}</div>
      <div class="reply-section">
        <div class="reply-label">Draft reply</div>
        <div class="reply-reason">${esc(p.relevance_reason)}</div>
        <textarea id="reply-${p.id}">${esc(p.draft_reply)}</textarea>
        <div class="action-row">
          ${!isReviewed ? `
            <button class="btn btn-approve" onclick="act('${p.id}','approved')">Approve</button>
            <button class="btn btn-skip" onclick="act('${p.id}','skipped')">Skip</button>
          ` : `<button class="btn btn-skip" onclick="act('${p.id}','pending')">Undo</button>`}
          <span class="char-count">${(p.draft_reply||'').length} chars</span>
          <button class="btn btn-copy" onclick="copyReply('${p.id}')">Copy reply</button>
        </div>
      </div>
    </div>`;
  }).join('');
}

function toggleBody(id) { document.getElementById('body-'+id).classList.toggle('open'); }

async function act(id, status) {
  await fetch('/api/action', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id, status}) });
  await load();
}

async function copyReply(id) {
  const text = document.getElementById('reply-'+id)?.value;
  if (text) {
    await navigator.clipboard.writeText(text);
    const btn = event.target;
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy reply', 1500);
  }
}

load();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/posts")
def api_posts():
    return jsonify(get_posts())

@app.route("/api/action", methods=["POST"])
def api_action():
    data = request.json
    update_status(data["id"], data["status"])
    return jsonify({"ok": True})


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--ui",   action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    init_db()

    if not args.ui:
        scan_reddit(limit_per_sub=args.limit)

    if not args.scan:
        port = int(os.environ.get("PORT", 5050))
        print(f"\nLaunching review UI at http://localhost:{port}")
        app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
