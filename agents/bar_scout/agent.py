"""
Pickled Eggs Co — Bar Scout Agent
===================================
Scans Reddit for posts mourning closed bars that could become future
Pickled Eggs Co products. Scores each candidate using the Grief Rubric
(0-100) and writes discoveries to bar_candidates for human review.

GRIEF RUBRIC — 9 signals scored 0-5 each, weighted:
  2x  — Years in operation, Reddit signal, Press coverage
  1.5x — Social grief, Neighborhood anchor, Community specificity, Story richness
  1x  — Recency of closure, Design potential
  Max weighted sum = 70, normalized to 0-100.

DECISION THRESHOLDS:
  75-100 — Build it       (proceed to product creation)
  60-74  — Research more  (deeper search needed)
  40-59  — Watchlist      (re-check in 90 days)
   0-39  — Pass           (insufficient grief community)

INSTANT DISQUALIFIERS (any = skip entirely):
  - Actively disputed closure / owner plans to reopen
  - Closure associated with harm / scandal
  - Story too thin to write
  - Too similar to existing catalog

Run directly:
  python -m agents.bar_scout.agent
  python -m agents.bar_scout.agent --days 60

Or via scheduler.py (recommended: weekly).
"""
import argparse
import json
import time
import uuid
from datetime import datetime

import requests

from shared.bars import BARS, CANDIDATES
from shared.claude_client import complete_json
from shared.config import REDDIT_USER_AGENT
from shared.db import get_conn, execute, fetchone

REDDIT_HEADERS = {"User-Agent": REDDIT_USER_AGENT or "PickledEggsCo-BarScout/1.0"}

ARCTIC_BASE   = "https://arctic-shift.photon-reddit.com/api/posts/search"
ARCTIC_FIELDS = "id,title,author,subreddit,created_utc,selftext,url"

# Minimum normalized grief score (0-100) to save a candidate.
# 40 = bottom of Watchlist threshold — below this is "Pass."
MIN_GRIEF_SCORE = 40

# Weights per signal (must match SIGNAL_KEYS order)
SIGNAL_WEIGHTS = {
    "years_in_operation":    2.0,
    "reddit_signal":         2.0,
    "press_coverage":        2.0,
    "social_grief":          1.5,
    "neighborhood_anchor":   1.5,
    "community_specificity": 1.5,
    "story_richness":        1.5,
    "recency_of_closure":    1.0,
    "design_potential":      1.0,
}
MAX_WEIGHTED_SUM = 70.0   # sum of (5 * weight) for all signals


def compute_grief_score(breakdown: dict) -> int:
    """Normalize weighted signal sum to 0-100."""
    weighted = sum(breakdown.get(k, 0) * w for k, w in SIGNAL_WEIGHTS.items())
    return round(weighted / MAX_WEIGHTED_SUM * 100)


def grief_label(score: int) -> str:
    if score >= 75:  return "Build it"
    if score >= 60:  return "Research more"
    if score >= 40:  return "Watchlist"
    return "Pass"


# ─────────────────────────────────────────────
# SEARCH TARGETS
# ─────────────────────────────────────────────

BAR_SCOUT_QUERIES = [
    "bar closed",
    "dive bar closed",
    "gay bar closed",
    "favorite bar closed",
    "miss that bar",
    "neighborhood bar closed",
    "bar shut down",
    "bar closing forever",
    "that bar is gone",
    "remember that bar",
    "bar we used to go to",
    "queer bar closed",
    "lesbian bar closed",
]

SCOUT_SUBREDDITS = {
    "Seattle":     ["SeattleWA", "Seattle", "AskSeattle", "SeattleHistory"],
    "Denver":      ["Denver", "AskDenver", "DenverHistory", "Colorado"],
    "Boulder":     ["Boulder", "Colorado"],
    "Bloomington": ["bloomington", "IndianaUniversity"],
    "Ithaca":      ["ithaca", "Cornell"],
    "Cambridge":   ["cambridge", "boston", "Harvard"],
    "Lawrence":    ["lawrence"],
    "Everett":     ["Everett", "washingtonstate"],
    "Rosemead":    ["LosAngeles"],
    "Arlington":   ["nova", "arlington"],
    "Hanover":     ["NewHampshire", "Dartmouth"],
    "Cincinnati":  ["cincinnati"],
}

GENERAL_SCOUT_SUBREDDITS = [
    "divebars", "gaybars", "nostalgia", "Bars", "LGBTHistory", "BarCulture",
]


# ─────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────

def init_db():
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS bar_candidates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                city TEXT,
                state TEXT,
                description TEXT,
                source_url TEXT,
                source_subreddit TEXT,
                evidence TEXT,
                grief_score INTEGER,
                grief_breakdown TEXT,
                disqualifiers TEXT,
                status TEXT DEFAULT 'discovered',
                notes TEXT,
                discovered_at TEXT,
                updated_at TEXT
            )
        """)
        # Seed any static CANDIDATES from bars.py
        for c in CANDIDATES:
            if fetchone(conn,
                "SELECT 1 FROM bar_candidates WHERE name=? AND city=?",
                (c["name"], c.get("city", ""))
            ):
                continue
            execute(conn, """
                INSERT INTO bar_candidates
                    (id, name, city, state, description, status, grief_score, notes, discovered_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"seed_{c['name'].lower().replace(' ', '_')}",
                c["name"], c.get("city", ""), c.get("state", ""),
                c.get("description", ""), c.get("status", "discovered"),
                c.get("grief_score", 0), c.get("notes", ""),
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))


