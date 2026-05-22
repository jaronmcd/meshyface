# Third-Party Notices

This project includes or may load the following third-party components. These notices apply to bundled browser libraries, bundled data, runtime network services, and Python dependencies. The project's root license, if any, does not supersede third-party licenses.

## Bundled Browser Libraries

### Leaflet 1.9.4

Files:
- `meshdash/assets/vendor/leaflet-1.9.4.js`
- `meshdash/assets/vendor/leaflet-1.9.4.css`
- `meshdash/assets/vendor/images/*`

License:
- BSD 2-Clause.

Included text:
- `third_party/licenses/leaflet-BSD-2-Clause.txt`

### Leaflet.heat 0.2.0 / simpleheat

File:
- `meshdash/assets/vendor/leaflet-heat-0.2.0.js`

License:
- BSD-style permissive terms (BSD 2-Clause-compatible) from Leaflet.heat and simpleheat.

Included text:
- `third_party/licenses/leaflet-heat-BSD-2-Clause.txt`
- `third_party/licenses/simpleheat-BSD-2-Clause.txt`

## Bundled Data

### Material Design Icons / @mdi/js

File:
- `meshdash/assets/dashboard.js.chat.events.core.identity.favorites_selection.favorites_state_ui.tmpl`

Use:
- Embeds the `mdiNewBox` SVG path for the automatic `New` node tag icon.

License:
- Apache License 2.0.

Included text:
- `third_party/licenses/apache-2.0.txt`

Version note:
- Exact source package version was not recorded in this repository; maintainers should record it when regenerating this icon path.

### Offline atlas

File:
- `meshdash/assets/offline_atlas_na.min.json`

Source metadata in payload:
- Natural Earth 110m global base layers.
- Natural Earth/GeoNames North America detail layers.
- GeoNames cities5000.

License/terms:
- Natural Earth data is public domain.
- GeoNames data is CC BY 4.0 and requires attribution.

Runtime attribution:
- When offline atlas layers are active, the Leaflet attribution control shows Natural Earth and GeoNames attribution in the map UI.

### Unicode emoji catalog

File:
- `meshdash/assets/chat_emoji_catalog.min.json`

Source:
- Generated from Unicode `emoji-test.txt`, Emoji `17.0`.
- Current bundled payload date: `2025-08-04, 20:55:31 GMT`.

License/terms:
- Unicode Data Files are under Unicode License v3 unless otherwise indicated by Unicode.
- Unicode copyright/permission notice is included in:
  - `third_party/licenses/unicode-license-v3.txt`

Generation documentation:
- `third_party/emoji_catalog_generation.md`

### Zork 1977 data

File:
- `meshdash/games/zork/upstream_1977/zork-master/zork/dung.56`

Source:
- MIT Libraries Department of Distinctive Collections (MITDDC) Zork repository: `https://github.com/MITDDC/zork`

Rights statement (upstream qualifier retained):
- "To the extent that MIT holds rights in these files, they are released under the terms of the MIT No Attribution License (MIT-0)."

Included text:
- `third_party/licenses/mitddc-zork-mit-no-attribution.txt`

Preferred citation (from upstream README):
- `[filename], Zork source code, 1977, Massachusetts Institute of Technology, Tapes of Tech Square (ToTS) collection, MC-0741. Massachusetts Institute of Technology, Department of Distinctive Collections, Cambridge, Massachusetts. swh:1:dir:ab9e2babe84cfc909c64d66291b96bb6b9d8ca15`

### Colossal Cave Adventure

- Colossal Cave Adventure materials are not bundled in this repository.
- The previously reviewed Adventure data was removed before publication staging because redistribution terms were not clearly documented.

## Runtime Network Assets

- Online basemap mode uses OpenStreetMap tiles.
- Runtime tile URL is:
  - `https://tile.openstreetmap.org/{z}/{x}/{y}.png`
- Runtime map attribution includes a visible OpenStreetMap copyright link:
  - `https://www.openstreetmap.org/copyright`
- The project does not treat OpenStreetMap as an offline atlas source.
- Offline atlas generation/runtime does not bulk-download or prefetch OSM tiles.

## Python Dependencies

Direct dependency files:
- Runtime: `requirements.txt`
- Dev/test: `requirements-dev.txt`

Pinned direct dependencies in this branch:
- `meshtastic==2.7.8`
- `pypubsub==4.0.7`
- `protobuf==7.34.1`
- `pytest==8.4.2` (dev)

Generated report:
- `THIRD_PARTY_PYTHON_DEPENDENCIES.md`

License-risk note:
- Current PyPI metadata for `meshtastic` reports `GPL-3.0-only`; maintainers must review compatibility before selecting the repository root license.

Root-license note:
- This file documents third-party notices only; selecting and adding a root `LICENSE` remains a maintainer decision.

## AI-Assisted Contributions

Some source code, documentation, and tests in this repository may have been created or edited with AI-assisted development tools. Maintainers review, modify, and accept project responsibility for committed changes.

AI assistance is not treated as a bundled third-party runtime component. Known bundled data, external assets, and package dependencies are tracked separately above.
