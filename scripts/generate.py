#!/usr/bin/env python3
"""
Generate site/data.json and site/index.html.

  site/data.json   — full support matrix; load it with any tool
  site/index.html  — self-contained viewer (loads data.json via fetch)

Run: python3 scripts/generate.py
Serve: cd site && python3 -m http.server
"""

import json
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
REGISTRY = ROOT / "registry"
SITE = ROOT / "site"
SITE.mkdir(exist_ok=True)

# ── App column definitions (order = column order in grid) ─────────────────────

# Tag key display order in the grid (sac_scale before mtb:scale)
TAG_ORDER = ["surface", "smoothness", "tracktype", "sac_scale"]

CAPABILITY_GROUPS = [
    ("Routing",   [
        "routing/osrm", "routing/brouter", "routing/graphhopper",
        "routing/valhalla", "routing/osmand", "routing/organic-maps",
    ]),
    ("Editors",   [
        "editors/josm", "editors/id", "editors/vespucci",
        "editors/mapcomplete", "editors/streetcomplete",
    ]),
    ("Renderers", [
        "renderers/openstreetmap-carto", "renderers/americana",
        "renderers/shortbread",
    ]),
    ("Display",   [
        "display/osmand", "display/organic-maps",
    ]),
]

DISPLAY_NAMES = {
    "routing/osrm":                  "OSRM",
    "routing/brouter":               "BRouter",
    "routing/graphhopper":           "GraphHopper",
    "routing/valhalla":              "Valhalla",
    "routing/osmand":                "OsmAnd",
    "routing/organic-maps":          "Organic Maps",
    "editors/josm":                  "JOSM",
    "editors/id":                    "iD",
    "editors/vespucci":              "Vespucci",
    "editors/mapcomplete":           "MapComplete",
    "editors/streetcomplete":        "StreetComplete",
    "renderers/openstreetmap-carto": "OSM Carto",
    "renderers/americana":           "Americana",
    "renderers/shortbread":          "Shortbread",
    "display/osmand":                "OsmAnd",
    "display/organic-maps":          "Organic Maps",
}

LEVEL_ORDER = [
    "direct", "derived", "profile_dependent",
    "user_defined_only", "fallback", "absent", "unknown",
]


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_tag_values():
    path = REGISTRY / "tag-values.json"
    with open(path) as f:
        tv = json.load(f)
    # Return ordered dict: tag_key → list of value dicts
    keys = [k for k in tv if k != "meta"]
    return tv["meta"], {k: tv[k] for k in keys}


def load_specs():
    specs = {}
    for path in REGISTRY.rglob("*.yaml"):
        key = path.relative_to(REGISTRY).with_suffix("").as_posix()
        with open(path) as f:
            specs[key] = yaml.safe_load(f)
    return specs


# ── Per-cell support level ────────────────────────────────────────────────────

def get_tag_entries(spec, tag_key):
    entries = []
    for t in spec.get("tags", []) + spec.get("tags_default", []):
        if t.get("tag_key") == tag_key:
            entries.append(t)
    for p in spec.get("profiles", []):
        for t in p.get("tags", []):
            if t.get("tag_key") == tag_key:
                entries.append(t)
    return entries


def cell_support(spec, tag_key, tag_value):
    entries = get_tag_entries(spec, tag_key)
    if not entries:
        return "unknown"

    best = None

    def better(a, b):
        # lower index = better support
        return b is None or LEVEL_ORDER.index(a) < LEVEL_ORDER.index(b)

    for entry in entries:
        level = entry.get("support_level", "unknown")
        if level == "user_defined_only":
            if better("user_defined_only", best):
                best = "user_defined_only"
            continue

        value_keys = [r.get("tag_value", "") for r in entry.get("value_rules", [])]
        if tag_value in value_keys:
            if better(level, best):
                best = level
        else:
            coverage = entry.get("value_coverage", "partial")
            if coverage == "full":
                if better(level, best):
                    best = level
            elif coverage == "none":
                if better("user_defined_only", best):
                    best = "user_defined_only"
            else:  # partial — value not listed
                ub = entry.get("unknown_value_behavior", "")
                if ub in ("fallback_default", "ignore"):
                    if better("fallback", best):
                        best = "fallback"
                elif ub == "absent":
                    if better("absent", best):
                        best = "absent"
                else:
                    # unknown_value_behavior not declared: we haven't verified this
                    if better("unknown", best):
                        best = "unknown"

    return best or "unknown"