# ─────────────────────────────────────────────
# DATABASE HELPERS
# ─────────────────────────────────────────────

def candidate_exists(name: str, city: str) -> bool:
    """True if this bar is already in our product line or candidates DB."""
    for b in BARS:
        if b["name"].lower() == name.lower() and b["city"].lower() == city.lower():
            return True
    with get_conn() as conn:
        return fetchone(conn,
            "SELECT 1 FROM bar_candidates WHERE lower(name)=lower(?) AND lower(city)=lower(?)",
            (name, city),
        ) is not None


def save_candidate(*, name, city, state, description, source_url,
                   source_subreddit, evidence, grief_score, grief_breakdown, disqualifiers):
    with get_conn() as conn:
        execute(conn, """
            INSERT INTO bar_candidates
                (id, name, city, state, description,
                 source_url, source_subreddit, evidence,
                 grief_score, grief_breakdown, disqualifiers,
                 status, discovered_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'discovered', ?, ?)
        """, (
            str(uuid.uuid4()),
            name, city, state, description,
            source_url, source_subreddit, evidence[:600],
            grief_score,
            json.dumps(grief_breakdown),
            json.dumps(disqualifiers),
            datetime.now().isoformat(),
            datetime.now().isoformat(),
        ))


# ─────────────────────────────────────────────
# ARCTIC SHIFT FETCHER
# ─────────────────────────────────────────────

def arctic_search(query: str, subreddit: str, days_back: int = 30, limit: int = 25) -> list:
    """Fetch posts from Arctic Shift. Retries once on 429."""
    params = {
        "query":     query,
        "after":     f"{days_back}d",
        "limit":     limit,
        "sort":      "desc",
        "fields":    ARCTIC_FIELDS,
        "subreddit": subreddit,
    }
    for attempt in range(2):
        try:
            resp = requests.get(ARCTIC_BASE, params=params, headers=REDDIT_HEADERS, timeout=15)
            if resp.status_code == 429:
                wait = 10 if attempt == 0 else 30
                print(f"    429 rate limit — waiting {wait}s then retrying...")
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                print(f"    HTTP {resp.status_code}: {resp.text[:200]}")
                return []
            return resp.json().get("data", [])
        except Exception as e:
            print(f"    Error: {e}")
            return []
    print(f"    Gave up after retries for '{query}' in r/{subreddit}")
    return []


# ─────────────────────────────────────────────
# SCORING (Claude + Grief Rubric)
# ─────────────────────────────────────────────

