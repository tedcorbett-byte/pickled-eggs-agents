"""
Single source of truth for bars, subreddits, and trigger phrases.
All agents import from here.
"""

BARS = [
    {"name": "Frontier Room",                "city": "Seattle",  "state": "WA", "url": "https://pickledeggsco.com/products/frontier-room-seattle"},
    {"name": "Jade Pagoda",                  "city": "Seattle",  "state": "WA", "url": "https://pickledeggsco.com/products/jade-pagoda-seattle"},
    {"name": "Manray",                       "city": "Seattle",  "state": "WA", "url": "https://pickledeggsco.com/products/manray-seattle"},
    {"name": "Purr Cocktail Lounge",         "city": "Seattle",  "state": "WA", "url": "https://pickledeggsco.com/products/purr-seattle"},
    {"name": "R Place",                      "city": "Seattle",  "state": "WA", "url": "https://pickledeggsco.com/products/r-place-seattle"},
    {"name": "Re-Bar",                       "city": "Seattle",  "state": "WA", "url": "https://pickledeggsco.com/products/re-bar-seattle"},
    {"name": "Red Door",                     "city": "Seattle",  "state": "WA", "url": "https://pickledeggsco.com/products/the-red-door-seattle"},
    {"name": "Glacier Lanes",                "city": "Everett",  "state": "WA", "url": "https://pickledeggsco.com/products/glacier-lanes-everett-wa"},
    {"name": "Bonnie Brae Tavern",           "city": "Denver",   "state": "CO", "url": "https://pickledeggsco.com/products/bonnie-brae-denver"},
    {"name": "Rock Island",                  "city": "Denver",   "state": "CO", "url": "https://pickledeggsco.com/products/rock-island-denver"},
    {"name": "Ogden Street South",           "city": "Denver",   "state": "CO", "url": "https://pickledeggsco.com/products/ogden-st-south-denver"},
    {"name": "Rainbow Music Hall",           "city": "Denver",   "state": "CO", "url": "https://pickledeggsco.com/products/rainbow-music-hall-seattle"},
    {"name": "Fabulous Matterhorn Supper Club", "city": "Boulder", "state": "CO", "url": "https://pickledeggsco.com/products/unisex-softstyle-t-shirt"},
]

SUBREDDITS = [
    "SeattleWA", "Seattle", "Denver", "Colorado",
    "gaybars", "divebars", "nostalgia", "Bars",
    "AskSeattle", "AskDenver",
    "LGBTQ", "gay", "LGBTHistory",
    "whatisthisplace",
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

# Preformatted string used in Claude prompts
BARS_SUMMARY = "\n".join(f"- {b['name']} ({b['city']}, {b['state']}): {b['url']}" for b in BARS)


def bar_url_for(bar_name: str) -> str:
    """Return the product URL for a bar name, or the homepage as fallback."""
    for b in BARS:
        if b["name"].lower() == bar_name.lower():
            return b["url"]
    return "https://pickledeggsco.com"
