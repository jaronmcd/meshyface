# Publication Checklist

Meshyface is currently staged as a private repository. Before making it public, complete these checks.

## Required

- Maintainer selected and added the repository root `LICENSE` file.
- `THIRD_PARTY_NOTICES.md` contains resolved notices (no release TODO placeholders).
- Vendored Leaflet/Leaflet.heat notices are present and full license texts are included in `third_party/licenses/`.
- Unicode emoji catalog generation is documented in `third_party/emoji_catalog_generation.md` and Unicode License v3 notice is included in `third_party/licenses/unicode-license-v3.txt`.
- Offline atlas map mode visibly credits Natural Earth and GeoNames in map attribution when atlas layers are active.
- OSM tile policy requirements are documented and runtime uses `https://tile.openstreetmap.org/{z}/{x}/{y}.png` with visible OpenStreetMap attribution.
- No hardcoded channel PSKs, shared secrets, tokens, or credentials remain in source or tests.
- No known default hotspot password is shipped; deploy scripts require explicit password input.
- Python dependency versions are pinned in `requirements.txt` / `requirements-dev.txt`.
- Python dependency license inventory is generated at `THIRD_PARTY_PYTHON_DEPENDENCIES.md`.
- `meshtastic` GPL-3.0-only metadata has been reviewed by maintainers before final root-license selection.
- Zork rights statement retains the MITDDC qualifier: "to the extent MIT holds rights".
- Colossal Cave Adventure data remains absent from the repository.
- CARTO/cartocdn remains absent unless explicitly relicensed, documented, and opt-in.
- Secret scan completed (for example `gitleaks` and/or `trufflehog`).
- `python -m pytest -q` passes on the release candidate commit.

## Recommended

- Add release tags once the first public cut is ready.
- Decide whether GitHub Issues and Discussions should be enabled.
- Add screenshots only after checking they do not expose node IDs, locations, private channel names, PSKs, or LAN details.
