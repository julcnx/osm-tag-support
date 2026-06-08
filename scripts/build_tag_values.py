#!/usr/bin/env python3
"""
One-shot script to (re-)generate registry/tag-values.json.

Combines:
  - WIKI_VALUES: values documented on OSM wiki key pages (manually updated)
  - App value_rules from YAML specs (auto-scanned)

Result: registry/tag-values.json  — the source of truth for generate.py.
Edit that file directly to add notes, change categories, or override sources.

Re-run this script only when refreshing from a new wiki fetch or to pick
up new values added to specs.  It will preserve existing entries and only
append new ones; it never removes entries.
"""

import json
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
REGISTRY = ROOT / "registry"
OUT = REGISTRY / "tag-values.json"

# ── Wiki-sourced values ───────────────────────────────────────────────────────
# Source: OSM wiki key pages, fetched 2026-06-08.
# category: paved | unpaved | sports | unknown
# note: optional explanation (non-standard, alias, regional, etc.)

WIKI_VALUES = {
    "surface": [
        # paved
        {"value": "paved",                          "category": "paved"},
        {"value": "asphalt",                        "category": "paved"},
        {"value": "chipseal",                       "category": "paved"},
        {"value": "concrete",                       "category": "paved"},
        {"value": "concrete:lanes",                 "category": "paved"},
        {"value": "concrete:plates",                "category": "paved"},
        {"value": "paving_stones",                  "category": "paved"},
        {"value": "paving_stones:lanes",            "category": "paved"},
        {"value": "grass_paver",                    "category": "paved"},
        {"value": "sett",                           "category": "paved"},
        {"value": "unhewn_cobblestone",             "category": "paved"},
        {"value": "cobblestone",                    "category": "paved"},
        {"value": "cobblestone:flattened",          "category": "paved"},
        {"value": "bricks",                         "category": "paved"},
        {"value": "metal",                          "category": "paved"},
        {"value": "metal_grid",                     "category": "paved"},
        {"value": "wood",                           "category": "paved"},
        {"value": "stepping_stones",                "category": "paved"},
        {"value": "tiles",                          "category": "paved"},
        {"value": "fibre_reinforced_polymer_grate", "category": "paved"},
        # unpaved
        {"value": "unpaved",                        "category": "unpaved"},
        {"value": "compacted",                      "category": "unpaved"},
        {"value": "fine_gravel",                    "category": "unpaved"},
        {"value": "gravel",                         "category": "unpaved"},
        {"value": "shells",                         "category": "unpaved"},
        {"value": "rock",                           "category": "unpaved"},
        {"value": "pebblestone",                    "category": "unpaved"},
        {"value": "ground",                         "category": "unpaved"},
        {"value": "dirt",                           "category": "unpaved"},
        {"value": "earth",                          "category": "unpaved"},
        {"value": "grass",                          "category": "unpaved"},
        {"value": "mud",                            "category": "unpaved"},
        {"value": "sand",                           "category": "unpaved"},
        {"value": "woodchips",                      "category": "unpaved"},
        {"value": "snow",                           "category": "unpaved"},
        {"value": "ice",                            "category": "unpaved"},
        {"value": "salt",                           "category": "unpaved"},
        # sports / special
        {"value": "clay",                           "category": "sports"},
        {"value": "tartan",                         "category": "sports"},
        {"value": "artificial_turf",                "category": "sports"},
        {"value": "acrylic",                        "category": "sports"},
        {"value": "carpet",                         "category": "sports"},
        {"value": "plastic",                        "category": "sports"},
        {"value": "rubber",                         "category": "sports"},
    ],
    "smoothness": [
        # wiki order: best → worst
        {"value": "excellent"},
        {"value": "good"},
        {"value": "intermediate"},
        {"value": "bad"},
        {"value": "very_bad"},
        {"value": "horrible"},
        {"value": "very_horrible"},
        {"value": "impassable"},
    ],
    "tracktype": [
        {"value": "grade1"},
        {"value": "grade2"},
        {"value": "grade3"},
        {"value": "grade4"},
        {"value": "grade5"},
    ],
    "sac_scale": [
        # wiki order: easiest → hardest; strolling (T0) added 2024
        {"value": "strolling"},
        {"value": "hiking"},
        {"value": "mountain_hiking"},
        {"value": "demanding_mountain_hiking"},
        {"value": "alpine_hiking"},
        {"value": "demanding_alpine_hiking"},
        {"value": "difficult_alpine_hiking"},
    ],
    "mtb:scale": [
        # wiki: 0–6 with optional +/- sub-grades; 0- exists but is rarer
        {"value": "0"},  {"value": "0-"}, {"value": "0+"},
        {"value": "1"},  {"value": "1-"}, {"value": "1+"},
        {"value": "2"},  {"value": "2-"}, {"value": "2+"},
        {"value": "3"},  {"value": "3-"}, {"value": "3+"},
        {"value": "4"},  {"value": "4-"}, {"value": "4+"},
        {"value": "5"},  {"value": "5-"}, {"value": "5+"},
        {"value": "6"},
    ],
}

