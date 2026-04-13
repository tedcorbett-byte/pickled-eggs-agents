# Pickled Eggs Co — Agent System: Project Knowledge Base

## What This Is

Pickled Eggs Co. sells memorial t-shirts for closed bars. Each shirt honors a specific bar that a community has lost — the product is nostalgic, hyper-local, and deeply personal. The core business challenge is: **how do you discover which closed bars people still care about, find the customers who care about them, and keep the content fresh at scale — without a full-time team?**

This codebase is the answer. It's a multi-agent AI system that runs continuously on Railway, automating the research, discovery, and content pipeline so the founder can operate as an editor and decision-maker rather than a researcher or writer.

---

## Business Context

**Current product catalog (~21 bars):**
Seattle (Frontier Room, Jade Pagoda, Manray, Purr, R Place, Re-Bar, Red Door), Everett WA (Glacier Lanes), Denver (Bonnie Brae Tavern, Rock Island, Ogden Street South, Rainbow Music Hall), Boulder (Fabulous Matterhorn Supper Club), Bloomington IN (Peanut Barrel), Ithaca NY (Royal Palm Tavern), Cambridge MA (The Tasty), Lawrence KS (Cadillac Ranch), Rosemead CA (Bahooka), Arlington VA (Bardo Rodeo), Hanover NH (Everything But Anchovies), Cincinnati OH (Sunlite Pool).

Notable themes across the catalog: LGBTQ community bars (Manray, Purr, R Place, Re-Bar, Jade Pagoda), college-town institutions, tiki culture, neighborhood anchors.

**The core discovery insight:** People on Reddit still mourn these places. They post about bars they miss, ask if anyone remembers them, mention them in reunion threads, and use gift-giving moments as a trigger for purchase. The system is designed to find those moments.

---

## System Architecture

### Deployment
- **Platform**: Railway (cloud)
- **Services**: Two — a `worker` (runs the scheduler + agents) and a `web` (runs the Flask review dashboard)
- **Database**: Railway-managed PostgreSQL, environment variable `DATABASE_URL` linked to both services
- **Deploys**: Triggered automatically on push to `main` branch (GitHub)

### File Structure
```
pickled-eggs-agents/
├── agents/
│   ├── listener/agent.py         # Community Listener
│   ├── bar_scout/agent.py        # Bar Scout
│   ├── content_freshness/agent.py
│   └── content_multiplier/agent.py
├── shared/
│   ├── bars.py                   # Single source of truth: BARS, SUBREDDITS, TRIGGER_PHRASES, CANDIDATES
│   ├── db.py                     # DB connection + execute() helper (SQLite local / PostgreSQL on Railway)
│   ├── claude_client.py          # Anthropic API client wrapper
│   ├── config.py                 # Env var loading
│   └── shopify_client.py         # Shopify API client
├── ui/app.py                     # Flask review dashboard (4 tabs)
├── scheduler.py                  # APScheduler entry point
└── listener.py                   # Legacy standalone script (kept for reference)
```

### Agents and Schedules

| Agent | Schedule | Purpose |
|---|---|---|
| Community Listener | Every 4 hours | Scans Reddit for grief/nostalgia posts matching known bars or trigger phrases |
| Content Freshness | Daily at 9am PT | Checks Shopify product descriptions for staleness, flags for refresh |
| Content Multiplier | Mondays at 8am PT | Generates content variants (email, social, etc.) from approved posts |
| Bar Scout | Sundays at 10am PT | Scans Reddit for new bar candidates not yet in the catalog |

---

## Agent Details

### Community Listener (`agents/listener/agent.py`)

**What it does:** Searches Reddit via the Arctic Shift API for posts that reference known bars or match grief/gift trigger phrases. Scores each post 1-10 for relevance using Claude. Saves posts scoring ≥ 6 to the `posts` table for human review.

**Data sources:** Arctic Shift API (`arctic-shift.photon-reddit.com/api/posts/search`) — no auth required, searches by subreddit. Covers ~40 subreddits (city, university, LGBTQ, nostalgia communities).

**Key queries:** Two query types run per subreddit:
1. Bar-name queries (one per bar in `BARS`)
2. Keyword queries (`KEY_QUERIES`) including: dive bar nostalgia, gift for bar lover, reunion/alumni bar phrases, LGBTQ bar closure phrases

**Rate limiting:** 2-second sleep between queries; retries on HTTP 429 and 422 (Arctic Shift timeout signals).

**Scoring:** Claude receives post title + body and returns a 1-10 relevance score with reasoning and a draft reply suggestion.

**DB write:** `INSERT INTO posts (...) ON CONFLICT (id) DO NOTHING` — PostgreSQL-compatible.

**"New post" definition:** A post is "new" if its `id` doesn't already exist in the `posts` table. Posts are deduplicated across runs.

### Bar Scout (`agents/bar_scout/agent.py`)

**What it does:** Discovers *new* bars not yet in the catalog that have community grief signals. Scores candidates on a structured rubric, saves them to `bar_candidates` table with `status="discovered"`. Never graduates a candidate to `BARS` automatically — that always requires human action via the UI.

**Grief Rubric (0-100 scale):** 9 signals, scored 0-5 each with weights:

| Signal | Weight |
|---|---|
| Years in operation | 2x |
| Reddit signal strength | 2x |
| Press coverage | 2x |
| Social grief intensity | 1.5x |
| Neighborhood anchor | 1.5x |
| Community specificity | 1.5x |
| Story richness | 1.5x |
| Recency of closure | 1x |
| Design potential | 1x |

