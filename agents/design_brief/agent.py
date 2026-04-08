"""
Design Brief Agent — Pickled Eggs Co
Triggered when a bar is graduated via the Bar Scout UI.
Generates a structured creative design brief using Claude and saves to DB.
Also searches for historical reference image sources.
"""

import json
import logging
import time
import uuid
from datetime import datetime

from shared.claude_client import complete_json
from shared.db import execute, fetchall, fetchone, get_conn
from shared.bars import BARS

logger = logging.getLogger(__name__)

BRIEF_PROMPT = """
You are a creative director for Pickled Eggs Co, an American apparel brand that
makes graphic t-shirts honoring closed dive bars, gay bars, and neighborhood
institutions. The aesthetic is rooted in authenticity — no irony, no nostalgia
kitsch. Think worn-in, era-appropriate, like the shirt could have actually
existed when the bar was open.

Generate a structured design brief for a new shirt honoring the bar below.

BAR NAME: {name}
CITY / STATE: {city}, {state}
KNOWN HISTORY: {description}
THEMES: {themes}

Return your response as valid JSON matching this exact schema:

{{
  "bar_name": "string",
  "era": "string — decade or range, e.g. '1970s–80s' or 'Late 1990s'",
  "vibe": "string — 2–3 sentence character description of the bar",
  "design_directions": [
    {{
      "name": "string — short label, e.g. 'Vintage Matchbook'",
      "description": "string — 3–4 sentences on the concept, visual approach, and feel",
      "typography": "string — font style direction, e.g. 'Condensed slab serif, hand-stamped feel'",
      "palette": ["string", "string", "string"],
      "key_visual_elements": ["string", "string", "string"],
      "reference_era": "string — specific visual era/genre to reference"
    }}
  ],
  "avoid": ["string — things that would feel wrong or off-brand"],
  "image_search_queries": [
    "string — a specific archival search query to find historical photos of this bar or era"
  ],
  "archival_sources": [
    {{
      "source": "string — name of archive or library",
      "url": "string — search URL or collection page",
      "notes": "string — what to look for there"
    }}
  ],
  "brief_notes": "string — any other creative context the designer should know"
}}

Return ONLY valid JSON. No preamble, no markdown fences.
""".strip()


def detect_themes(bar: dict) -> str:
    desc = (bar.get("description") or "").lower()
    name = bar["name"].lower()
    themes = []

    lgbtq_terms = ["gay", "lesbian", "queer", "lgbtq", "drag", "nightclub", "video bar"]
    if any(t in desc or t in name for t in lgbtq_terms):
        themes.append("LGBTQ community space")

    music_terms = ["music", "venue", "concert", "band", "jukebox", "dance"]
    if any(t in desc or t in name for t in music_terms):
        themes.append("live music / dancing")

    if any(t in desc or t in name for t in ["tavern", "neighborhood", "local", "regulars"]):
        themes.append("neighborhood anchor")

    if any(t in desc or t in name for t in ["bowling", "pool", "arcade"]):
        themes.append("leisure / working class recreation")

    if any(t in desc or t in name for t in ["supper club", "tiki", "lounge", "cocktail"]):
        themes.append("mid-century hospitality / cocktail culture")

    return ", ".join(themes) if themes else "dive bar culture, working-class Americana"


def build_archival_sources(bar: dict) -> str:
    city  = bar.get("city", "").lower()
    state = bar.get("state", "").lower()
    name_encoded = bar["name"].replace(" ", "+")

    sources = []

    if "seattle" in city or "wa" in state:
        sources.append(
            f"Seattle Municipal Archives: https://digitalcollections.seattle.gov/digital/search/searchterm/{name_encoded}"
        )
        sources.append(
            "Washington State Historical Society: https://www.washingtonhistory.org/research/whc/digital-archives/"
        )
        sources.append(
            "Seattle Times Archive: search via Seattle Public Library card for bar name"
        )

    if "denver" in city or "boulder" in city or "co" in state:
        sources.append(
            f"Denver Public Library Digital Collections: https://digital.denverlibrary.org/digital/search/searchterm/{name_encoded}"
        )
        sources.append(
            "Colorado Historic Newspapers: https://www.coloradohistoricnewspapers.org/"
        )

    sources.append(
        f"Flickr Commons: https://www.flickr.com/search/?q={name_encoded}&l=commderiv"
    )
    sources.append(
        f"Internet Archive: https://archive.org/search?query={name_encoded}"
    )

    return "\n".join(f"  - {s}" for s in sources)


def ensure_table():
    """Create the design_briefs table if it doesn't exist."""
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS design_briefs (
                id TEXT PRIMARY KEY,
                bar_name TEXT NOT NULL,
                city TEXT,
                state TEXT,
                brief_json TEXT NOT NULL,
                archival_sources TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                notes TEXT
            )
        """)


def generate_brief(bar: dict):
    """Call Claude to produce a design brief. Returns (brief_dict, archival_str) or (None, None)."""
    themes   = detect_themes(bar)
    archival = build_archival_sources(bar)

    prompt = BRIEF_PROMPT.format(
        name=bar["name"],
        city=bar.get("city", "Unknown"),
        state=bar.get("state", "Unknown"),
        description=bar.get("description", "No description available."),
        themes=themes,
    )

    logger.info(f"Generating design brief for: {bar['name']}")

    try:
        brief = complete_json(prompt, max_tokens=4000)
        return brief, archival
    except Exception as e:
        logger.error(f"Failed to generate brief for {bar['name']}: {e}")
        return None, None


def save_brief(bar: dict, brief: dict, archival: str):
    """Insert a new design brief row."""
    with get_conn() as conn:
        execute(conn,
            """
            INSERT INTO design_briefs (id, bar_name, city, state, brief_json, archival_sources, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                str(uuid.uuid4()),
                bar["name"],
                bar.get("city"),
                bar.get("state"),
                json.dumps(brief, indent=2),
                archival,
                datetime.utcnow().isoformat(),
            ),
        )
    logger.info(f"Saved brief for {bar['name']}")


def run_for_bar(bar: dict) -> dict | None:
    """Generate and save a brief for a single bar. Returns the brief dict or None."""
    ensure_table()
    brief, archival = generate_brief(bar)
    if brief:
        save_brief(bar, brief, archival)
    return brief


def run_for_all_bars(bars: list = None, delay: float = 2.0):
    """Backfill briefs for all bars, skipping any that already have one."""
    ensure_table()
    bars = bars or BARS

    with get_conn() as conn:
        existing_rows = fetchall(conn, "SELECT bar_name FROM design_briefs")
    done = {row["bar_name"] for row in existing_rows}

    to_process = [b for b in bars if b["name"] not in done]
    logger.info(f"Generating briefs for {len(to_process)} bars (skipping {len(done)} existing)")

    for bar in to_process:
        brief, archival = generate_brief(bar)
        if brief:
            save_brief(bar, brief, archival)
        time.sleep(delay)

    logger.info("Design brief backfill complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_for_all_bars()
