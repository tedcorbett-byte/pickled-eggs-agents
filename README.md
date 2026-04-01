# Pickled Eggs Co — Agent System

Multi-agent system for [Pickled Eggs Co](https://pickledeggsco.com), a print-on-demand apparel brand memorializing closed dive bars, gay bars, and neighborhood taverns across Seattle and Denver. Founded by Ted and Andy Corbett.

## Business Goals

1. **Get found in AI search** (ChatGPT, Perplexity, Gemini) via fresh, rich product content
2. **Grow sales** by finding people already mourning closed bars and connecting them to products
3. **Keep Shopify content fresh** for AI search ranking

---

## Architecture

```
pickled-eggs-agents/
│
├── shared/                     # Reusable modules imported by all agents
│   ├── bars.py                 # Single source of truth: BARS list, subreddits, trigger phrases
│   ├── claude_client.py        # Anthropic API wrapper (complete, complete_json)
│   ├── shopify_client.py       # Shopify Admin API wrapper (get/update products)
│   ├── db.py                   # DB abstraction: SQLite locally, Postgres on Railway
│   └── config.py               # All env vars in one place (loads .env)
│
├── agents/
│   ├── listener/               # Community Listener — monitors Reddit
│   ├── content_freshness/      # Content Freshness — refreshes stale Shopify copy
│   ├── content_multiplier/     # Content Multiplier — generates Instagram/Reddit/email content
│   └── bar_scout/              # Bar Scout — finds new bars to memorialize (future)
│
├── ui/
│   └── app.py                  # Shared Flask review dashboard for all agents
│
├── scheduler.py                # APScheduler: runs agents on their schedules
├── requirements.txt
├── .env.example
└── data/                       # SQLite DB lives here in local dev (gitignored)
```

### Data flow

```
Reddit / Shopify / News
        ↓
   Agent scans
        ↓
  Writes to DB (posts / content_drafts / freshness_queue)
        ↓
  Review Dashboard (ui/app.py)
        ↓
  Human approves / skips
        ↓
  You post the reply / push to Shopify
```

---

## Agents

### 1. Community Listener (`agents/listener/`)
- **What**: Scans Reddit for posts mentioning our 13 bars or dive bar nostalgia trigger phrases
- **How**: Uses PRAW to fetch new posts from 14 subreddits; Claude scores each 0-10 and drafts a reply
- **Schedule**: Every 4 hours
- **Output table**: `posts`

### 2. Content Freshness (`agents/content_freshness/`)
- **What**: Finds Shopify products not updated in 60+ days and generates fresh copy
- **How**: Pulls all products via Shopify Admin API; Claude rewrites descriptions with emotional bar history hooks
- **Schedule**: Daily at 9am PT
- **Output table**: `freshness_queue`

### 3. Content Multiplier (`agents/content_multiplier/`)
- **What**: For each bar, generates an Instagram caption, Reddit post draft, and email newsletter angle
- **How**: One Claude call per bar produces all three formats
- **Schedule**: Mondays at 8am PT
- **Output table**: `content_drafts`

### 4. Bar Scout (`agents/bar_scout/`) — *stub, not yet active*
- **What**: Discovers closed bars with enough community attachment to justify a new product
- **Planned sources**: Reddit, Google News RSS, local news sites (The Stranger, Westword)

---

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in your API keys in .env
```

Keys you need to start:
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` — from reddit.com/prefs/apps (create a "script" app)
- `ANTHROPIC_API_KEY` — from console.anthropic.com

For Content Freshness, also add:
- `SHOPIFY_SHOP_DOMAIN` — `pickledeggsco.myshopify.com`
- `SHOPIFY_ACCESS_TOKEN` — from Shopify Partners → Apps

### 3. Run an agent

```bash
# Community Listener (scan + queue results)
python -m agents.listener.agent

# Open the review dashboard
python -m ui.app

# Or run everything through the scheduler
python scheduler.py --now           # run all agents once
python scheduler.py                 # run on schedule (blocking)
```

---

## Database

**Local dev**: SQLite at `data/pickled_eggs.db` — created automatically on first run.

**Railway (production)**: Add the Postgres plugin in Railway. It sets `DATABASE_URL` automatically. The same code runs against Postgres transparently — `shared/db.py` handles the difference.

Tables:
| Table | Owner agent | Purpose |
|---|---|---|
| `posts` | Listener | Reddit posts scored and queued for reply |
| `content_drafts` | Content Multiplier | Instagram / Reddit / email drafts per bar |
| `freshness_queue` | Content Freshness | Refreshed Shopify descriptions awaiting approval |
| `bar_candidates` | Bar Scout | Potential new bars to memorialize |

---

## Adding a new bar

1. Add an entry to `BARS` in `shared/bars.py`
2. Create the Shopify product and update the `url` field
3. Run `python -m agents.content_multiplier.agent --bar "Bar Name"` to generate initial content

---

## Deployment on Railway

1. Push this repo to GitHub
2. Create a new Railway project → Deploy from GitHub
3. Add Postgres plugin (sets `DATABASE_URL` automatically)
4. Add all other env vars from `.env.example` in Railway's Variables tab
5. Set the start command: `python scheduler.py`

The scheduler runs all agents on their schedules. The review dashboard is available at the Railway-assigned URL on port `$FLASK_PORT`.
