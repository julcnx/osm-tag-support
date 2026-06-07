# OSM Tag Support Tracker: Build Spec Prompt

## Documentation Kit (surface/smoothness/tracktype)

- Schema: docs/tag-support-schema.yaml
  - v2 supports two document shapes: single_profile_record and router_with_profiles
- Contributor checklist: docs/contributor-checklist.md
- Engine examples (using router_with_profiles):
  - data/examples/osrm.yaml
  - data/examples/osmand.yaml
  - data/examples/brouter.yaml
  - data/examples/valhalla.yaml
  - data/examples/graphhopper.yaml
  - data/examples/pgrouting.yaml

## Project overview

Build a web application that tracks support for OpenStreetMap tags across consumer applications (routers, editors, renderers). The mental model is caniuse.com, applied to OSM tags instead of browser features.

The primary audience is OSM users (not necessarily mappers) who want to know whether a tag they care about is actually usable in the apps they use, and OSM contributors who want to coordinate advocacy for better tag support. Consumer developers can also use it to benchmark their support against peers.

---

## Core concepts

**Tag**: an OSM key=value pair, e.g. `surface=fine_gravel`, `smoothness=bad`, `tracktype=grade3`.

**Consumer**: an application that reads OSM data and does something with tags. Categories:

- **Router**: OsmAnd, GraphHopper, OSRM, Valhalla, BRouter
- **Editor**: iD editor (via iD-tagging-schema), JOSM
- **Renderer**: OSM Carto, OpenTopoMap, Waymarked Trails
- **Viewer**: OsmAnd (map display, separate from routing), Maps.me, Organic Maps

**Capability**: a specific feature within a consumer. Support is tracked at the capability level, not the app level. Each consumer exposes one or more capabilities. Examples: `graphhopper:routing`, `osmand:routing`, `osmand:display`, `id-tagging-schema:preset_ui`.

Standard capability names by category:

| Category | Capability     | Meaning                                |
| -------- | -------------- | -------------------------------------- |
| Router   | `routing`      | Path selection and tag-based weighting |
| Router   | `instructions` | Turn-by-turn navigation instructions   |
| Router   | `avoidance`    | Tag-based route avoidance              |
| Editor   | `preset_ui`    | Tag appears in preset dropdown         |
| Editor   | `validation`   | Tag is validated or linted             |
| Renderer | `style`        | Tag affects visual map output          |
| Renderer | `legend`       | Tag has a legend entry                 |
| Viewer   | `display`      | Tag affects map display in viewer mode |
| Viewer   | `search`       | Tag is used in search/POI lookup       |

**Support status** (per tag per capability):

- `supported`: correctly handled, affects output as intended
- `partial`: handled in some profiles, modes, or platforms but not all
- `ignored`: tag is read but has no effect; silently discarded
- `unknown`: no verified information
- `wontfix`: maintainers have explicitly declined to support

---

## Data model

All data lives in a structured format (YAML or JSON) that can be stored in a GitHub repository and edited via PRs.

### Consumer registry

Each app has a metadata entry with its capabilities listed explicitly. Apps with a single obvious capability (e.g. OSRM only does routing, OSM Carto only renders) have one capability. Apps like OsmAnd have several.

```yaml
# data/consumers/graphhopper.yaml
id: graphhopper
name: GraphHopper
category: router
homepage: https://www.graphhopper.com
source_repo: https://github.com/graphhopper/graphhopper
capabilities:
  routing:
    id: graphhopper:routing
    description: Path selection and tag-based weighting
    verify_notes: Check profiles/ directory in source repo
  instructions:
    id: graphhopper:instructions
    description: Turn-by-turn navigation instruction generation
```

```yaml
# data/consumers/osmand.yaml
id: osmand
name: OsmAnd
category: router # primary category; display capability listed separately
homepage: https://osmand.net
source_repo: https://github.com/osmandapp/OsmAnd-resources
capabilities:
  routing:
    id: osmand:routing
    description: Routing profiles and tag-based weighting
    verify_notes: Check routing/ directory in OsmAnd-resources
  display:
    id: osmand:display
    description: Map display in viewer mode (style, icons, labels)
```

```yaml
# data/consumers/id-tagging-schema.yaml
id: id-tagging-schema
name: iD Editor
category: editor
homepage: https://wiki.openstreetmap.org/wiki/ID
source_repo: https://github.com/openstreetmap/id-tagging-schema
capabilities:
  preset_ui:
    id: id-tagging-schema:preset_ui
    description: Tag value appears in preset dropdown
  validation:
    id: id-tagging-schema:validation
    description: Tag is validated or flagged for typos
```

### Tag entry

Support is declared per capability. Tags omit capabilities that are not applicable, which renders as `unknown` in the matrix.

