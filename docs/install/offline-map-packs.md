# Offline And Custom Map Data

Meshyface includes a small bundled offline atlas as a fallback basemap. For
more detail, build or install offline map packs on the dashboard host. Map packs
are local GeoJSON chunks served by the dashboard; the browser does not need
internet access after they are installed.

Use the Console workspace command `mappacks` for a live, mesh-sized build
command. It suggests a center/radius from current node GPS positions and prints
the matching install command for that host.

Common CLI workflow:

```bash
# Preview a regional pack around stored node history.
python scripts/build_map_pack.py --source-dir map_sources --download \
  --from-history --estimate

# Build a custom pack around stored node history.
python scripts/build_map_pack.py --source-dir map_sources --download \
  --from-history --pack-id mymesh --zip mymesh.zip

# Install it into the dashboard's map pack directory.
python scripts/install_map_pack.py mymesh --zip mymesh.zip
```

Regional packs can also use `--region "Minnesota"` or an explicit
`--center LAT,LON --radius-km KM`. Use `--layers` or `--exclude-layers` to keep
the pack small. The peaks layer uses GeoNames country dumps; for remote areas
where country inference is empty, pass `--peaks-countries US` or omit peaks
with `--exclude-layers peaks`.

Installed packs appear in Settings -> Maps. Source downloads and build outputs
use local `map_sources/` and `map_pack_build/` directories, which are ignored by
git.
