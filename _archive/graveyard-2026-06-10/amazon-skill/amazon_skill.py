#!/usr/bin/env python3
"""
Amazon Skill - Search products, check prices, build carts, manage shopping lists.

Usage:
    python amazon_skill.py search "query" [--limit N] [--sort price-asc|price-desc|reviews|newest]
    python amazon_skill.py product ASIN_OR_URL
    python amazon_skill.py cart-url ASIN1[:QTY] [ASIN2[:QTY] ...]
    python amazon_skill.py list-save NAME ASIN1[:QTY] [ASIN2[:QTY] ...]
    python amazon_skill.py list-load NAME
    python amazon_skill.py list-cart NAME
    python amazon_skill.py list-delete NAME
    python amazon_skill.py lists
    python amazon_skill.py enrich-list NAME
"""

import argparse
import json
import os
import re
import sys
import time
import random
from pathlib import Path
from urllib.parse import quote_plus, urlencode

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Run: pip install requests beautifulsoup4")
    sys.exit(1)

SKILL_DIR = Path(__file__).parent
LISTS_DIR = SKILL_DIR / "lists"
LISTS_DIR.mkdir(exist_ok=True)

# Rotate user agents to reduce blocking
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
]

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


def get_session():
    """Create a requests session with browser-like headers."""
    session = requests.Session()
    session.headers.update(HEADERS)
    session.headers["User-Agent"] = random.choice(USER_AGENTS)
    return session


def extract_asin(text):
    """Extract ASIN from a URL or return as-is if already an ASIN."""
    # ASIN pattern: 10 alphanumeric characters starting with B0 or a digit
    asin_match = re.search(r'/(?:dp|product|gp/product)/([A-Z0-9]{10})', text)
    if asin_match:
        return asin_match.group(1)
    # Check if it's already an ASIN
    if re.match(r'^[A-Z0-9]{10}$', text):
        return text
    return text


def parse_price(price_str):
    """Parse a price string like '$12.99' into a float."""
    if not price_str:
        return None
    match = re.search(r'[\$]?([\d,]+\.?\d*)', price_str.replace(',', ''))
    if match:
        return float(match.group(1))
    return None


def search_amazon(query, limit=10, sort=None):
    """Search Amazon for products."""
    session = get_session()

    params = {"k": query}
    if sort:
        sort_map = {
            "price-asc": "price-asc-rank",
            "price-desc": "price-desc-rank",
            "reviews": "review-rank",
            "newest": "date-desc-rank",
        }
        if sort in sort_map:
            params["s"] = sort_map[sort]

    url = f"https://www.amazon.com/s?{urlencode(params)}"

    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        return {"error": f"Request failed: {e}"}

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    # Find product cards
    items = soup.select('[data-component-type="s-search-result"]')

    for item in items[:limit]:
        try:
            asin = item.get("data-asin", "")
            if not asin:
                continue

            # Title
            title_el = item.select_one("h2 a span") or item.select_one("h2 span")
            title = title_el.get_text(strip=True) if title_el else "Unknown"

            # URL
            link_el = item.select_one("h2 a")
            product_url = ""
            if link_el and link_el.get("href"):
                href = link_el["href"]
                if href.startswith("/"):
                    product_url = f"https://www.amazon.com{href}"
                else:
                    product_url = href

            # Price
            price = None
            price_whole = item.select_one(".a-price-whole")
            price_frac = item.select_one(".a-price-fraction")
            if price_whole:
                whole = price_whole.get_text(strip=True).rstrip(".")
                frac = price_frac.get_text(strip=True) if price_frac else "00"
                price = f"${whole}.{frac}"

            # Rating
            rating = None
            rating_el = item.select_one(".a-icon-alt")
            if rating_el:
                rating_text = rating_el.get_text(strip=True)
                rating_match = re.search(r'([\d.]+) out of', rating_text)
                if rating_match:
                    rating = float(rating_match.group(1))

            # Review count
            reviews = None
            reviews_el = item.select_one('[aria-label*="stars"] + span') or item.select_one('.a-size-base.s-underline-text')
            if reviews_el:
                reviews_text = reviews_el.get_text(strip=True).replace(",", "")
                reviews_match = re.search(r'([\d]+)', reviews_text)
                if reviews_match:
                    reviews = int(reviews_match.group(1))

            # Prime
            is_prime = bool(item.select_one('.a-icon-prime, [aria-label*="Prime"]'))

            # Image
            img_el = item.select_one("img.s-image")
            image = img_el.get("src", "") if img_el else ""

            result = {
                "asin": asin,
                "title": title[:120],
                "price": price,
                "rating": rating,
                "reviews": reviews,
                "prime": is_prime,
                "url": f"https://www.amazon.com/dp/{asin}",
            }
            results.append(result)

        except Exception:
            continue

    return {
        "query": query,
        "count": len(results),
        "results": results,
    }