Max weighted sum = 70, normalized to 0-100.

**Score thresholds:** 75+ = Build it, 60-74 = Research more, 40-59 = Watchlist, 0-39 = Pass.

**Instant disqualifiers:** Still open, chain/franchise, no community grief evidence, or not a bar/bar-adjacent venue.

**Candidate status lifecycle:** `discovered` → `approved` → `graduated` (or `rejected` at any stage). Graduation copies the bar into `shared/bars.py CANDIDATES` list via a UI modal with a Python snippet.

**Searches:** 13 cities × 6 general subreddits × 13 queries each.

### Content Freshness (`agents/content_freshness/agent.py`)

Checks Shopify product descriptions against a freshness standard. Flags products that need copy refreshes and surfaces them in the review dashboard.

### Content Multiplier (`agents/content_multiplier/agent.py`)

Takes approved listener posts and generates content variants — email copy, social posts, or other formats — using Claude. Outputs saved to the `posts` table for review.

---

## Shared Infrastructure

### `shared/bars.py` — Source of Truth

Three key lists:
- `BARS` — current product catalog (21 bars). Each entry: name, city, state, Shopify URL, description.
- `CANDIDATES` — pre-seeded bar candidates for future research. Currently empty; populated manually or via Bar Scout graduation.
- `TRIGGER_PHRASES` — keyword phrases used by the Listener for non-bar-name matching.
- `SUBREDDITS` — full list of subreddits to scan.

**Rule:** All agents import from `shared/bars.py`. This is the single source of truth. Updating a bar's description or URL here propagates everywhere.

### `shared/db.py`

Handles both SQLite (local dev) and PostgreSQL (Railway). The `execute()` helper converts `?` placeholders to `%s` for PostgreSQL. **Important:** it does NOT handle SQL dialect differences beyond placeholder syntax — dialect-specific syntax (like `ON CONFLICT`) must be written to be compatible with both.

### `shared/claude_client.py`

Thin wrapper around the Anthropic Python SDK. All agents use this for Claude calls.

---

## Review Dashboard (`ui/app.py`)

Flask app with four tabs:

| Tab | Table | Actions |
|---|---|---|
| Community Listener | `posts` | Approve, Skip |
| Content Multiplier | `posts` (multiplier type) | Approve, Skip |
| Content Freshness | `posts` (freshness type) | Approve, Skip |
| Bar Scout | `bar_candidates` | Approve, Reject, Graduate |

**Graduate flow (Bar Scout tab):** When a candidate is graduated, the UI shows a modal with a pre-formatted Python dict ready to paste into `shared/bars.py CANDIDATES`. The human pastes it, commits, and deploys — this is intentional. Catalog additions are a deliberate editorial decision.

**Header stats:** Each tab shows a count of items in each status (e.g., "3 discovered / 1 approved / 0 rejected").

**API routes:**
- `GET /api/items?tab=<tab>` — paginated item list
- `POST /api/action` — approve/reject/skip with optional notes
- `POST /api/graduate` — graduate a bar candidate (Bar Scout only)

---

## Key Design Decisions

**Human-in-the-loop for catalog additions.** Automated discovery is fine; adding a bar to the catalog is a business and brand decision. The system surfaces candidates but never adds them to `BARS` without the founder's explicit action.

**Arctic Shift over Reddit API.** The official Reddit API has restrictive rate limits and requires account authentication. Arctic Shift provides full search access with no auth and handles the rate limiting gracefully (HTTP 422 means "slow down," same as 429).

**Grief score as a compass, not a gate.** The rubric helps prioritize research but isn't a hard cutoff. A bar scoring 45 might still be worth pursuing if it has a strong personal story.

**PostgreSQL-compatible SQL from the start.** After encountering `INSERT OR IGNORE` failures (SQLite-only syntax) in production, all DB writes use `ON CONFLICT (id) DO NOTHING`, which works in both environments.

---

## Open Threads / Future Directions

- **Reddit API credentials**: Account still being aged up before applying for API access. Arctic Shift is the current data source; Reddit's own API would allow comment scanning and DM outreach.
- **Shopify URL cleanup**: Bardo Rodeo has a mismatched URL slug (cosmetic issue, not functional).
- **Bar Scout graduation workflow**: Currently generates a Python snippet for manual paste. Could be automated to write directly to `shared/bars.py` via a file edit, but manual review is preferred at current catalog size.
- **Outreach agent**: Not yet built. The natural next agent would take approved Listener posts and draft a personalized Reddit reply or DM to the OP, introducing the relevant product.
- **Demand validation before production**: Current model is to discover grief signals first, then decide whether to add a bar. Could be inverted — run a pre-order or waitlist before committing to a new shirt design.
- **Geographic expansion**: Current catalog skews Pacific Northwest and Colorado. Bar Scout queries cover 13 cities including Chicago, Austin, Nashville, Portland, San Francisco, New York — candidates from these cities would diversify the catalog.
- **Gift occasion triggers**: "College reunion," "alumni weekend," "homecoming" queries added to Listener. These map to high-intent purchase moments. Worth exploring as a paid search or email segment.
- **LGBTQ bar focus**: Multiple bars in current catalog are former LGBTQ community spaces. The closure of gay bars is a documented cultural trend with active online communities. Strong signal-to-noise for the listener.