```yaml
# data/tags/surface=fine_gravel.yaml
key: surface
value: fine_gravel
description: Loose fine gravel, particle size < 8mm. Unpaved but compact when dry.
wiki_url: https://wiki.openstreetmap.org/wiki/Tag:surface%3Dfine_gravel
added_to_wiki: 2021-03
consumers:
  osrm:routing:
    status: ignored
    notes: No profile entry; falls back to surface=gravel weighting
    evidence: https://github.com/Project-OSRM/osrm-backend/...
    last_verified: 2025-11
  graphhopper:routing:
    status: partial
    notes: Affects bicycle profile only; car profile ignores it
    evidence: https://github.com/graphhopper/graphhopper/...
    since: 2023-04
    last_verified: 2026-01
  osmand:routing:
    status: supported
    notes: Penalised in car profile; usable in bicycle and pedestrian
    evidence: https://github.com/osmandapp/OsmAnd-resources/...
    last_verified: 2026-02
  osmand:display:
    status: unknown
  id-tagging-schema:preset_ui:
    status: supported
    notes: Present in surface dropdown
    evidence: https://github.com/openstreetmap/id-tagging-schema/...
    last_verified: 2026-01
```

Tags like `lanes=*` would omit renderer capabilities and focus on `routing:instructions` and `editor:preset_ui`. The schema does not change per tag type; relevance is expressed by what is included or left as `unknown`.

### Tag group

Tags can be grouped by key (all `surface=*` values, all `smoothness=*` values, etc.) for filtered views.

---

## UI: main views

### 1. Tag matrix (default view)

A grid modeled on caniuse.com:

- Rows: tag values (grouped by key, expandable/collapsible)
- Columns: capabilities, grouped visually by consumer category (Router | Editor | Renderer | Viewer), then by app

Cell colors:

- Green: supported
- Yellow: partial
- Red: ignored
- Grey: unknown
- Dark grey / strikethrough: wontfix

Clicking a cell opens a detail panel showing: status, notes, evidence link, since/last_verified dates, and a "flag as outdated" button.

### 2. Tag detail page (`/tag/surface=fine_gravel`)

Full breakdown for a single tag:

- Description and wiki link
- Consumer support table with full notes, grouped by category
- History / changelog of status changes
- Link to open a pre-filled GitHub issue for a specific capability (the "follow-up" / advocacy workflow)

### 3. Consumer detail page (`/consumer/graphhopper`)

All tags tracked for a given consumer, with status per capability. Useful for consumer developers to see their coverage at a glance.

### 4. Key group view (`/key/surface`)

All values under a single key (surface=asphalt, surface=fine_gravel, etc.) with their full capability matrix. This is the most common entry point for OSM contributors.

---

## Filtering and navigation

- Filter matrix by: tag key, consumer category, capability type, status (e.g. show only "ignored" or "unknown")
- Search by tag value or consumer name
- "Show only gaps" toggle: hides well-supported cells, surfaces advocacy targets
- Sortable columns

---

## Contribution workflow

All data is managed via a GitHub repository. The web app is static (no backend), reading from the compiled data files at build time or from raw GitHub URLs at runtime.

Contribution paths:

1. **Flag as outdated**: button on any cell opens a pre-filled GitHub issue
2. **Submit correction**: links to a GitHub PR template with the YAML structure pre-populated
3. **Bulk import**: CLI tool (optional, future) to parse router source files and propose new entries

---

## AI-assisted update workflow (future / optional layer)

An AI agent periodically:

- Scans router changelogs and GitHub issues for surface/smoothness/tracktype mentions
- Proposes YAML diffs as draft PRs
- Drafts outreach GitHub issues to consumer maintainers for unsupported tags ("fine_gravel has no GraphHopper car profile entry: here is a suggested PR")

This is not part of v1 but the data schema should support it (evidence URLs, last_verified dates, since fields).

---

## Initial tag scope (v1)

Start with `surface=*` only. Design schema and UI to handle multiple keys from the start. Extend to `smoothness=*`, `tracktype=*`, `sac_scale=*`, `mtb:scale=*`, `dirtbike:scale=*` in subsequent iterations.

Initial consumer list (v1):

- Routers: OsmAnd, GraphHopper, OSRM, Valhalla, BRouter
- Editors: iD (iD-tagging-schema), JOSM
- Renderers: OSM Carto (optional, lower priority)

---

## Tech stack (suggested, adjust to repo conventions)

- Static site: Astro or plain Vite + React
- Data: YAML files in `/data/tags/` and `/data/consumers/`, compiled to JSON at build time
- Hosting: GitHub Pages or Netlify
- Styling: Tailwind or CSS modules; caniuse-style grid layout
- No backend required for v1

---

## URL / hosting decision

Standalone domain (e.g. `osmtags.support` or similar) rather than a subdomain of `th.unpaved.app`, since scope is global and not Thailand-specific. Cross-link from unpaved.app where relevant.

---

## Out of scope for v1

- User accounts or logins
- Real-time data fetching from consumer APIs
- Automated wiki updates
- Coverage of non-surface tags (planned for v2+)
