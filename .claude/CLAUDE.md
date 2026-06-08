# OSM Tag Support Tracker

## Project structure

- `registry/` — YAML files, one per tool/engine, documenting tag support
- `schema/tag-support-schema.yaml` — schema definition for registry files
- `scripts/generate.py` — builds `site/data.json` from the registry
- `site/` — static site (index.html + data.json)
- `sources/` — full git clones of upstream repos used as evidence sources

## Evidence URLs

All `evidence[].file` values must be full `https://` URLs. No relative paths allowed.

### Converting local source references to GitHub URLs

When a new evidence entry references a local file (e.g. from a `sources/` clone), convert it to a permanent GitHub URL using the commit hash from `source_ref`:

```
sources/REPO_DIR/path/to/file  +  source_ref: HASH
  =>  https://github.com/ORG/REPO/blob/HASH/path/to/file#LN
```

Include `#LN` when `line > 1`.

### Repo directory to GitHub URL mapping

| `sources/` dir       | GitHub URL                                          |
|----------------------|-----------------------------------------------------|
| `OsmAnd-resources`   | https://github.com/osmandapp/OsmAnd-resources       |
| `brouter`            | https://github.com/abrensch/brouter                 |
| `graphhopper`        | https://github.com/graphhopper/graphhopper          |
| `osrm-backend`       | https://github.com/Project-OSRM/osrm-backend        |
| `valhalla`           | https://github.com/valhalla/valhalla                |
| `openstreetmap-americana` | https://github.com/osm-americana/openstreetmap-americana |
| `MapComplete`        | https://github.com/pietervdvn/MapComplete            |
| `id-tagging-schema`  | https://github.com/openstreetmap/id-tagging-schema  |
| `shortbread-docs`    | https://github.com/shortbread-tiles/shortbread-docs |
| `StreetComplete`     | https://github.com/streetcomplete/StreetComplete    |
| `openstreetmap-carto`| https://github.com/gravitystorm/openstreetmap-carto |
| `organicmaps`        | https://github.com/organicmaps/organicmaps          |

### Cloning a new source repo

Full clones (not shallow) are required so `source_ref` commit hashes resolve correctly:

```bash
git clone https://github.com/ORG/REPO.git sources/REPO
```

### Known path migrations (as of 2026-06-08)

These upstream repos reorganized their files. Evidence URLs were updated accordingly.

| Tool | Old path | New path |
|------|----------|----------|
| StreetComplete | `app/src/main/kotlin/.../quests/` | `app/src/androidMain/kotlin/.../quests/` (Kotlin Multiplatform migration) |
| StreetComplete | `AddSmoothness.kt` | `AddRoadSmoothness.kt` |
| StreetComplete | `app/src/main/res/drawable/ic_quest_surface_detail` | `app/src/androidMain/res/drawable/quest_street_surface_detail.xml` |
| openstreetmap-americana | `ZeLonewolf/` org | `osm-americana/` org |
| openstreetmap-americana | `style/style.json` | `src/americana.js` (style is now programmatic) |
| openstreetmap-carto | `roads.mss` | `style/roads.mss` |
| shortbread-docs | `content/schema/streets.md` | `shortbread-website/content/schema/1.0.md` |
| MapComplete | `assets/layers/cyclostreets/` | `assets/layers/cyclestreets/` |
| MapComplete | `assets/layers/bicycle_infrastructure/` | `assets/layers/cycleways_and_roads/` |
| id-tagging-schema | `data/fields/mtb_scale.json` | `data/fields/mtb/scale.json` |
| organicmaps | `routing/bicycle_directions.cpp` | `libs/routing_common/bicycle_model.cpp` |
| organicmaps | `routing/pedestrian_directions.cpp` | `libs/routing/pedestrian_directions.cpp` |

## Regenerating the site

```bash
python3 scripts/generate.py
```

This reads all `registry/**/*.yaml` files and writes `site/data.json`.
