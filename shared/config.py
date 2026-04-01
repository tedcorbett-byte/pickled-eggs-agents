"""
Central configuration — reads all env vars from .env (or Railway env).
Import from here rather than calling os.getenv() scattered across the codebase.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Reddit
REDDIT_CLIENT_ID     = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT    = os.getenv("REDDIT_USER_AGENT", "PickledEggsCo/1.0")

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# Shopify
SHOPIFY_SHOP_DOMAIN  = os.getenv("SHOPIFY_SHOP_DOMAIN", "")   # e.g. pickledeggsco.myshopify.com
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN", "")

# Database — Postgres URL on Railway; leave blank to use local SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "")

# App
FLASK_PORT           = int(os.getenv("FLASK_PORT", "5050"))
MIN_RELEVANCE_SCORE  = int(os.getenv("MIN_RELEVANCE_SCORE", "6"))
