"""
Shopify Admin API wrapper.
Used by: content_freshness agent.

Requires env vars:
  SHOPIFY_SHOP_DOMAIN  — e.g. pickledeggsco.myshopify.com
  SHOPIFY_ACCESS_TOKEN — Admin API access token from Shopify Partners
"""
import requests

from shared.config import SHOPIFY_SHOP_DOMAIN, SHOPIFY_ACCESS_TOKEN

_BASE = f"https://{SHOPIFY_SHOP_DOMAIN}/admin/api/2024-01"
_HEADERS = {
    "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    "Content-Type": "application/json",
}


def get_products(limit: int = 250) -> list[dict]:
    """Return all products from the Shopify store."""
    url = f"{_BASE}/products.json?limit={limit}"
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json().get("products", [])


def get_product(product_id: str) -> dict:
    """Return a single product by ID."""
    url = f"{_BASE}/products/{product_id}.json"
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json().get("product", {})


def update_product_description(product_id: str, new_body_html: str) -> dict:
    """Push a new description (body_html) to a Shopify product."""
    url = f"{_BASE}/products/{product_id}.json"
    payload = {"product": {"id": product_id, "body_html": new_body_html}}
    resp = requests.put(url, json=payload, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json().get("product", {})