def cell_detail(spec, tag_key, tag_value):
    entries = get_tag_entries(spec, tag_key)
    effects, notes = [], []
    for entry in entries:
        for rule in entry.get("value_rules", []):
            if rule.get("tag_value") == tag_value:
                e = {"kind": rule.get("effect_kind", ""),
                     "value": rule.get("effect_value", "")}
                if rule.get("conditions"):
                    e["conditions"] = rule["conditions"]
                effects.append(e)
        notes += entry.get("special_handling", [])

    evidence = list(spec.get("evidence", []))
    for p in spec.get("profiles", []):
        evidence += p.get("evidence", [])

    issues = [
        i for i in spec.get("related_issues", [])
        if tag_key in i.get("tags", [])
    ]

    return {
        "effects":     effects,
        "notes":       notes[:3],
        "evidence":    [
            {k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
             for k, v in e.items()}
            for e in evidence[:4]
        ],
        "issues":      [
            {k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
             for k, v in i.items()}
            for i in issues
        ],
        "verified_on": str(spec.get("verified_on", "")),
        "engine_meta": spec.get("engine_meta", {}),
    }


# ── Build data.json ───────────────────────────────────────────────────────────

def build_data(tag_values_meta, tag_values, specs):
    all_cols = [(g, k) for g, keys in CAPABILITY_GROUPS for k in keys]

    apps = []
    for group, col_keys in CAPABILITY_GROUPS:
        for key in col_keys:
            spec = specs.get(key, {})
            apps.append({
                "id":    key,
                "name":  DISPLAY_NAMES.get(key, key.split("/")[-1]),
                "group": group,
                "meta":  spec.get("engine_meta", {}),
            })

    tags_out = {}
    ordered_keys = [k for k in TAG_ORDER if k in tag_values]
    for tag_key in ordered_keys:
        value_dicts = tag_values[tag_key]
        matrix = {}
        for vd in value_dicts:
            val = vd["value"]
            row = {}
            for _, col_key in all_cols:
                spec = specs.get(col_key)
                if spec is None:
                    row[col_key] = {"support": "unknown"}
                else:
                    support = cell_support(spec, tag_key, val)
                    detail  = cell_detail(spec, tag_key, val)
                    row[col_key] = {"support": support, **detail}
            matrix[val] = row

        behaviors = {}
        for _, col_key in all_cols:
            spec = specs.get(col_key, {})
            entries = get_tag_entries(spec, tag_key)
            if entries:
                behaviors[col_key] = {
                    "missing": entries[0].get("missing_tag_behavior", ""),
                    "unknown": entries[0].get("unknown_value_behavior", ""),
                }
            else:
                behaviors[col_key] = {"missing": "", "unknown": ""}

        tags_out[tag_key] = {
            "values":    value_dicts,
            "matrix":    matrix,
            "behaviors": behaviors,
        }

    return {
        "meta": {
            "generated_on":    str(date.today()),
            "tag_values_meta": tag_values_meta,
            "apps": apps,
            "groups": [{"name": g, "app_ids": keys} for g, keys in CAPABILITY_GROUPS],
        },
        "tags": tags_out,
    }