def get_product(asin_or_url):
    """Get detailed product information."""
    asin = extract_asin(asin_or_url)
    session = get_session()
    url = f"https://www.amazon.com/dp/{asin}"

    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        return {"error": f"Request failed: {e}"}

    soup = BeautifulSoup(resp.text, "html.parser")

    # Title
    title_el = soup.select_one("#productTitle")
    title = title_el.get_text(strip=True) if title_el else "Unknown"

    # Price - try multiple selectors
    price = None
    for selector in [
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        ".a-price .a-offscreen",
        "#corePrice_feature_div .a-offscreen",
        "#tp_price_block_total_price_wc .a-offscreen",
        ".priceToPay .a-offscreen",
    ]:
        price_el = soup.select_one(selector)
        if price_el:
            price = price_el.get_text(strip=True)
            break

    # Rating
    rating = None
    rating_el = soup.select_one("#acrPopover .a-icon-alt, .reviewCountTextLinkedHistogram .a-icon-alt")
    if rating_el:
        rating_match = re.search(r'([\d.]+)', rating_el.get_text(strip=True))
        if rating_match:
            rating = float(rating_match.group(1))

    # Review count
    reviews = None
    reviews_el = soup.select_one("#acrCustomerReviewText")
    if reviews_el:
        reviews_match = re.search(r'([\d,]+)', reviews_el.get_text(strip=True))
        if reviews_match:
            reviews = int(reviews_match.group(1).replace(",", ""))

    # Availability
    avail = None
    avail_el = soup.select_one("#availability span")
    if avail_el:
        avail = avail_el.get_text(strip=True)

    # Brand
    brand = None
    brand_el = soup.select_one("#bylineInfo, .po-brand .a-span9 span")
    if brand_el:
        brand = brand_el.get_text(strip=True).replace("Visit the ", "").replace(" Store", "")

    # Features / bullet points
    features = []
    feature_els = soup.select("#feature-bullets li span.a-list-item")
    for f in feature_els[:8]:
        text = f.get_text(strip=True)
        if text and len(text) > 5:
            features.append(text)

    # Main image
    image = None
    img_el = soup.select_one("#landingImage, #imgBlkFront")
    if img_el:
        image = img_el.get("src", "") or img_el.get("data-old-hires", "")

    # Technical details / specs
    specs = {}
    spec_rows = soup.select("#productDetails_techSpec_section_1 tr, #detailBullets_feature_div li")
    for row in spec_rows[:15]:
        cells = row.select("th, td") or row.select("span.a-text-bold, span:not(.a-text-bold)")
        if len(cells) >= 2:
            key = cells[0].get_text(strip=True).rstrip(" \u200f\u200e:")
            val = cells[1].get_text(strip=True)
            if key and val:
                specs[key] = val

    result = {
        "asin": asin,
        "title": title,
        "price": price,
        "rating": rating,
        "reviews": reviews,
        "availability": avail,
        "brand": brand,
        "features": features,
        "specs": specs,
        "url": f"https://www.amazon.com/dp/{asin}",
    }

    return result


def build_cart_url(items):
    """
    Build an Amazon 'Add to Cart' URL for multiple items.
    items: list of (asin, quantity) tuples
    """
    params = {}
    for i, (asin, qty) in enumerate(items, 1):
        params[f"ASIN.{i}"] = asin
        params[f"Quantity.{i}"] = qty

    url = f"https://www.amazon.com/gp/aws/cart/add.html?{urlencode(params)}"
    return {
        "cart_url": url,
        "items": [{"asin": a, "quantity": q} for a, q in items],
        "item_count": len(items),
        "note": "Open this URL in your browser to add all items to your Amazon cart at once.",
    }


def parse_item_arg(arg):
    """Parse 'ASIN:QTY' or just 'ASIN' into (asin, qty) tuple."""
    parts = arg.split(":")
    asin = extract_asin(parts[0])
    qty = int(parts[1]) if len(parts) > 1 else 1
    return (asin, qty)


# --- Shopping List Management ---

def save_list(name, items, notes=None):
    """Save a shopping list to disk."""
    data = {
        "name": name,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "items": [{"asin": a, "quantity": q} for a, q in items],
    }
    if notes:
        data["notes"] = notes

    filepath = LISTS_DIR / f"{name}.json"
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    return {"saved": str(filepath), "items": len(items)}


def load_list(name):
    """Load a shopping list from disk."""
    filepath = LISTS_DIR / f"{name}.json"
    if not filepath.exists():
        return {"error": f"List '{name}' not found. Use 'lists' to see available lists."}

    with open(filepath) as f:
        data = json.load(f)

    return data


def delete_list(name):
    """Delete a shopping list."""
    filepath = LISTS_DIR / f"{name}.json"
    if not filepath.exists():
        return {"error": f"List '{name}' not found."}
    filepath.unlink()
    return {"deleted": name}


