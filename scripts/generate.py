#!/usr/bin/env python3
"""
Generate site/index.html — a caniuse-style grid of OSM tag support.

Rows: canonical tag values (surface=*, smoothness=*, tracktype=*, mtb:scale=*, sac_scale=*)
Cols: apps grouped by capability type (Routing | Editors | Renderers | Display)

Run: python3 scripts/generate.py
Output: site/index.html (self-contained, no server needed)
"""

import json
import re
from pathlib import Path
import yaml

ROOT = Path(__file__).parent.parent
REGISTRY = ROOT / "registry"
SITE = ROOT / "site"
SITE.mkdir(exist_ok=True)

# ── Canonical tag values (master list, OSM wiki order) ───────────────────────

# Source: https://wiki.openstreetmap.org/wiki/Key:surface (fetched 2026-06-08)
# Source: https://wiki.openstreetmap.org/wiki/Key:smoothness (fetched 2026-06-08)
# Source: https://wiki.openstreetmap.org/wiki/Key:mtb:scale (fetched 2026-06-08)
# Source: https://wiki.openstreetmap.org/wiki/Key:sac_scale (fetched 2026-06-08)
TAGS = {
    "surface": [
        # paved
        "paved", "asphalt", "chipseal", "concrete", "concrete:lanes",
        "concrete:plates", "paving_stones", "paving_stones:lanes",
        "grass_paver", "sett", "unhewn_cobblestone", "cobblestone",
        "cobblestone:flattened", "bricks", "metal", "metal_grid", "wood",
        "stepping_stones", "tiles", "fibre_reinforced_polymer_grate",
        # unpaved
        "unpaved", "compacted", "fine_gravel", "gravel", "shells", "rock",
        "pebblestone", "ground", "dirt", "earth", "grass", "mud", "sand",
        "woodchips", "snow", "ice", "salt",
        # sports / special
        "clay", "tartan", "artificial_turf", "acrylic", "carpet", "plastic",
        "rubber",
        # not in wiki but explicitly tracked as a gap in this project
        "laterite",
    ],
    "smoothness": [
        "excellent", "good", "intermediate", "bad", "very_bad",
        "horrible", "very_horrible", "impassable",
    ],
    "tracktype": ["grade1", "grade2", "grade3", "grade4", "grade5"],
    "mtb:scale": [
        "0", "0-", "0+",
        "1", "1-", "1+",
        "2", "2-", "2+",
        "3", "3-", "3+",
        "4", "4-", "4+",
        "5", "5-", "5+",
        "6",
    ],
    "sac_scale": [
        "strolling", "hiking", "mountain_hiking", "demanding_mountain_hiking",
        "alpine_hiking", "demanding_alpine_hiking", "difficult_alpine_hiking",
    ],
}

# ── App column definitions ────────────────────────────────────────────────────

CAPABILITY_GROUPS = [
    ("Routing",   ["routing/osrm", "routing/brouter", "routing/graphhopper",
                   "routing/valhalla", "routing/osmand", "routing/organic-maps"]),
    ("Editors",   ["editors/josm", "editors/id", "editors/vespucci",
                   "editors/mapcomplete", "editors/streetcomplete"]),
    ("Renderers", ["renderers/openstreetmap-carto", "renderers/americana",
                   "renderers/shortbread"]),
    ("Display",   ["display/osmand", "display/organic-maps"]),
]

DISPLAY_NAMES = {
    "routing/osrm":                     "OSRM",
    "routing/brouter":                  "BRouter",
    "routing/graphhopper":              "GraphHopper",
    "routing/valhalla":                 "Valhalla",
    "routing/osmand":                   "OsmAnd",
    "routing/organic-maps":             "Organic Maps",
    "editors/josm":                     "JOSM",
    "editors/id":                       "iD",
    "editors/vespucci":                 "Vespucci",
    "editors/mapcomplete":              "MapComplete",
    "editors/streetcomplete":           "StreetComplete",
    "renderers/openstreetmap-carto":    "OSM Carto",
    "renderers/americana":              "Americana",
    "renderers/shortbread":             "Shortbread",
    "display/osmand":                   "OsmAnd",
    "display/organic-maps":             "Organic Maps",
}

# ── Load registry ─────────────────────────────────────────────────────────────

def load_specs():
    specs = {}
    for path in REGISTRY.rglob("*.yaml"):
        key = path.relative_to(REGISTRY).with_suffix("").as_posix()
        with open(path) as f:
            specs[key] = yaml.safe_load(f)
    return specs