# ── HTML ──────────────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OSM Tag Support</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:13px;background:#f5f5f5;color:#222}
#header{padding:12px 20px;background:#1a1a2e;color:#eee;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
#header h1{font-size:17px;font-weight:700}
#header span{font-size:12px;color:#aaa}
#legend{display:flex;gap:10px;padding:8px 20px;background:#fff;border-bottom:1px solid #ddd;flex-wrap:wrap;align-items:center}
.ls{display:flex;align-items:center;gap:4px;font-size:11px;white-space:nowrap}
.lc{width:14px;height:14px;border-radius:3px;border:1px solid rgba(0,0,0,.1)}
#loading{padding:40px;text-align:center;color:#888}
#grid-wrap{overflow-x:auto;padding:12px 20px 80px}
table{border-collapse:collapse;min-width:max-content}
thead th{position:sticky;top:0;z-index:2}
.gh{background:#2d2d44;color:#eee;text-align:center;font-size:10px;font-weight:700;letter-spacing:.5px;padding:4px 6px;text-transform:uppercase}
.ah{background:#fff;border-bottom:2px solid #555;font-size:12px;font-weight:600;text-align:center;
    writing-mode:vertical-lr;transform:rotate(180deg);height:110px;vertical-align:bottom;padding:4px 3px;white-space:nowrap}
.tag-section td{background:#e8eaf6;font-weight:700;font-size:12px;padding:5px 10px;letter-spacing:.2px}
.vl{padding:3px 10px;white-space:nowrap;font-family:monospace;font-size:11px;
    position:sticky;left:0;background:#fafafa;border-right:1px solid #ddd;z-index:1;min-width:190px}
.vl .src{font-size:9px;color:#aaa;margin-left:4px}
td.c{width:40px;min-width:40px;text-align:center;cursor:pointer;border:1px solid #e8e8e8;font-size:12px}
td.c:hover{outline:2px solid #333;z-index:1;position:relative}
td.c.ge{border-right:2px solid #bbb}
.direct{background:#4caf50;color:#fff}
.derived{background:#4caf50;color:#fff}
.profile_dependent{background:#4caf50;color:#fff}
.user_defined_only{background:#ef5350;color:#fff}
.fallback{background:#ffa726;color:#fff}
.absent{background:#ef5350;color:#fff}
.unknown{background:#ef5350;color:#fff}
.tag-sum td{border-top:2px solid #ddd}
.sum-lbl{font-size:9px;color:#999;font-style:italic;background:#f5f5f5}
/* panel */
#panel{position:fixed;right:0;top:0;width:360px;height:100vh;background:#fff;
       box-shadow:-3px 0 16px rgba(0,0,0,.15);overflow-y:auto;
       transform:translateX(100%);transition:transform .18s ease;z-index:100;padding:18px}
#panel.open{transform:translateX(0)}
#pcls{float:right;font-size:20px;cursor:pointer;border:none;background:none;color:#888;line-height:1}
#panel h2{font-size:14px;margin-bottom:3px}
.psub{color:#888;font-size:11px;margin-bottom:14px}
#panel section{margin-bottom:14px}
#panel h3{font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:#999;
          margin-bottom:5px;border-bottom:1px solid #eee;padding-bottom:3px}
.ef{font-family:monospace;font-size:11px;padding:2px 0;border-bottom:1px solid #f5f5f5}
.ef span{color:#999}
.ni{font-size:11px;color:#444;margin-bottom:5px;line-height:1.4}
.ev{font-size:10px;margin-bottom:7px}
.ev a{color:#1565c0;text-decoration:none;word-break:break-all}
.ev .cf{font-size:9px;padding:1px 4px;border-radius:8px;background:#e3f2fd;color:#1565c0;margin-left:3px}
.ev .es{color:#666;margin-top:1px}
.iss{font-size:11px;padding:5px 7px;border-radius:4px;border:1px solid #eee;margin-bottom:5px}
.iss a{color:#1a237e;text-decoration:none;font-weight:600}
.badge{font-size:9px;padding:1px 5px;border-radius:8px;font-weight:700;margin-left:3px}
.badge.open{background:#e8f5e9;color:#2e7d32}
.badge.closed{background:#fce4ec;color:#c62828}
.im{color:#888;font-size:9px;margin-top:2px}
.btn{display:block;margin-top:7px;padding:6px 10px;border-radius:4px;text-align:center;
     font-size:11px;font-weight:600;text-decoration:none;cursor:pointer;border:none;width:100%}
.btn-p{background:#1565c0;color:#fff}
.btn-s{background:#f5f5f5;color:#333;border:1px solid #ccc;margin-top:4px}
.vdate{font-size:9px;color:#bbb;margin-top:10px}
</style>
</head>
<body>
<div id="header">
  <h1>OSM Tag Support</h1>
  <span>surface · smoothness · tracktype · mtb:scale · sac_scale</span>
  <span id="gen-date" style="margin-left:auto"></span>
</div>
<div id="legend">
  <div class="ls"><div class="lc direct"></div>supported</div>
  <div class="ls"><div class="lc fallback"></div>ignored (fallback)</div>
  <div class="ls"><div class="lc absent"></div>absent</div>
</div>
<div id="loading">Loading data…</div>
<div id="grid-wrap" style="display:none"></div>
<div id="panel"><button id="pcls">✕</button></div>
<script>
const ICONS = {direct:'✓',derived:'✓',profile_dependent:'✓',user_defined_only:'✗',fallback:'~',absent:'✗',unknown:'✗'};

async function init() {
  let d;
  try {
    const r = await fetch('data.json');
    d = await r.json();
  } catch(e) {
    document.getElementById('loading').textContent = 'Error loading data.json — serve this directory with: python3 -m http.server';
    return;
  }
  document.getElementById('loading').style.display = 'none';
  document.getElementById('grid-wrap').style.display = '';
  document.getElementById('gen-date').textContent = 'generated ' + d.meta.generated_on;
  renderGrid(d);
}

function esc(s){
  return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function renderGrid(d) {
  const groups = d.meta.groups;
  const apps   = d.meta.apps;
  const appIds = apps.map(a => a.id);

  // group-end set
  const groupEnds = new Set();
  let pos = 0;
  for (const g of groups) {
    pos += g.app_ids.length;
    groupEnds.add(pos - 1);
  }

  let html = '<table><thead>';

  // group header row
  html += '<tr><th class="vl" rowspan="2" style="background:#fff;z-index:3"></th>';
  for (let gi = 0; gi < groups.length; gi++) {
    const g = groups[gi];
    const last = gi === groups.length - 1;
    html += `<th class="gh" colspan="${g.app_ids.length}"${last ? '' : ' style="border-right:2px solid #777"'}>${esc(g.name)}</th>`;
  }
  html += '</tr>';

  // app name row
  html += '<tr>';
  for (let ai = 0; ai < apps.length; ai++) {
    const a = apps[ai];
    const ge = groupEnds.has(ai) && ai < apps.length - 1;
    html += `<th class="ah${ge ? ' ge' : ''}">${esc(a.name)}</th>`;
  }
  html += '</tr></thead><tbody>';

  for (const [tagKey, tagData] of Object.entries(d.tags)) {
    html += `<tr class="tag-section"><td colspan="${apps.length + 1}">${esc(tagKey)}</td></tr>`;

    for (const vd of tagData.values) {
      const val = vd.value;
      const appOnly = vd.sources && !vd.sources.includes('wiki')
        ? ' <span class="src">consumer-only</span>' : '';
      html += `<tr><td class="vl">${esc(val)}${appOnly}</td>`;

      for (let ai = 0; ai < apps.length; ai++) {
        const a = apps[ai];
        const cell = tagData.matrix[val]?.[a.id] ?? {support: 'unknown'};
        const sup = cell.support;
        const icon = ICONS[sup] || '·';
        const ge = groupEnds.has(ai) && ai < apps.length - 1;
        html += `<td class="c ${esc(sup)}${ge ? ' ge' : ''}" `
             + `data-tag="${esc(tagKey)}" data-val="${esc(val)}" data-app="${esc(a.id)}" `
             + `title="${esc(a.name)}: ${esc(sup)}">${icon}</td>`;
      }

      html += '</tr>';
    }

    function behaviorCell(val, ge) {
      let cls, icon, title;
      if (!val) {
        cls = 'absent'; icon = '✗'; title = 'not documented';
      } else if (val === 'none' || val === 'ignore') {
        cls = 'direct'; icon = '✓'; title = 'ignored — no effect';
      } else {
        cls = 'fallback'; icon = '~'; title = val;
      }
      return `<td class="c ${cls}${ge ? ' ge' : ''}" title="${esc(title)}">${icon}</td>`;
    }

    html += '<tr class="tag-sum"><td class="vl sum-lbl">tag missing</td>';
    for (let ai = 0; ai < apps.length; ai++) {
      const b = tagData.behaviors?.[apps[ai].id] ?? {};
      html += behaviorCell(b.missing, groupEnds.has(ai) && ai < apps.length - 1);
    }
    html += '</tr>';

    html += '<tr class="tag-sum"><td class="vl sum-lbl">unknown value</td>';
    for (let ai = 0; ai < apps.length; ai++) {
      const b = tagData.behaviors?.[apps[ai].id] ?? {};
      html += behaviorCell(b.unknown, groupEnds.has(ai) && ai < apps.length - 1);
    }
    html += '</tr>';
  }

  html += '</tbody></table>';
  document.getElementById('grid-wrap').innerHTML = html;

  // click → panel
  document.querySelectorAll('td.c').forEach(td => {
    td.addEventListener('click', () => {
      const tagKey = td.dataset.tag;
      const val    = td.dataset.val;
      const appId  = td.dataset.app;
      const app    = d.meta.apps.find(a => a.id === appId);
      const cell   = d.tags[tagKey].matrix[val][appId];
      const vd     = d.tags[tagKey].values.find(v => v.value === val);
      openPanel(app, tagKey, val, cell, vd);
    });
  });
}

function openPanel(app, tagKey, val, cell, vd) {
  const sup = cell.support;
  const statusLabels = {
    direct:'Supported', derived:'Supported (derived)',
    profile_dependent:'Profile-dependent', user_defined_only:'User-defined only',
    fallback:'Ignored — road-class fallback used', absent:'Absent — documented gap',
    unknown:'Not documented'
  };
  let html = `<button id="pcls">✕</button>
    <h2>${esc(app.name)}</h2>
    <div class="psub"><code>${esc(tagKey)}=${esc(val)}</code> &nbsp;·&nbsp; ${esc(statusLabels[sup]||sup)}</div>`;

  if (sup === 'fallback') {
    html += `<section><h3>Status</h3><div class="ni">This value is not recognized by ${esc(app.name)}. The tag is silently discarded and the way's road class drives surface costing instead — routing continues but ignores the actual surface.</div></section>`;
  } else if (sup === 'absent') {
    html += `<section><h3>Status</h3><div class="ni">Documented gap: ${esc(app.name)} does not handle <code>${esc(tagKey)}=${esc(val)}</code>.</div></section>`;
  } else if (sup === 'unknown') {
    html += `<section><h3>Status</h3><div class="ni">No documentation for this combination. ${esc(app.name)} may or may not handle this value — the spec has not been verified.</div></section>`;
  }

  if (vd?.note) {
    html += `<section><h3>Value note</h3><div class="ni">${esc(vd.note)}</div></section>`;
  }

  if (cell.effects?.length) {
    html += '<section><h3>Effect</h3>';
    cell.effects.forEach(e => {
      html += `<div class="ef">${esc(e.kind)}: <strong>${esc(e.value)}</strong>`;
      if (e.conditions) html += ` <span>(${esc(e.conditions)})</span>`;
      html += '</div>';
    });
    html += '</section>';
  }

  if (cell.notes?.length) {
    html += '<section><h3>Notes</h3>';
    cell.notes.forEach(n => html += `<div class="ni">${esc(n)}</div>`);
    html += '</section>';
  }

  if (cell.issues?.length) {
    html += '<section><h3>Known Issues</h3>';
    cell.issues.forEach(i => {
      const lr = i.last_reply_date ? ` · last reply ${esc(i.last_reply_date)}` : '';
      html += `<div class="iss">
        <a href="${esc(i.url)}" target="_blank">#${i.id} ${esc(i.title)}</a>
        <span class="badge ${esc(i.state)}">${esc(i.state)}</span>
        <div class="im">${esc(i.note||'')}${lr}</div>
      </div>`;
    });
    html += '</section>';
  }

  if (cell.evidence?.length) {
    html += '<section><h3>Evidence</h3>';
    cell.evidence.forEach(e => {
      const isUrl = String(e.file).startsWith('http');
      const fl = isUrl
        ? `<a href="${esc(e.file)}" target="_blank">${esc(e.file)}</a>`
        : `<code>${esc(e.file)}</code>${e.line ? ':'+e.line : ''}`;
      html += `<div class="ev">${fl}<span class="cf">${esc(e.confidence)}</span>
        <div class="es">${esc(e.summary||'')}</div></div>`;
    });
    html += '</section>';
  }

  // action buttons
  const issuesUrl = app.meta?.issues || '#';
  const newUrl = issuesUrl !== '#'
    ? `${issuesUrl}/new?title=${encodeURIComponent('[tag-support] '+tagKey+'='+val+' in '+app.name)}`
      + `&body=${encodeURIComponent('**Tag:** \`'+tagKey+'='+val+'\`\n**App:** '+app.name+'\n\n**Issue:**\n<!-- describe the gap or inaccuracy -->')}`
    : '#';
  const reportUrl = 'https://github.com/YOUR_ORG/osm-tag-support/issues/new'
    + `?template=report.md&title=${encodeURIComponent('[report] '+app.name+' · '+tagKey+'='+val)}`;
  html += `<section>
    <a class="btn btn-p" href="${esc(newUrl)}" target="_blank">Open issue in ${esc(app.name)} tracker ↗</a>
    <a class="btn btn-s" href="${esc(reportUrl)}" target="_blank">Report inaccurate data</a>
  </section>`;

  if (cell.verified_on) {
    html += `<div class="vdate">Spec verified: ${esc(cell.verified_on)}</div>`;
  }

  const panel = document.getElementById('panel');
  panel.innerHTML = html;
  document.getElementById('pcls').addEventListener('click', () => panel.classList.remove('open'));
  panel.classList.add('open');
}

document.getElementById('pcls').addEventListener('click', () => {
  document.getElementById('panel').classList.remove('open');
});

init();
</script>
</body>
</html>
"""


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    tv_meta, tag_values = load_tag_values()
    specs = load_specs()
    print(f"Loaded {len(specs)} specs, {sum(len(v) for v in tag_values.values())} tag values")

    data = build_data(tv_meta, tag_values, specs)

    data_path = SITE / "data.json"
    with open(data_path, "w") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Written: {data_path}  ({data_path.stat().st_size:,} bytes)")

    html_path = SITE / "index.html"
    html_path.write_text(HTML_TEMPLATE, encoding="utf-8")
    print(f"Written: {html_path}  ({html_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