def get_all_lists():
    """List all saved shopping lists."""
    lists = []
    for f in sorted(LISTS_DIR.glob("*.json")):
        with open(f) as fh:
            data = json.load(fh)
            lists.append({
                "name": data.get("name", f.stem),
                "items": len(data.get("items", [])),
                "created": data.get("created", "unknown"),
            })
    return {"lists": lists, "count": len(lists)}


def enrich_list(name):
    """Load a list and fetch current prices/titles for each item."""
    data = load_list(name)
    if "error" in data:
        return data

    enriched_items = []
    for item in data.get("items", []):
        asin = item["asin"]
        qty = item.get("quantity", 1)

        print(f"  Fetching {asin}...", file=sys.stderr)
        product = get_product(asin)

        enriched = {
            "asin": asin,
            "quantity": qty,
            "title": product.get("title", "Unknown"),
            "price": product.get("price"),
            "rating": product.get("rating"),
            "reviews": product.get("reviews"),
            "availability": product.get("availability"),
            "url": f"https://www.amazon.com/dp/{asin}",
        }

        # Calculate line total
        price_val = parse_price(enriched["price"])
        if price_val:
            enriched["line_total"] = f"${price_val * qty:.2f}"

        enriched_items.append(enriched)

        # Be polite - don't hammer Amazon
        time.sleep(random.uniform(1.0, 2.5))

    # Calculate grand total
    grand_total = 0
    for item in enriched_items:
        price_val = parse_price(item.get("price"))
        if price_val:
            grand_total += price_val * item.get("quantity", 1)

    result = {
        "name": data["name"],
        "items": enriched_items,
        "item_count": len(enriched_items),
        "grand_total": f"${grand_total:.2f}" if grand_total > 0 else "unknown",
    }

    # Save enriched version back
    enriched_path = LISTS_DIR / f"{name}.json"
    save_data = {**data, "items": enriched_items, "enriched": time.strftime("%Y-%m-%d %H:%M:%S"), "grand_total": result["grand_total"]}
    with open(enriched_path, "w") as f:
        json.dump(save_data, f, indent=2)

    return result


def list_to_cart(name):
    """Generate a cart URL from a saved list."""
    data = load_list(name)
    if "error" in data:
        return data

    items = [(item["asin"], item.get("quantity", 1)) for item in data.get("items", [])]
    result = build_cart_url(items)
    result["list_name"] = name
    return result


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(description="Amazon Skill")
    subparsers = parser.add_subparsers(dest="command")

    # search
    sp = subparsers.add_parser("search", help="Search Amazon products")
    sp.add_argument("query", help="Search query")
    sp.add_argument("--limit", type=int, default=10, help="Max results")
    sp.add_argument("--sort", choices=["price-asc", "price-desc", "reviews", "newest"])

    # product
    sp = subparsers.add_parser("product", help="Get product details")
    sp.add_argument("asin", help="ASIN or Amazon URL")

    # cart-url
    sp = subparsers.add_parser("cart-url", help="Build Add to Cart URL")
    sp.add_argument("items", nargs="+", help="ASIN[:QTY] pairs")

    # list-save
    sp = subparsers.add_parser("list-save", help="Save a shopping list")
    sp.add_argument("name", help="List name")
    sp.add_argument("items", nargs="+", help="ASIN[:QTY] pairs")
    sp.add_argument("--notes", help="Optional notes")

    # list-load
    sp = subparsers.add_parser("list-load", help="Load a shopping list")
    sp.add_argument("name", help="List name")

    # list-cart
    sp = subparsers.add_parser("list-cart", help="Generate cart URL from list")
    sp.add_argument("name", help="List name")

    # list-delete
    sp = subparsers.add_parser("list-delete", help="Delete a shopping list")
    sp.add_argument("name", help="List name")

    # lists
    subparsers.add_parser("lists", help="Show all saved lists")

    # enrich-list
    sp = subparsers.add_parser("enrich-list", help="Fetch current prices for all items in a list")
    sp.add_argument("name", help="List name")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "search":
        result = search_amazon(args.query, limit=args.limit, sort=args.sort)
    elif args.command == "product":
        result = get_product(args.asin)
    elif args.command == "cart-url":
        items = [parse_item_arg(a) for a in args.items]
        result = build_cart_url(items)
    elif args.command == "list-save":
        items = [parse_item_arg(a) for a in args.items]
        result = save_list(args.name, items, notes=args.notes)
    elif args.command == "list-load":
        result = load_list(args.name)
    elif args.command == "list-cart":
        result = list_to_cart(args.name)
    elif args.command == "list-delete":
        result = delete_list(args.name)
    elif args.command == "lists":
        result = get_all_lists()
    elif args.command == "enrich-list":
        result = enrich_list(args.name)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
