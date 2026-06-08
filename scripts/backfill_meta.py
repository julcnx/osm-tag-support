#!/usr/bin/env python3
"""
Backfill source_ref into evidence entries and checked_on into related_issues entries.

Files are located by name under registry/ (recursively), so subdirectory moves
don't require updating this script — only filename changes do.
"""

import re
import sys
from pathlib import Path

REGISTRY = Path(__file__).parent.parent / "registry"


def find(fname):
    """Locate a yaml file anywhere under REGISTRY by filename."""
    matches = list(REGISTRY.rglob(fname))
    if not matches:
        print(f"MISSING: {fname}", file=sys.stderr)
        return None
    return matches[0]


# Commit hashes at the time evidence was verified (from git rev-parse HEAD)
SOURCE_REFS = {
    "osmand.yaml":       "465a14dbe27932b86355ee44904551ab59310d88",  # routing/osmand.yaml
    # display/osmand.yaml shares the same source repo
    "brouter.yaml":      "a2e2f16f4bb3318a8b017fd76d08fbf67d895849",
    "graphhopper.yaml":  "c8bfa90531748c53d4d2054dad1d3c04f69ce7b6",
    "osrm.yaml":         "3f31696808909070ed081d51d7f01bfa56240da7",
    "valhalla.yaml":     "14e2c93a88353789eb0c9f036e5f8a11a5f1b39e",
}

CHECKED_ON = {
    "mapcomplete.yaml":   "2026-06-08",
    "streetcomplete.yaml": "2026-06-08",
    "organic-maps.yaml":  "2026-06-08",
    "brouter.yaml":       "2026-06-07",
    "graphhopper.yaml":   "2026-06-07",
    "osrm.yaml":          "2026-06-07",
    "valhalla.yaml":      "2026-06-07",
    "osmand.yaml":        "2026-06-07",
}

# display/osmand.yaml has the same source_ref as routing/osmand.yaml
DISPLAY_OSMAND_REF = "465a14dbe27932b86355ee44904551ab59310d88"


def add_source_ref(text: str, commit: str) -> str:
    lines = text.splitlines(keepends=True)
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = re.match(r'^( +)confidence: ', line)
        if m:
            indent = m.group(1)
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines) and "source_ref:" in lines[j]:
                pass
            else:
                out.append(f"{indent}source_ref: {commit}\n")
        i += 1
    return "".join(out)


def add_checked_on(text: str, date: str) -> str:
    lines = text.splitlines(keepends=True)
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = re.match(r'^( +)note: ', line)
        if m:
            indent = m.group(1)
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines) and "checked_on:" in lines[j]:
                pass
            else:
                out.append(f"{indent}checked_on: {date}\n")
        i += 1
    return "".join(out)


def process(fname, commit, date):
    path = find(fname)
    if not path:
        return
    original = path.read_text()
    result = original
    if commit:
        result = add_source_ref(result, commit)
    if date:
        result = add_checked_on(result, date)
    if result != original:
        path.write_text(result)
        print(f"{path.relative_to(REGISTRY.parent)}: updated")
    else:
        print(f"{path.relative_to(REGISTRY.parent)}: unchanged")


def main():
    all_names = set(SOURCE_REFS) | set(CHECKED_ON)
    for fname in sorted(all_names):
        process(fname, SOURCE_REFS.get(fname), CHECKED_ON.get(fname))

    # display/osmand.yaml shares the OsmAnd-resources source ref
    path = REGISTRY / "display" / "osmand.yaml"
    if path.exists():
        original = path.read_text()
        result = add_source_ref(original, DISPLAY_OSMAND_REF)
        if result != original:
            path.write_text(result)
            print(f"registry/display/osmand.yaml: updated (source_ref)")


if __name__ == "__main__":
    main()
