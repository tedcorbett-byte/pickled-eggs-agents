"""
Single source of truth for bars, subreddits, and trigger phrases.
All agents import from here.
"""

BARS = [
    # Seattle, WA
    {"name": "Frontier Room", "city": "Seattle", "state": "WA",
     "url": "https://pickledeggsco.com/products/frontier-room-seattle",
     "description": "A legendary Belltown dive bar in Seattle — one of the strongest in the collection."},
    {"name": "Jade Pagoda", "city": "Seattle", "state": "WA",
     "url": "https://pickledeggsco.com/products/jade-pagoda-seattle",
     "description": "Sat on Broadway in Capitol Hill for decades — a proper dive, dark and unpretentious. A gay bar before Capitol Hill was known for it, a neighborhood bar before the neighborhood got expensive, and a late-night institution until it quietly disappeared."},
    {"name": "Manray", "city": "Seattle", "state": "WA",
     "url": "https://pickledeggsco.com/products/manray-seattle",
     "description": "Capitol Hill's default gay bar and video bar — the gravitational center of the scene, the place you started from or ended up at. The Stranger once called Purr 'the new Manray, meaning that's the default, where you go to regroup if your night's not going as it should.' When it closed, the hole it left was big enough that new bars had to be defined in relation to it."},
    {"name": "Purr Cocktail Lounge", "city": "Seattle", "state": "WA",
     "url": "https://pickledeggsco.com/products/purr-seattle",
     "description": "Opened in 2005 on 11th Avenue on Capitol Hill by Barbie Roberts, a Manray veteran. Out magazine and Out Traveler named it one of the world's 200 greatest gay bars. Ran drag shows, karaoke, election viewing parties, and fundraisers. Pushed out of Capitol Hill by soaring rents in 2017, closed in Montlake in 2018. The space became Queer/Bar."},
    {"name": "R Place", "city": "Seattle", "state": "WA",
     "url": "https://pickledeggsco.com/products/r-place-seattle",
     "description": "Opened in 1984 on Capitol Hill. Three floors, rooftop deck, drag cabaret. A particularly welcoming space for LGBTQ people of color — described as a sanctuary. Ran for nearly four decades. Didn't close because it was failing — it lost its lease after the property owner died and the estate didn't renew it. An attempt to continue as The Comeback in SoDo didn't survive either."},
    {"name": "Re-Bar", "city": "Seattle", "state": "WA",
     "url": "https://pickledeggsco.com/products/re-bar-seattle",
     "description": "Opened January 1990 on Howell Street. A bar, nightclub, and performance space that hosted drag, live music, theater, and dance nights. Hosted Nirvana's Nevermind release party. Launched Dina Martina's career. Home to the Seattle Poetry Slam. Described by patrons as 'a home away from home — the ultimate safe space.' Closed permanently in 2020 due to the pandemic and a property tax hike."},
    {"name": "Red Door", "city": "Seattle", "state": "WA",
     "url": "https://pickledeggsco.com/products/the-red-door-seattle",
     "description": "A neighborhood pub in Fremont — good beer, comfortable room, the right amount of noise, and a crowd that was happy to be exactly where it was. Fit Fremont's character perfectly. When it closed it took a piece of Fremont's particular personality with it."},
    # Everett, WA
    {"name": "Glacier Lanes", "city": "Everett", "state": "WA",
     "url": "https://pickledeggsco.com/products/glacier-lanes-everett-wa",
     "description": "A bowling alley and bar in Everett — cold beer, good lanes, zero pretension. Served Everett for decades as the kind of place that anchors a community without anyone noticing how much until it's gone."},
    # Denver, CO
    {"name": "Bonnie Brae Tavern", "city": "Denver", "state": "CO",
     "url": "https://pickledeggsco.com/products/bonnie-brae-denver",
     "description": "A Denver institution people assumed would outlast them. A neighborhood bar in the truest sense — tucked into a quiet residential pocket of the city, low-key to the point of invisibility if you didn't already know it was there. When it closed, people took it personally."},
    {"name": "Rock Island", "city": "Denver", "state": "CO",
     "url": "https://pickledeggsco.com/products/rock-island-denver",
     "description": "Denver's great late-night equalizer — a dance bar and music venue on Welton Street that didn't care who you were when you walked in, only that you were ready to have a good time. Left a hole in the Denver nightlife map that never quite got filled. Two brothers from Denver are still not over it."},
    {"name": "Ogden Street South", "city": "Denver", "state": "CO",
     "url": "https://pickledeggsco.com/products/ogden-st-south-denver",
     "description": "The bar you ended up at when the night still had somewhere to go. Colfax-adjacent Denver, reliably unpretentious — good drinks, no nonsense, the right kind of dark. Denver has newer bars. Denver doesn't have this one anymore."},
    {"name": "Rainbow Music Hall", "city": "Denver", "state": "CO",
     "url": "https://pickledeggsco.com/products/rainbow-music-hall-seattle",
     "description": "A mid-size Denver music venue that hosted legendary acts through the late 70s and 80s. Punched well above its weight. The acoustics weren't perfect, the sightlines weren't great, and it was absolutely irreplaceable."},
    # Boulder, CO
    {"name": "Fabulous Matterhorn Supper Club", "city": "Boulder", "state": "CO",
     "url": "https://pickledeggsco.com/products/unisex-softstyle-t-shirt",
     "description": "A bar, restaurant, and live music spot in Boulder with a name so good it almost didn't need to be a real place. It was. People ate there, drank there, saw bands there, and had the kind of evenings that get mentioned in conversation for years after. Boulder has changed a lot. The Matterhorn isn't coming back."},
    # Bloomington, IN
    {"name": "Peanut Barrel", "city": "Bloomington", "state": "IN",
     "url": "https://pickledeggsco.com/products/peanut-barrel-bloomington",
     "description": "A beloved Bloomington, Indiana bar — a college town institution near Indiana University that meant something to generations of students and locals."},
    # Ithaca, NY
    {"name": "Royal Palm Tavern", "city": "Ithaca", "state": "NY",
     "url": "https://pickledeggsco.com/products/royal-palm-tavern-ithaca",
     "description": "A beloved Ithaca, New York bar near Cornell University — a community institution that meant something to generations of students and locals."},
    # Cambridge, MA
    {"name": "The Tasty", "city": "Cambridge", "state": "MA",
     "url": "https://pickledeggsco.com/products/the-tasty-cambridge-1",
     "description": "A legendary late-night diner and gathering spot in Harvard Square, Cambridge. A fixture of the Square for decades before closing — the kind of place where students, locals, and night owls all ended up eventually."},
    # Lawrence, KS
    {"name": "Cadillac Ranch", "city": "Lawrence", "state": "KS",
     "url": "https://pickledeggsco.com/products/cadillac-ranch-lawrence",
     "description": "A bar in Lawrence, Kansas — a college town institution near the University of Kansas that served the community for years."},
    # Rosemead, CA
    {"name": "Bahooka", "city": "Rosemead", "state": "CA",
     "url": "https://pickledeggsco.com/products/copy-of-bahooka-rosemead-ca",
     "description": "A legendary tiki bar in Rosemead, California — famous for its elaborate tropical decor, fish tanks, and rum drinks. An institution of Southern California tiki culture that ran for decades before closing."},
    # Arlington, VA
    {"name": "Bardo Rodeo", "city": "Arlington", "state": "VA",
     "url": "https://pickledeggsco.com/products/bahooka-rosemead-ca",
     "description": "A beloved bar in Arlington, Virginia — a community gathering place that served its neighborhood faithfully before closing."},
    # Hanover, NH
    {"name": "Everything But Anchovies", "city": "Hanover", "state": "NH",
     "url": "https://pickledeggsco.com/products/everything-but-anchovies-hanover",
     "description": "A legendary late-night pizza and bar spot in Hanover, New Hampshire — a Dartmouth College institution that served generations of students and locals before closing."},
    # Cincinnati, OH
    {"name": "Sunlite Pool", "city": "Cincinnati", "state": "OH",
     "url": "https://pickledeggsco.com/products/sunlite-pool-coney-island-ohio",
     "description": "The iconic pool at Coney Island amusement park in Cincinnati, Ohio — one of the largest recirculating pools in the world. A summertime institution for generations of Cincinnati families before closing."},
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
    # Tiki (Bahooka)
    "Tiki", "TikiBar",
    # Dartmouth (Everything But Anchovies)
    "Dartmouth",
    # Harvard Square (The Tasty)
    "Harvard",
    # General bar / nostalgia / LGBTQ
    "gaybars", "divebars", "nostalgia", "Bars", "BarCulture",
    "LGBTQ", "LGBT", "gay", "LGBTHistory",
    "whatisthisplace", "mildlynostalgia", "AskNYC", "BeerCulture",
]

