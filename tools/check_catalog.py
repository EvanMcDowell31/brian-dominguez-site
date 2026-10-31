#!/usr/bin/env python3
"""Compare Audible's catalogue with data/titles.json.

Lists audiobooks Audible credits to the narrator that the site doesn't show yet,
and site titles Audible no longer lists. Exits 1 when the two differ.

    python3 tools/check_catalog.py
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    site = json.loads((ROOT / "data" / "site.json").read_text())
    ours = {t["asin"]: t["title"] for t in json.loads((ROOT / "data" / "titles.json").read_text())}
    query = urllib.parse.urlencode({
        "narrator": site["name"],
        "num_results": 50,
        "products_sort_by": "-ReleaseDate",
        "response_groups": "product_desc,product_attrs,contributors",
    })
    with urllib.request.urlopen("https://api.audible.com/1.0/catalog/products?" + query, timeout=30) as reply:
        products = json.load(reply).get("products", [])
    theirs = {p["asin"]: p for p in products
              if any(n.get("name") == site["name"] for n in p.get("narrators", []))}

    new = [p for asin, p in theirs.items() if asin not in ours]
    gone = [(asin, title) for asin, title in ours.items() if asin not in theirs]
    for p in new:
        print(f"new on Audible: {p['asin']}  {p.get('release_date')}  {p.get('title')}"
              f"  by {', '.join(a['name'] for a in p.get('authors', []))}")
    for asin, title in gone:
        print(f"no longer on Audible: {asin}  {title}")
    if not new and not gone:
        print(f"up to date: {len(ours)} titles")
    sys.exit(1 if new or gone else 0)


if __name__ == "__main__":
    main()
