"""
Single source of truth for bars, subreddits, and trigger phrases.
All agents import from here.
"""

BARS = [
    # Seattle, WA
    {"name": "Frontier Room",                    "city": "Seattle",    "state": "WA", "url": "https://pickledeggsco.com/products/frontier-room-seattle"},
    {"name": "Jade Pagoda",                      "city": "Seattle",    "state": "WA", "url": "https://pickledeggsco.com/products/jade-pagoda-seattle"},
    {"name": "Manray",                           "city": "Seattle",    "state": "WA", "url": "https://pickledeggsco.com/products/manray-seattle"},
    {"name": "Purr Cocktail Lounge",             "city": "Seattle",    "state": "WA", "url": "https://pickledeggsco.com/products/purr-seattle"},
    {"name": "R Place",                          "city": "Seattle",    "state": "WA", "url": "https://pickledeggsco.com/products/r-place-seattle"},
    {"name": "Re-Bar",                           "city": "Seattle",    "state": "WA", "url": "https://pickledeggsco.com/products/re-bar-seattle"},
    {"name": "Red Door",                         "city": "Seattle",    "state": "WA", "url": "https://pickledeggsco.com/products/the-red-door-seattle"},
    # Everett, WA
    {"name": "Glacier Lanes",                    "city": "Everett",    "state": "WA", "url": "https://pickledeggsco.com/products/glacier-lanes-everett-wa"},
    # Denver, CO
    {"name": "Bonnie Brae Tavern",               "city": "Denver",     "state": "CO", "url": "https://pickledeggsco.com/products/bonnie-brae-denver"},
    {"name": "Rock Island",                      "city": "Denver",     "state": "CO", "url": "https://pickledeggsco.com/products/rock-island-denver"},
    {"name": "Ogden Street South",               "city": "Denver",     "state": "CO", "url": "https://pickledeggsco.com/products/ogden-st-south-denver"},
    {"name": "Rainbow Music Hall",               "city": "Denver",     "state": "CO", "url": "https://pickledeggsco.com/products/rainbow-music-hall-seattle"},
    # Boulder, CO
    {"name": "Fabulous Matterhorn Supper Club",  "city": "Boulder",    "state": "CO", "url": "https://pickledeggsco.com/products/unisex-softstyle-t-shirt"},
    # Bloomington, IN
    {"name": "Peanut Barrel",                    "city": "Bloomington","state": "IN", "url": "https://pickledeggsco.com/products/peanut-barrel-bloomington"},
    # Ithaca, NY
    {"name": "Royal Palm Tavern",                "city": "Ithaca",     "state": "NY", "url": "https://pickledeggsco.com/products/royal-palm-tavern-ithaca"},
    # Cambridge, MA
    {"name": "The Tasty",                        "city": "Cambridge",  "state": "MA", "url": "https://pickledeggsco.com/products/the-tasty-cambridge-1"},
    # Lawrence, KS
    {"name": "Cadillac Ranch",                   "city": "Lawrence",   "state": "KS", "url": "https://pickledeggsco.com/products/cadillac-ranch-lawrence"},
    # Rosemead, CA
    {"name": "Bahooka",                          "city": "Rosemead",   "state": "CA", "url": "https://pickledeggsco.com/products/copy-of-bahooka-rosemead-ca"},
    # Arlington, VA
    {"name": "Bardo Rodeo",                      "city": "Arlington",  "state": "VA", "url": "https://pickledeggsco.com/products/bardo-rodeo-arlington"},
    # Hanover, NH
    {"name": "Everything But Anchovies",         "city": "Hanover",    "state": "NH", "url": "https://pickledeggsco.com/products/everything-but-anchovies-hanover"},
    # Cincinnati, OH
    {"name": "Sunlite Pool",                     "city": "Cincinnati", "state": "OH", "url": "https://pickledeggsco.com/products/sunlite-pool-coney-island-ohio"},
]

SUBREDDITS = [
    # Pacific Northwest
    "SeattleWA", "Seattle", "AskSeattle", "SeattleHistory", "washingtonstate", "Everett",
    # Colorado
    "Denver", "Colorado", "AskDenver", "DenverHistory", "Boulder",
    # Indiana (Peanut Barrel)
    "bloomington", "IndianaUniversity",
    # New York (Royal Palm Tavern)
    "ithaca", "Cornell",
    # Massachusetts (The Tasty)
    "cambridge", "boston",
    # Kansas (Cadillac Ranch)
    "lawrence",
    # California (Bahooka)
    "LosAngeles",
    # Ohio (Sunlite Pool)
    "cincinnati",
    # Virginia (Bardo Rodeo)
    "nova", "arlington",
    # New Hampshire (Everything But Anchovies)
    "NewHampshire", "Dartmouth",
    # General bar / nostalgia / LGBTQ
    "gaybars", "divebars", "nostalgia", "Bars", "BarCulture",
    "LGBTQ", "LGBT", "gay", "LGBTHistory",
    "whatisthisplace",
]

TRIGGER_PHRASES = [
    "miss that bar", "miss that place", "remember when", "whatever happened to",
    "does anyone remember", "rip to", "closed down", "used to go to",
    "back in the day", "that place is gone", "they closed", "it closed",
    "looking for a gift", "gift for someone who", "gift idea", "dive bar gift",
    "bar shirt", "bar tshirt", "bar t-shirt", "bar merch",
    "gay bar closed", "lesbian bar closed", "queer bar closed",
    # Seattle
    "Capitol Hill bar", "Pike Pine bar", "Belltown bar", "old seattle",
    # Denver / Boulder
    "Colfax bar", "Denver bar", "Boulder bar", "old denver",
    # Bloomington
    "Bloomington bar", "IU bar",
    # Ithaca
    "Ithaca bar", "Cornell bar",
    # Cambridge
    "Cambridge bar", "Harvard Square bar",
    # Lawrence
    "Lawrence bar", "KU bar",
    # Cincinnati
    "Cincinnati bar",
    # Arlington / DC
    "Arlington bar",
    # General
    "dive bar nostalgia", "neighborhood bar gone", "bar is gone", "used to drink at",
]

# Preformatted string used in Claude prompts
BARS_SUMMARY = "\n".join(f"- {b['name']} ({b['city']}, {b['state']}): {b['url']}" for b in BARS)


def bar_url_for(bar_name: str) -> str:
    """Return the product URL for a bar name, or the homepage as fallback."""
    for b in BARS:
        if b["name"].lower() == bar_name.lower():
            return b["url"]
    return "https://pickledeggsco.com"
