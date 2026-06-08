#!/usr/bin/env python3
"""
Fetch OSM wiki status for tag values that appear in ohsome count files.

For each value in data/{tag}_counts_raw.json with >= min-count uses,
fetches Tag:key=value wiki page (action=raw) and extracts:
  - status (de facto, in use, deprecated, obsolete, etc.)
  - deprecated flag + replacement if applicable
  - whether the wiki page exists at all

Saves to data/wiki_status.json:
  {tag_key: {value: {status, deprecated, replacement, wiki_exists}}}

Reuses cache by default; pass --refresh to re-fetch all pages.

Usage:
  python3 scripts/fetch_deprecated.py [--refresh] [--min-count N]
"""

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
REGISTRY = ROOT / "registry"

WIKI_RAW = "https://wiki.openstreetmap.org/w/index.php"
WIKI_HEADERS = {"User-Agent": "osm-tag-support-tracker/1.0"}

TAGS = ["surface", "smoothness", "tracktype"]


def load_registry_values(tag_key):
    path = REGISTRY / "tag-values.json"
    if not path.exists():
        return []
    tv = json.loads(path.read_text())
    return [v["value"] for v in tv.get(tag_key, [])]


def load_ohsome_values(tag_key, min_count):
    path = DATA / f"{tag_key}_counts_raw.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    values = []
    for group in raw.get("groupByResult", []):
        obj = group.get("groupByObject", "")
        if obj in ("remainder", "total"):
            continue
        prefix = f"{tag_key}="
        value = obj.removeprefix(prefix) if obj.startswith(prefix) else obj
        result = group.get("result", [])
        count = int(result[-1]["value"]) if result else 0
        if count >= min_count:
            values.append(value)
    return values


def fetch_wiki_raw(tag_key, value):
    title = f"Tag:{tag_key}={value}"
    url = f"{WIKI_RAW}?title={urllib.parse.quote(title)}&action=raw"
    req = urllib.request.Request(url, headers=WIKI_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status == 404:
                return None
            return r.read().decode("utf-8")
    except urllib.request.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except Exception:
        return None


def parse_wiki_status(wikitext, tag_key, value):
    """
    Return dict with: status, deprecated, replacement.
    status: the raw wiki status string (e.g. 'de facto', 'in use', 'deprecated')
    deprecated: True if value is formally deprecated
    replacement: suggested replacement value (same key), if any
    """
    if wikitext is None:
        return {"status": None, "deprecated": False, "replacement": None}

    # Extract |status= from ValueDescription infobox
    sm = re.search(r"\|\s*status\s*=\s*([^\n|{}]+)", wikitext, re.IGNORECASE)
    status = sm.group(1).strip() if sm else None

    # Check for standalone {{deprecated ...}} template
    has_deprecated_tpl = bool(re.search(r"\{\{\s*deprecated", wikitext, re.IGNORECASE))

    deprecated = (
        (status is not None and status.lower() in ("deprecated", "obsolete"))
        or has_deprecated_tpl
    )

    replacement = None
    if deprecated:
        for m in re.finditer(r"\|\s*(?:combination|instead|use|newtext)\s*=([^\n]*)", wikitext, re.IGNORECASE):
            block = m.group(1)
            tm = re.search(
                r"\{\{(?:Tag|Key/Value)\s*\|\s*" + re.escape(tag_key) + r"\s*\|\s*([^|}]+)",
                block, re.IGNORECASE,
            )
            if tm:
                replacement = tm.group(1).strip()
                break
            lm = re.search(
                r"\[\[Tag:" + re.escape(tag_key) + r"=([^\]|]+)",
                block, re.IGNORECASE,
            )
            if lm:
                replacement = lm.group(1).strip()
                break
        if not replacement:
            nv = re.search(r"\|\s*newvalue\s*=\s*([^\n|}]+)", wikitext, re.IGNORECASE)
            if nv:
                replacement = nv.group(1).strip()

    return {"status": status, "deprecated": deprecated, "replacement": replacement}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Re-fetch all wiki pages")
    parser.add_argument("--min-count", type=int, default=1000, metavar="N",
                        help="Minimum ohsome count to include (default: 1000)")
    args = parser.parse_args()

    out_path = DATA / "wiki_status.json"
    existing = json.loads(out_path.read_text()) if out_path.exists() else {}

    for tag_key in TAGS:
        print(f"\n{'='*55}")
        print(f"Tag: {tag_key}")

        ohsome_values = load_ohsome_values(tag_key, args.min_count)
        registry_values = load_registry_values(tag_key)
        # union: ohsome top values first, then any registry-only values appended
        seen = set(ohsome_values)
        extra = [v for v in registry_values if v not in seen]
        values = ohsome_values + extra
        if not values:
            print(f"  No values found (run fetch_counts.py first and/or check registry)")
            continue
        if extra:
            print(f"  {len(ohsome_values)} ohsome values + {len(extra)} registry-only values")

        cached = existing.get(tag_key, {})
        tag_result = {}

        to_fetch = values if args.refresh else [v for v in values if v not in cached]
        if to_fetch:
            print(f"  Fetching {len(to_fetch)} wiki pages ({len(values) - len(to_fetch)} cached)...")
        else:
            print(f"  All {len(values)} values cached (--refresh to re-fetch)")

        for i, value in enumerate(to_fetch):
            wikitext = fetch_wiki_raw(tag_key, value)
            info = parse_wiki_status(wikitext, tag_key, value)
            info["wiki_exists"] = wikitext is not None
            cached[value] = info
            time.sleep(0.2)
            if i > 0 and i % 10 == 0:
                print(f"    {i}/{len(to_fetch)} fetched...")

        for value in values:
            tag_result[value] = cached[value]

        existing[tag_key] = {**cached}
        out_path.write_text(json.dumps(existing, indent=2))

        # Print report
        print(f"\n  {'value':<35}  {'status':<20}  note")
        print(f"  {'-'*70}")
        for value in values:
            info = tag_result[value]
            status = info.get("status") or ("(no page)" if not info.get("wiki_exists") else "(no status)")
            note = ""
            if info.get("deprecated"):
                note = f"DEPRECATED → {info['replacement']}" if info.get("replacement") else "DEPRECATED"
            print(f"  {value:<35}  {status:<20}  {note}")

    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