def get_tag_entries(spec, tag_key):
    """Return list of tag_entry dicts for tag_key from a spec (handles both shapes)."""
    entries = []
    shape = "router_with_profiles" if "profiles" in spec else "single_profile_record"
    if shape == "single_profile_record":
        for t in spec.get("tags", []):
            if t.get("tag_key") == tag_key:
                entries.append(t)
    else:
        for profile in spec.get("profiles", []):
            for t in profile.get("tags", []):
                if t.get("tag_key") == tag_key:
                    entries.append(t)
        for t in spec.get("tags_default", []):
            if t.get("tag_key") == tag_key:
                entries.append(t)
    return entries


# ── Cell support classification ───────────────────────────────────────────────
# Returns one of: "direct", "derived", "profile_dependent",
#                 "user_defined_only", "absent", "unknown"

def cell_support(spec, tag_key, tag_value):
    entries = get_tag_entries(spec, tag_key)
    if not entries:
        return "unknown"

    # Aggregate across profiles: take the best level found
    LEVEL_ORDER = ["direct", "derived", "profile_dependent", "user_defined_only", "absent", "unknown"]

    best = None
    value_found_in_any = False

    for entry in entries:
        level = entry.get("support_level", "unknown")
        if level == "user_defined_only":
            if best is None:
                best = "user_defined_only"
            continue

        # Check if this specific value is handled
        value_rules = entry.get("value_rules", [])
        value_keys = [r.get("tag_value", "") for r in value_rules]
        value_found = tag_value in value_keys

        if value_found:
            value_found_in_any = True
            if best is None or LEVEL_ORDER.index(level) < LEVEL_ORDER.index(best):
                best = level
        else:
            # Value not in rules; check coverage
            coverage = entry.get("value_coverage", "partial")
            if coverage == "none":
                if best is None:
                    best = "user_defined_only"
            elif coverage == "full":
                # All values implied to be handled at this level
                if best is None or LEVEL_ORDER.index(level) < LEVEL_ORDER.index(best):
                    best = level
            else:
                # partial: value not explicitly listed → absent from this profile
                if best is None:
                    best = "absent"

    return best or "unknown"


def cell_detail(spec, tag_key, tag_value):
    """Return dict with detail info for the tooltip/panel."""
    entries = get_tag_entries(spec, tag_key)
    effects = []
    notes = []
    for entry in entries:
        for rule in entry.get("value_rules", []):
            if rule.get("tag_value") == tag_value:
                effects.append({
                    "kind": rule.get("effect_kind", ""),
                    "value": rule.get("effect_value", ""),
                    "conditions": rule.get("conditions", ""),
                })
        for n in entry.get("special_handling", []):
            notes.append(n)

    evidence = spec.get("evidence", [])
    # Also gather profile-level evidence
    for p in spec.get("profiles", []):
        evidence += p.get("evidence", [])

    issues = spec.get("related_issues", [])

    return {
        "effects": effects,
        "notes": notes[:3],
        "evidence": evidence[:4],
        "issues": [i for i in issues if tag_key in i.get("tags", [])],
        "verified_on": spec.get("verified_on", ""),
        "engine_meta": spec.get("engine_meta", {}),
    }


# ── Build data matrix ─────────────────────────────────────────────────────────

def build_matrix(specs):
    all_cols = []
    for group_name, col_keys in CAPABILITY_GROUPS:
        for key in col_keys:
            all_cols.append((group_name, key))

    matrix = {}
    for tag_key, values in TAGS.items():
        matrix[tag_key] = {}
        for val in values:
            matrix[tag_key][val] = {}
            for group_name, col_key in all_cols:
                spec = specs.get(col_key)
                if spec is None:
                    matrix[tag_key][val][col_key] = {"support": "unknown", "detail": {}}
                else:
                    support = cell_support(spec, tag_key, val)
                    detail = cell_detail(spec, tag_key, val)
                    matrix[tag_key][val][col_key] = {"support": support, "detail": detail}

    return matrix, all_cols


# ── HTML generation ───────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       font-size: 13px; background: #f5f5f5; color: #222; }
h1 { padding: 16px 20px; font-size: 18px; background: #1a1a2e; color: #eee;
     letter-spacing: .5px; }
