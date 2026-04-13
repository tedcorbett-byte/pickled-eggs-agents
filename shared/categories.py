"""
Pickled Eggs Co — Non-bar grief categories.
Single source of truth for Music Venues, Restaurants, and Rinks/Bowling.

Agents import from here when scanning for non-bar candidates.
Do not modify shared/bars.py for these — it stays bar-only.
"""
from shared.bars import SUBREDDITS as _BAR_SUBREDDITS

CATEGORIES = {
    "venue": {
        "label": "Music Venue",
        "candidates": [],
        "trigger_phrases": [
            "miss that venue",
            "closed music venue",
            "remember playing there",
            "saw my first show there",
            "rip [venue name]",
            "where bands used to play",
            "best small venue",
            "they tore it down",
            "last show ever",
            "venue closed",
            "indie venue gone",
            "all ages venue",
            "wish this venue was still open",
            "saw [band] there once",
            "concert venue memories",
        ],
        "subreddits": list(dict.fromkeys(
            _BAR_SUBREDDITS + [
                "indieheads", "emo", "punk", "hiphopheads", "metal", "concertgoers",
            ]
        )),
        "disqualifiers": [
            "arena", "amphitheater", "stadium", "ticketmaster",
            "Live Nation", "chain", "franchise", "still open", "currently open",
        ],
    },

    "restaurant": {
        "label": "Restaurant",
        "candidates": [],
        "trigger_phrases": [
            "miss this restaurant",
            "closed restaurant",
            "used to eat there",
            "childhood restaurant",
            "they finally closed",
            "rip [restaurant name]",
            "been going since I was a kid",
            "family restaurant closed",
            "diner closed",
            "local spot gone",
            "neighborhood restaurant",
            "best [food] in the city",
            "wish it was still open",
            "our family tradition",
            "where we always went for",
            "can't believe it closed",
            "institution closed",
        ],
        "subreddits": list(dict.fromkeys(
            _BAR_SUBREDDITS + [
                "food", "KitchenConfidential", "AskCulinary",
                "chicago", "Austin", "FoodNYC", "portland",
            ]
        )),
        "disqualifiers": [
            "chain", "franchise", "fast food", "still open",
            "currently open", "Yelp", "corporate",
            "Applebee's", "Denny's", "IHOP",
        ],
    },

    "rink": {
        "label": "Roller Rink / Bowling",
        "candidates": [],
        "trigger_phrases": [
            "miss the skating rink",
            "roller rink closed",
            "bowling alley closed",
            "used to skate there",
            "remember this rink",
            "childhood bowling alley",
            "rip [rink name]",
            "best roller rink",
            "they tore down the bowling alley",
            "skating rink memories",
            "birthday parties there",
            "wish the rink was still open",
            "laser tag closed",
            "arcades we miss",
            "old school rink",
        ],
        "subreddits": list(dict.fromkeys(
            _BAR_SUBREDDITS + ["rollerderby", "Bowling"]
        )),
        "disqualifiers": [
            "still open", "currently open",
            "Dave and Busters", "chain", "franchise", "Main Event",
        ],
    },
}

CATEGORY_LABELS = {
    "bar":        "Dive Bar",
    "venue":      "Music Venue",
    "restaurant": "Restaurant",
    "rink":       "Roller Rink / Bowling",
}