def score_candidate(title: str, body: str, subreddit: str) -> dict:
    """
    Ask Claude to determine if the post surfaces a scoreable closed bar,
    then apply the full Grief Rubric (9 signals, 0-5 each) and check
    4 instant disqualifiers. Returns a dict or {"is_candidate": false}.
    """
    known = ", ".join(f"{b['name']} ({b['city']}, {b['state']})" for b in BARS)

    prompt = f"""You are helping Pickled Eggs Co identify closed bars worth memorializing as t-shirts.

Pickled Eggs Co honors defunct dive bars, neighborhood taverns, and beloved local institutions.
They particularly value:
  - Dive bars with decades of history and a distinct personality
  - Gay / LGBTQ / queer bars and community spaces
  - College-town institutions (multiple graduating classes → deep attachment)
  - Neighborhood anchors that shaped local identity

BARS ALREADY IN THE CATALOG — skip these, do not surface them again:
{known}

Reddit post from r/{subreddit}:
Title: {title}
Body: {body[:900]}

STEP 1 — Is this post about a specific closed or closing bar?
  - If no specific bar is named or clearly implied, return {{"is_candidate": false}}
  - If the bar is already in the catalog above, return {{"is_candidate": false}}
  - If yes, proceed to Steps 2 and 3.

STEP 2 — Extract:
  - name: The bar's name
  - city: City it was in
  - state: Two-letter US state code (or country if outside USA)
  - description: 2-3 sentences capturing what made it special, who went there, what it meant

STEP 3 — Score each signal 0-5 (integers only), then check disqualifiers:

SIGNALS (score 0-5 each):
  years_in_operation    — 0=unknown/short, 1=<5yr, 2=5-10yr, 3=10-20yr, 4=20-30yr, 5=30+yr
  reddit_signal         — 0=this post only, 1=few posts, 2=several, 3=active threads, 4=many mourning posts, 5=viral/massive
  press_coverage        — 0=none, 1=local mention, 2=local article, 3=local feature, 4=regional/LGBTQ press, 5=national coverage
  social_grief          — 0=none, 1=a comment or two, 2=some grief, 3=clear nostalgia, 4=memorial posts/tributes, 5=GoFundMe/vigils
  neighborhood_anchor   — 0=not distinctive, 1=known locally, 2=neighborhood staple, 3=defined its block, 4=defined its neighborhood, 5=defined the city
  community_specificity — 0=generic, 1=slight niche, 2=clear community (LGBTQ/POC/etc), 3=tight-knit community, 4=beloved by specific group, 5=irreplaceable safe space
  story_richness        — 0=nothing memorable, 1=vague affection, 2=some details, 3=incidents/characters, 4=rich lore, 5=legendary stories
  recency_of_closure    — 0=60+yr ago, 1=30-60yr, 2=15-30yr, 3=5-15yr (nostalgia peak), 4=2-5yr (active grief), 5=within 2yr
  design_potential      — 0=nothing to work with, 1=weak, 2=okay name/era, 3=good aesthetic, 4=great name+era, 5=iconic visual identity

INSTANT DISQUALIFIERS (true = disqualified):
  disputed_closure   — Ongoing legal fight or owner publicly plans to reopen
  harm_associated    — Scandal, crime, or abuse dominates the story
  story_too_thin     — No memorable details, incidents, or characters found anywhere
  too_similar        — Same city AND same bar type as something already in the catalog

Respond in exactly this JSON format:
{{
  "is_candidate": true,
  "name": "<bar name>",
  "city": "<city>",
  "state": "<state>",
  "description": "<2-3 sentences>",
  "breakdown": {{
    "years_in_operation": <0-5>,
    "reddit_signal": <0-5>,
    "press_coverage": <0-5>,
    "social_grief": <0-5>,
    "neighborhood_anchor": <0-5>,
    "community_specificity": <0-5>,
    "story_richness": <0-5>,
    "recency_of_closure": <0-5>,
    "design_potential": <0-5>
  }},
  "disqualifiers": {{
    "disputed_closure": false,
    "harm_associated": false,
    "story_too_thin": false,
    "too_similar": false
  }}
}}

Or if not a candidate: {{"is_candidate": false}}"""

    try:
        return complete_json(prompt, max_tokens=600)
    except Exception as e:
        print(f"  Claude error: {e}")
        return {"is_candidate": False}


# ─────────────────────────────────────────────
# MAIN SCANNER
# ─────────────────────────────────────────────

def scan_for_candidates(days_back: int = 30):
    print(f"\n{'='*50}")
    print(f"Bar Scout — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Looking back {days_back} days | min grief score {MIN_GRIEF_SCORE}/100")
    print(f"{'='*50}")

    init_db()

    # Build flat deduplicated subreddit list
    all_subs = []
    for subs in SCOUT_SUBREDDITS.values():
        all_subs.extend(subs)
    all_subs.extend(GENERAL_SCOUT_SUBREDDITS)
    all_subs = list(dict.fromkeys(all_subs))   # preserve order, remove dupes

    seen_post_ids = set()
    discovered    = 0

    for sub in all_subs:
        for query in BAR_SCOUT_QUERIES:
            print(f"  r/{sub} | \"{query}\" ...", end=" ", flush=True)
            posts = arctic_search(query, subreddit=sub, days_back=days_back)
            new_posts = [p for p in posts if p["id"] not in seen_post_ids]
            seen_post_ids.update(p["id"] for p in posts)
            print(f"{len(new_posts)} posts")

            for post in new_posts:
                title = post.get("title", "")
                body  = post.get("selftext", "")
                url   = post.get("url", "")

                result = score_candidate(title, body, sub)

                if not result.get("is_candidate"):
                    continue

                # Check disqualifiers
                disq = result.get("disqualifiers", {})
                if any(disq.values()):
                    active = [k for k, v in disq.items() if v]
                    print(f"    Disqualified ({', '.join(active)}): {result.get('name', '?')}")
                    continue

                breakdown = result.get("breakdown", {})
                grief_score = compute_grief_score(breakdown)
                name = result.get("name", "").strip()
                city = result.get("city", "").strip()

                print(f"    {name} ({city}) — {grief_score}/100 [{grief_label(grief_score)}]")

                if grief_score < MIN_GRIEF_SCORE:
                    print(f"    Below threshold, skipping.")
                    continue

                if candidate_exists(name, city):
                    print(f"    Already known.")
                    continue

                discovered += 1
                save_candidate(
                    name             = name,
                    city             = city,
                    state            = result.get("state", ""),
                    description      = result.get("description", ""),
                    source_url       = url,
                    source_subreddit = sub,
                    evidence         = f"{title}\n\n{body[:400]}",
                    grief_score      = grief_score,
                    grief_breakdown  = breakdown,
                    disqualifiers    = disq,
                )
                print(f"    SAVED.")

            time.sleep(2)

    print(f"\nDone. Scanned {len(seen_post_ids)} unique posts. Discovered {discovered} new candidates.")
    return discovered


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bar Scout — find closed bar candidates via Arctic Shift")
    parser.add_argument("--days", type=int, default=30, help="Days back to search (default 30)")
    args = parser.parse_args()
    scan_for_candidates(days_back=args.days)
