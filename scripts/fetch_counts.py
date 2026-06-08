#!/usr/bin/env python3
"""
Fetch tag usage counts from ohsome API for tracked tag keys.

Saves raw responses to data/{tag}_counts_raw.json.
Reuses cache by default; pass --refresh to force re-fetch.

Usage:
  python3 scripts/fetch_counts.py [--refresh] [--min-count N]
"""

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

OHSOME_URL = "https://api.ohsome.org/v1/elements/count/groupBy/tag"

TAGS = {
    "surface":    "highway=* and surface=* and type:way",
    "smoothness": "highway=* and smoothness=* and type:way",
    "tracktype":  "highway=* and tracktype=* and type:way",
}
DATE = "2025-06-01"


def fetch_ohsome(tag_key, filter_expr):
    print(f"  Fetching ohsome counts for {tag_key}...")
    params = urllib.parse.urlencode({
        "bboxes": "-180,-90,180,90",
        "filter": filter_expr,
        "time": DATE,
        "groupByKey": tag_key,
        "format": "json",
    }).encode()
    req = urllib.request.Request(OHSOME_URL, data=params, method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def load_counts(tag_key, raw):
    counts = {}
    for group in raw.get("groupByResult", []):
        obj = group.get("groupByObject", "")
        if obj in ("remainder", "total"):
            continue
        prefix = f"{tag_key}="
        value = obj.removeprefix(prefix) if obj.startswith(prefix) else obj
        result = group.get("result", [])
        counts[value] = int(result[-1]["value"]) if result else 0
    return counts


def fmt(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M".rstrip("0").rstrip(".")
    if n >= 1_000:
        return f"{n/1_000:.1f}k".rstrip("0").rstrip(".")
    return str(n)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Re-fetch even if cache exists")
    parser.add_argument("--min-count", type=int, default=1000, metavar="N",
                        help="Minimum count to show in report (default: 1000)")
    args = parser.parse_args()

    for tag_key, filter_expr in TAGS.items():
        print(f"\n{'='*50}")
        print(f"Tag: {tag_key}")

        raw_path = DATA / f"{tag_key}_counts_raw.json"

        if args.refresh or not raw_path.exists():
            raw = fetch_ohsome(tag_key, filter_expr)
            raw_path.write_text(json.dumps(raw, indent=2))
            print(f"  Saved {raw_path.name}")
        else:
            raw = json.loads(raw_path.read_text())
            print(f"  Using cached {raw_path.name} (--refresh to re-fetch)")

        counts = load_counts(tag_key, raw)
        rows = sorted(
            [(v, c) for v, c in counts.items() if c >= args.min_count],
            key=lambda x: -x[1],
        )

        print(f"\n  {'count':>10}  value")
        print(f"  {'-'*40}")
        for value, count in rows:
            print(f"  {fmt(count):>10}  {value}")
        print(f"\n  {len(rows)} values with >= {args.min_count} uses")


if __name__ == "__main__":
    main()