# Values to skip from app scans — BRouter-internal smoothness variants,
# OSRM typos, overly specific sub-variants not in use elsewhere.
SKIP_VALUES = {
    "smoothness": {"grade1_wet", "grade3_wet", "grade5_wet"},
    # concrete_lanes / paving_stones:30: OSRM/GH internal parsing artifacts
    # laterite: not on OSM wiki; apps that mention it do so as a *documented gap*,
    #           not as a supported value — keep it out of the canonical list
    "surface":    {"concrete_lanes", "paving_stones:30", "laterite"},
}

# Manual annotations for app-only values (added when auto-scan finds them)
APP_VALUE_NOTES = {
    "surface": {
        "boardwalk":   "Treated as wood planks over water; paved equivalent in Valhalla",
        "brick":       "Alias for bricks used in some routing engines",
        "cement":      "Treated as paved concrete equivalent in some routing engines",
        "gravel_dirt": "Composite value used in OSM Carto rendering rules",
        "laterite":    "Documented gap: absent from most renderer unpaved lists; common in tropical/West Africa",
        "rocky":       "Variant of rock used in some routing engines",
        "stone":       "Generic stone surface; treated as cobblestone-equivalent in some engines",
    },
    "smoothness": {
        "very_good":   "Used in OSM data and handled by iD/JOSM/BRouter; not on the main wiki smoothness table",
    },
}

APP_VALUE_CATEGORIES = {
    "surface": {
        "boardwalk": "paved",
        "brick":     "paved",
        "cement":    "paved",
        "gravel_dirt": "unpaved",
        "laterite":  "unpaved",
        "rocky":     "unpaved",
        "stone":     "unpaved",
    },
}


# ── Taginfo counts ───────────────────────────────────────────────────────────

def fetch_taginfo_counts(tag_key):
    """Return dict: value → in_ways count from taginfo.openstreetmap.org.
    Uses all-ways count (not filtered to highway=*) as a proxy."""
    url = (
        f"https://taginfo.openstreetmap.org/api/4/key/values"
        f"?key={tag_key}&filter=ways&sortname=count&sortorder=desc&page=1&rp=500"
    )
    with urllib.request.urlopen(url, timeout=20) as resp:
        data = json.loads(resp.read())
    return {row["value"]: row["count"] for row in data.get("data", [])}


# ── Scan YAML specs ───────────────────────────────────────────────────────────

def scan_specs():
    """Return dict: tag_key → {value → [engine_id, ...]}"""
    found = defaultdict(lambda: defaultdict(list))
    for path in sorted(REGISTRY.rglob("*.yaml")):
        with open(path) as f:
            spec = yaml.safe_load(f)
        engine_id = spec.get("engine_id", path.stem)

        all_entries = list(spec.get("tags", [])) + list(spec.get("tags_default", []))
        for p in spec.get("profiles", []):
            all_entries += p.get("tags", [])

        for entry in all_entries:
            tag_key = entry.get("tag_key")
            if tag_key not in WIKI_VALUES:
                continue
            skip = SKIP_VALUES.get(tag_key, set())
            for rule in entry.get("value_rules", []):
                val = rule.get("tag_value", "")
                if val and val not in skip:
                    if engine_id not in found[tag_key][val]:
                        found[tag_key][val].append(engine_id)
    return found


