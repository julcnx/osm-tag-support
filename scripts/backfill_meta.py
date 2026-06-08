#!/usr/bin/env python3
"""
Backfill source_ref into evidence entries and checked_on into related_issues entries.

source_ref is inserted after the last `confidence:` line in each evidence block,
only for files that reference a locally cloned source repo.

checked_on is inserted after each `note:` line in related_issues blocks,
using the file's top-level verified_on date as the baseline.
"""

import re
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "examples"

# Commit hashes at the time evidence was verified (from git rev-parse HEAD)
SOURCE_REFS = {
    "osmand.yaml":         "465a14dbe27932b86355ee44904551ab59310d88",
    "osmand-display.yaml": "465a14dbe27932b86355ee44904551ab59310d88",
    "brouter.yaml":        "a2e2f16f4bb3318a8b017fd76d08fbf67d895849",
    "graphhopper.yaml":    "c8bfa90531748c53d4d2054dad1d3c04f69ce7b6",
    "osrm.yaml":           "3f31696808909070ed081d51d7f01bfa56240da7",
    "pgrouting.yaml":      "be1200ad9d9e2bfdd74e67500cd6a3d729861cad",
    "valhalla.yaml":       "14e2c93a88353789eb0c9f036e5f8a11a5f1b39e",
}

# Files with related_issues that need checked_on backfilled.
# Value: the checked_on date to use (same as verified_on for that file).
CHECKED_ON = {
    "mapcomplete.yaml":  "2026-06-08",
    "streetcomplete.yaml": "2026-06-08",
    "organic-maps.yaml": "2026-06-08",
}


def add_source_ref(text: str, commit: str) -> str:
    """
    Insert `source_ref: <commit>` after every `confidence:` line that does not
    already have a source_ref on the next non-empty line.
    """
    lines = text.splitlines(keepends=True)
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        # Match a confidence: line (any indentation)
        m = re.match(r'^( +)confidence: ', line)
        if m:
            indent = m.group(1)
            # Check if the next non-empty line is already a source_ref
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines) and "source_ref:" in lines[j]:
                pass  # already present, skip
            else:
                out.append(f"{indent}source_ref: {commit}\n")
        i += 1
    return "".join(out)


def add_checked_on(text: str, date: str) -> str:
    """
    Insert `checked_on: <date>` after every `note:` line in a related_issues
    block that does not already have checked_on on the next non-empty line.
    Only single-line note values are handled (multi-line notes would need more
    complex logic, but none of the current files use block scalars here).
    """
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


def process_file(path: Path, commit: str | None, checked_on_date: str | None) -> bool:
    original = path.read_text()
    result = original
    if commit:
        result = add_source_ref(result, commit)
    if checked_on_date:
        result = add_checked_on(result, checked_on_date)
    if result != original:
        path.write_text(result)
        return True
    return False


def main():
    for fname, commit in SOURCE_REFS.items():
        path = DATA_DIR / fname
        if not path.exists():
            print(f"MISSING: {fname}", file=sys.stderr)
            continue
        changed = process_file(path, commit, CHECKED_ON.get(fname))
        status = "updated" if changed else "unchanged"
        print(f"{fname}: {status} (source_ref)")

    for fname, date in CHECKED_ON.items():
        if fname in SOURCE_REFS:
            continue  # already handled above
        path = DATA_DIR / fname
        if not path.exists():
            print(f"MISSING: {fname}", file=sys.stderr)
            continue
        changed = process_file(path, None, date)
        status = "updated" if changed else "unchanged"
        print(f"{fname}: {status} (checked_on)")


if __name__ == "__main__":
    main()