h1 span { font-size: 12px; color: #aaa; font-weight: normal; margin-left: 12px; }

.legend { display: flex; gap: 12px; padding: 10px 20px; background: #fff;
          border-bottom: 1px solid #ddd; flex-wrap: wrap; align-items: center; }
.legend-item { display: flex; align-items: center; gap: 5px; font-size: 12px; }
.legend-swatch { width: 16px; height: 16px; border-radius: 3px; border: 1px solid #ccc; }

.grid-wrap { overflow-x: auto; padding: 16px 20px 60px; }
table { border-collapse: collapse; min-width: max-content; }

th { position: sticky; top: 0; background: #fff; z-index: 2; }
.col-group-header { background: #2d2d44; color: #eee; text-align: center;
                    font-size: 11px; font-weight: 600; letter-spacing: .5px;
                    padding: 4px 6px; text-transform: uppercase; }
.col-app-header { background: #fff; border-bottom: 2px solid #555;
                  font-size: 11px; font-weight: 600; text-align: center;
                  padding: 4px 3px; white-space: nowrap;
                  writing-mode: vertical-lr; transform: rotate(180deg);
                  height: 80px; vertical-align: bottom; }

.tag-key-row td { background: #e8eaf6; font-weight: 700; font-size: 12px;
                  padding: 6px 10px; letter-spacing: .3px; color: #333; }
.val-label { padding: 4px 10px; white-space: nowrap; font-family: monospace;
             font-size: 12px; position: sticky; left: 0; background: #fafafa;
             border-right: 1px solid #ddd; z-index: 1; min-width: 180px; }

td.cell { width: 36px; min-width: 36px; text-align: center; cursor: pointer;
          border: 1px solid #e0e0e0; font-size: 14px; transition: opacity .1s; }
td.cell:hover { opacity: .75; outline: 2px solid #555; }
td.cell.group-end { border-right: 2px solid #999; }

/* Support levels */
.direct          { background: #4caf50; }
.derived         { background: #ff9800; }
.profile_dependent { background: #ffd54f; }
.user_defined_only { background: #b0b0b0; }
.absent          { background: #ef5350; }
.unknown         { background: #f0f0f0; color: #bbb; }

/* Panel */
#panel { position: fixed; right: 0; top: 0; width: 380px; height: 100vh;
         background: #fff; box-shadow: -4px 0 20px rgba(0,0,0,.15);
         overflow-y: auto; transform: translateX(100%);
         transition: transform .2s ease; z-index: 100; padding: 20px; }
#panel.open { transform: translateX(0); }
#panel-close { float: right; font-size: 20px; cursor: pointer; color: #888;
               line-height: 1; border: none; background: none; }
#panel h2 { font-size: 15px; margin-bottom: 4px; }
#panel .subtitle { color: #888; font-size: 12px; margin-bottom: 16px; }
#panel section { margin-bottom: 16px; }
#panel h3 { font-size: 11px; text-transform: uppercase; letter-spacing: .5px;
            color: #888; margin-bottom: 6px; border-bottom: 1px solid #eee;
            padding-bottom: 4px; }
.effect-row { font-family: monospace; font-size: 12px; padding: 3px 0;
              border-bottom: 1px solid #f5f5f5; }
.effect-row span { color: #888; }
.note-item { font-size: 12px; color: #444; margin-bottom: 6px; line-height: 1.4; }
.evidence-item { font-size: 11px; margin-bottom: 8px; }
.evidence-item a { color: #1565c0; text-decoration: none; word-break: break-all; }
.evidence-item .conf { font-size: 10px; padding: 1px 5px; border-radius: 9px;
                       background: #e3f2fd; color: #1565c0; margin-left: 4px; }
.issue-item { font-size: 12px; padding: 6px 8px; border-radius: 4px;
              border: 1px solid #eee; margin-bottom: 6px; }
.issue-item a { color: #1a237e; text-decoration: none; font-weight: 600; }
.issue-item .badge { font-size: 10px; padding: 1px 6px; border-radius: 9px;
                     font-weight: 600; margin-left: 4px; }
.badge.open   { background: #e8f5e9; color: #2e7d32; }
.badge.closed { background: #fce4ec; color: #c62828; }
.issue-meta { color: #888; font-size: 10px; margin-top: 2px; }
.action-btn { display: block; margin-top: 8px; padding: 7px 12px;
              border-radius: 5px; text-align: center; font-size: 12px;
              font-weight: 600; text-decoration: none; cursor: pointer;
              border: none; width: 100%; }
.btn-new-issue { background: #1565c0; color: #fff; }
.btn-report    { background: #f5f5f5; color: #333; border: 1px solid #ccc; }
.verified { font-size: 10px; color: #aaa; margin-top: 12px; }
"""

JS = """
const panel = document.getElementById('panel');
const cells = document.querySelectorAll('td.cell');

cells.forEach(cell => {
  cell.addEventListener('click', () => {
    const d = JSON.parse(cell.dataset.detail);
    const tag_key = cell.dataset.tagKey;
    const tag_val = cell.dataset.tagVal;
    const app = cell.dataset.app;
    const support = cell.dataset.support;
    renderPanel(app, tag_key, tag_val, support, d);
    panel.classList.add('open');
  });
});

document.getElementById('panel-close').addEventListener('click', () => {
  panel.classList.remove('open');
});

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
                  .replace(/"/g,'&quot;');
}

function renderPanel(app, tag_key, tag_val, support, d) {
  const statusLabel = {
    direct: 'Direct support', derived: 'Derived support',
    profile_dependent: 'Profile-dependent', user_defined_only: 'User-defined only',
    absent: 'Absent / documented gap', unknown: 'Not documented'
  }[support] || support;

  let html = `<button id="panel-close">✕</button>
    <h2>${esc(app)}</h2>
    <div class="subtitle"><code>${esc(tag_key)}=${esc(tag_val)}</code> &nbsp;·&nbsp; ${esc(statusLabel)}</div>`;

  if (d.effects && d.effects.length) {
    html += '<section><h3>Effect</h3>';
    d.effects.forEach(e => {
      html += `<div class="effect-row">${esc(e.kind)}: <strong>${esc(e.value)}</strong>`;
      if (e.conditions) html += ` <span>(${esc(e.conditions)})</span>`;
      html += '</div>';
    });
    html += '</section>';
  }

  if (d.notes && d.notes.length) {
    html += '<section><h3>Notes</h3>';
    d.notes.forEach(n => html += `<div class="note-item">${esc(n)}</div>`);
    html += '</section>';
  }

  if (d.issues && d.issues.length) {
    html += '<section><h3>Known Issues</h3>';
    d.issues.forEach(i => {
      const badge = `<span class="badge ${esc(i.state)}">${esc(i.state)}</span>`;
      const lastReply = i.last_reply_date ? ` · last reply ${esc(i.last_reply_date)}` : '';
      html += `<div class="issue-item">
        <a href="${esc(i.url)}" target="_blank">#${i.id} ${esc(i.title)}</a>${badge}
        <div class="issue-meta">${esc(i.note || '')}${lastReply}</div>
      </div>`;
    });
    html += '</section>';
  }

  if (d.evidence && d.evidence.length) {
    html += '<section><h3>Evidence</h3>';
    d.evidence.forEach(e => {
      const isUrl = String(e.file).startsWith('http');
      const fileLink = isUrl
        ? `<a href="${esc(e.file)}" target="_blank">${esc(e.file)}</a>`
        : `<code>${esc(e.file)}</code>` + (e.line ? `:${e.line}` : '');
      html += `<div class="evidence-item">${fileLink}
        <span class="conf">${esc(e.confidence)}</span>
        <div style="color:#555;margin-top:2px">${esc(e.summary || '')}</div>
      </div>`;
    });
    html += '</section>';
  }

  // Actions
  const repoUrl = (d.engine_meta && d.engine_meta.issues) || '#';
  const newIssueUrl = repoUrl !== '#'
    ? `${repoUrl}/new?title=${encodeURIComponent('[tag-support] ' + tag_key + '=' + tag_val + ' in ' + app)}&body=${encodeURIComponent('**Tag:** `' + tag_key + '=' + tag_val + '`\\n**App:** ' + app + '\\n\\n**Issue:**\\n<!-- Describe what is wrong or missing -->')}`
    : '#';
  const reportUrl = 'https://github.com/osm-tag-support/tracker/issues/new?template=inaccuracy.md&title=' + encodeURIComponent('[report] ' + app + ' · ' + tag_key + '=' + tag_val);

  html += `<section>
    <a class="action-btn btn-new-issue" href="${esc(newIssueUrl)}" target="_blank">Open issue in ${esc(app)} tracker ↗</a>
    <a class="action-btn btn-report" href="${esc(reportUrl)}" target="_blank">Report inaccurate data</a>
  </section>`;

  if (d.verified_on) {
    html += `<div class="verified">Spec verified: ${esc(d.verified_on)}</div>`;
  }

  panel.innerHTML = html;
  document.getElementById('panel-close').addEventListener('click', () => {
    panel.classList.remove('open');
  });
}
"""

SUPPORT_ICONS = {
    "direct":            "✓",
    "derived":           "~",
    "profile_dependent": "◑",
    "user_defined_only": "—",
    "absent":            "✗",
    "unknown":           "·",
}

LEGEND = [
    ("direct",            "#4caf50", "Direct — value explicitly handled"),
    ("derived",           "#ff9800", "Derived — inferred or indirect"),
    ("profile_dependent", "#ffd54f", "Profile-dependent — depends on active profile"),
    ("user_defined_only", "#b0b0b0", "User-defined only — value not in schema"),
    ("absent",            "#ef5350", "Absent — known gap, falls through to default"),
    ("unknown",           "#f0f0f0", "Not documented in this spec"),
]


def render_html(matrix, all_cols, specs):
    # Group-end column indices for border styling
    group_end_cols = set()
    pos = 0
    for group_name, col_keys in CAPABILITY_GROUPS:
        pos += len(col_keys)
        group_end_cols.add(pos - 1)

    def th_group():
        parts = ['<tr><th class="val-label" rowspan="2"></th>']
        for group_name, col_keys in CAPABILITY_GROUPS:
            border = ' style="border-right:2px solid #999"' if group_name != CAPABILITY_GROUPS[-1][0] else ''
            parts.append(f'<th class="col-group-header" colspan="{len(col_keys)}"{border}>{group_name}</th>')
        parts.append('</tr>')
        return "".join(parts)

    def th_apps():
        parts = ['<tr>']
        idx = 0
        for group_name, col_keys in CAPABILITY_GROUPS:
            for i, key in enumerate(col_keys):
                is_last_in_group = (i == len(col_keys) - 1)
                border = ' style="border-right:2px solid #999"' if is_last_in_group and group_name != CAPABILITY_GROUPS[-1][0] else ''
                name = DISPLAY_NAMES.get(key, key.split("/")[-1])
                parts.append(f'<th class="col-app-header"{border}>{name}</th>')
            idx += len(col_keys)
        parts.append('</tr>')
        return "".join(parts)

    rows = []
    for tag_key, values in TAGS.items():
        col_count = sum(len(ck) for _, ck in CAPABILITY_GROUPS)
        rows.append(f'<tr class="tag-key-row"><td colspan="{col_count + 1}">{tag_key}</td></tr>')
        for val in values:
            row = [f'<td class="val-label">{val}</td>']
            idx = 0
            for group_name, col_keys in CAPABILITY_GROUPS:
                for i, col_key in enumerate(col_keys):
                    cell_data = matrix[tag_key][val][col_key]
                    support = cell_data["support"]
                    detail = cell_data["detail"]
                    icon = SUPPORT_ICONS.get(support, "·")
                    is_last_in_group = (i == len(col_keys) - 1)
                    group_end_cls = " group-end" if is_last_in_group and group_name != CAPABILITY_GROUPS[-1][0] else ""
                    app_name = DISPLAY_NAMES.get(col_key, col_key)
                    detail_json = json.dumps(detail, ensure_ascii=False, default=str)
                    row.append(
                        f'<td class="cell {support}{group_end_cls}" '
                        f'data-support="{support}" '
                        f'data-tag-key="{tag_key}" '
                        f'data-tag-val="{val}" '
                        f'data-app="{app_name}" '
                        f'data-detail=\'{detail_json.replace(chr(39), "&apos;")}\' '
                        f'title="{app_name}: {support}">{icon}</td>'
                    )
                idx += len(col_keys)
            rows.append(f'<tr>{"".join(row)}</tr>')

    legend_html = "".join(
        f'<div class="legend-item"><div class="legend-swatch" style="background:{color}"></div>{label}</div>'
        for _, color, label in LEGEND
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OSM Tag Support — caniuse for mappers</title>
<style>{CSS}</style>
</head>
<body>
<h1>OSM Tag Support <span>surface · smoothness · tracktype · mtb:scale · sac_scale</span></h1>
<div class="legend">{legend_html}</div>
<div class="grid-wrap">
<table>
<thead>
{th_group()}
{th_apps()}
</thead>
<tbody>
{"".join(rows)}
</tbody>
</table>
</div>
<div id="panel"><button id="panel-close">✕</button></div>
<script>{JS}</script>
</body>
</html>"""


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    specs = load_specs()
    print(f"Loaded {len(specs)} specs: {sorted(specs)}")
    matrix, all_cols = build_matrix(specs)
    html = render_html(matrix, all_cols, specs)
    out = SITE / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"Written: {out}  ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