# ── Build / merge ─────────────────────────────────────────────────────────────

def build(existing=None, taginfo_counts=None, taginfo_fetched_on=None):
    app_values = scan_specs()
    if taginfo_counts is None:
        taginfo_counts = {}

    # Preserve existing meta dates unless we have new ones
    existing_meta = (existing or {}).get("meta", {})
    result = {
        "meta": {
            "description": (
                "Canonical tag value lists for OSM tag support tracking. "
                "Values sourced from OSM wiki key pages and explicit consumer usage. "
                "sources[] lists wiki and/or engine_ids that explicitly handle the value. "
                "taginfo_count is the global in_ways count (all way types, proxy for highway use). "
                "Edit this file to adjust categories, add notes, or remove spurious entries."
            ),
            "wiki_fetched_on":    existing_meta.get("wiki_fetched_on", "2026-06-08"),
            "taginfo_fetched_on": taginfo_fetched_on or existing_meta.get("taginfo_fetched_on", ""),
        }
    }

    for tag_key, wiki_entries in WIKI_VALUES.items():
        wiki_vals = {e["value"] for e in wiki_entries}
        app_vals  = set(app_values.get(tag_key, {}).keys())
        counts    = taginfo_counts.get(tag_key, {})

        # Preserve existing entries if re-running
        existing_map = {}
        if existing and tag_key in existing:
            existing_map = {e["value"]: e for e in existing[tag_key]}

        entries = []

        # 1. Wiki values first (in wiki order)
        for wiki_entry in wiki_entries:
            val = wiki_entry["value"]
            if val in existing_map:
                entry = dict(existing_map[val])
            else:
                entry = {k: v for k, v in wiki_entry.items()}

            sources = ["wiki"] + [e for e in app_values.get(tag_key, {}).get(val, [])]
            entry["sources"] = sources

            if val in counts:
                entry["taginfo_count"] = counts[val]
            elif "taginfo_count" in entry:
                pass  # keep existing count if taginfo not re-fetched

            note = APP_VALUE_NOTES.get(tag_key, {}).get(val)
            if note:
                entry["note"] = note
            elif "note" in entry:
                pass  # keep existing note

            entries.append(entry)

        # 2. App-only values not in wiki (sorted for stability)
        for val in sorted(app_vals - wiki_vals):
            if val in existing_map:
                entry = dict(existing_map[val])
            else:
                entry = {"value": val}
                cat = APP_VALUE_CATEGORIES.get(tag_key, {}).get(val)
                if cat:
                    entry["category"] = cat
                note = APP_VALUE_NOTES.get(tag_key, {}).get(val)
                if note:
                    entry["note"] = note

            entry["sources"] = app_values[tag_key][val]
            if val in counts:
                entry["taginfo_count"] = counts[val]
            elif "taginfo_count" in entry:
                pass
            entries.append(entry)

        result[tag_key] = entries

    return result


def main():
    existing = None
    if OUT.exists():
        with open(OUT) as f:
            existing = json.load(f)
        print(f"Merging into existing {OUT}")
    else:
        print(f"Creating {OUT}")

    print("Fetching taginfo counts…")
    taginfo_counts = {}
    for tag_key in WIKI_VALUES:
        taginfo_counts[tag_key] = fetch_taginfo_counts(tag_key)
        n = len(taginfo_counts[tag_key])
        print(f"  {tag_key}: {n} values from taginfo")
    taginfo_fetched_on = str(date.today())

    data = build(existing, taginfo_counts=taginfo_counts, taginfo_fetched_on=taginfo_fetched_on)
    with open(OUT, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Written: {OUT}")
    for tag_key in WIKI_VALUES:
        n = len(data[tag_key])
        print(f"  {tag_key}: {n} values")


if __name__ == "__main__":
    main()