TRIGGER_PHRASES = [
    "miss that bar", "miss that place", "remember when", "whatever happened to",
    "does anyone remember", "rip to", "closed down", "used to go to",
    "back in the day", "that place is gone", "they closed", "it closed",
    "looking for a gift", "gift for someone who", "gift idea", "dive bar gift",
    "bar shirt", "bar tshirt", "bar t-shirt", "bar merch",
    "gay bar closed", "lesbian bar closed", "queer bar closed",
    "queer space closed", "lost gay bar", "gay bar nostalgia", "pride bar",
    "LGBTQ bar", "queer bar gone",
    # Reunions
    "college reunion", "alumni reunion", "homecoming", "class reunion",
    "bar from college", "reunion weekend", "alumni weekend",
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
BARS_SUMMARY = "\n".join(
    f"- {b['name']} ({b['city']}, {b['state']}): {b['url']}\n  {b['description']}"
    for b in BARS
)


CANDIDATES = [
    # Pre-seeded bar candidates worth researching as future products.
    # Shape mirrors BARS, plus status, grief_score, and notes.
    # The bar_scout agent discovers NEW candidates automatically and writes them
    # to the bar_candidates DB table. To add a manual seed here, follow this shape:
    #
    # {
    #     "name": "The Comet Tavern",
    #     "city": "Seattle",
    #     "state": "WA",
    #     "description": "A Capitol Hill dive bar that outlasted a dozen neighborhood changes.",
    #     "status": "discovered",
    #     "grief_score": 8,
    #     "notes": "Multiple Reddit threads. Long history on Pike St.",
    # },

    # ── Portland, OR ──────────────────────────────────────────────────────────
    {
        "name": "Embers Avenue",
        "city": "Portland",
        "state": "OR",
        "description": "Portland's longest-running gay bar and nightclub, open from 1975 to 2019 — 44 years on NW Broadway. Closed due to development pressure. A multigenerational anchor of Portland LGBTQ life.",
        "status": "discovered",
        "grief_score": 82,
        "notes": "Zero competitor coverage. 44-year run. Geographically adjacent to Seattle market. Strong multigenerational alumni community.",
    },
    {
        "name": "The Egyptian Club",
        "city": "Portland",
        "state": "OR",
        "description": "Portland's last self-described lesbian bar, closed in 2010. No lesbian bar has replaced it in Portland since. Strong ongoing grief signal among Portland queer women's community.",
        "status": "discovered",
        "grief_score": 74,
        "notes": "No competitor memorial shirt exists. Unique as Portland's final lesbian bar. Community grief well-documented online.",
    },

    # ── Chicago, IL ───────────────────────────────────────────────────────────
    {
        "name": "Little Jim's Tavern",
        "city": "Chicago",
        "state": "IL",
        "description": "The first gay bar in Boystown and second-oldest gay bar in Chicago, open from 1975 to 2020 — 45 years. Known as the gay Cheers for its deeply inclusive, across-race-and-identity regulars. Closed when the property sold to Howard Brown Health for a clinic. Massive alumni community dispersed nationwide.",
        "status": "discovered",
        "grief_score": 88,
        "notes": "No competitor memorial shirt exists. Chicago is a massive untapped market. 45-year run. Boystown institution with national alumni footprint.",
    },

    # ── Washington, DC ────────────────────────────────────────────────────────
    {
        "name": "Phase 1",
        "city": "Washington",
        "state": "DC",
        "description": "The longest-running lesbian bar in America at the time of its closure in 2016. A community cornerstone for decades in DC. Closure mourned nationally with strong ongoing online grief signal.",
        "status": "discovered",
        "grief_score": 85,
        "notes": "No competitor memorial shirt exists. National significance — longest-running lesbian bar in the US. Strong grief signal continues years after closure.",
    },
    {
        "name": "Ziegfeld's / Secrets",
        "city": "Washington",
        "state": "DC",
        "description": "A long-running DC drag institution and gay bar, closed in 2020. Known for performances and a welcoming, diverse queer clientele. A significant loss to the DC LGBTQ scene.",
        "status": "discovered",
        "grief_score": 71,
        "notes": "No competitor memorial shirt exists. DC drag history angle. Closed during pandemic — recency adds grief intensity.",
    },

    # ── West Hollywood, CA ────────────────────────────────────────────────────
    {
        "name": "Gold Coast Bar",
        "city": "West Hollywood",
        "state": "CA",
        "description": "Known as the last true dive bar in West Hollywood — 40 years of cheap drinks, longtime regulars, and zero pretension in a neighborhood that lost most of its dive bars long ago. The fourth WeHo gay bar to close during the pandemic in 2020.",
        "status": "discovered",
        "grief_score": 78,
        "notes": "No competitor memorial shirt exists. Proves the LA market. Dive bar identity within gay bar world is a strong angle. 40-year run.",
    },

    # ── Ann Arbor, MI ─────────────────────────────────────────────────────────
    {
        "name": "aut Bar",
        "city": "Ann Arbor",
        "state": "MI",
        "description": "Ann Arbor's LGBTQ bar for 25 years, founded by Keith Orr and Martin Contreras. Closed in July 2020 due to COVID financial difficulties. The University of Michigan alumni community is large and geographically dispersed — a strong gift-purchase signal across decades of graduates.",
        "status": "discovered",
        "grief_score": 76,
        "notes": "No competitor memorial shirt exists. College town + LGBTQ angle. U of M alumni base is nationwide. High gift occasion relevance for reunions.",
    },
]


def bar_url_for(bar_name: str) -> str:
    """Return the product URL for a bar name, or the homepage as fallback."""
    for b in BARS:
        if b["name"].lower() == bar_name.lower():
            return b["url"]
    return "https://pickledeggsco.com"
