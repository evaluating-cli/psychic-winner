# elevation-route

**Terrain route minimiser for two European cities.** Geocodes two place names,
downloads public Web-Mercator terrain tiles, builds a DEM grid, finds a
least-cost path that strongly penalises elevation change, reports route
distance / ascent / descent, and plots the route on a topographic map with
hillshading and contours.

```
cost = step_distance + elev_weight * |change_in_elevation|
```

A high `--elev-weight` makes the route prefer flatter terrain. With the default
weight of `100`, one metre of climbing costs as much as one hundred metres of
walking — so the path happily detours around hills and through passes.

## Features

- **Geocoding** of city/place names via OpenStreetMap Nominatim, or direct
  `lat,lon` coordinates.
- **DEM** assembled from public [Terrarium elevation tiles](https://registry.opendata.aws/terrain-tiles/)
  (Mapzen terrain tiles, hosted on AWS Open Data), cached on disk.
- **A\* least-cost pathfinding** on the grid with an elevation-change penalty.
- **Statistics**: straight-line distance, route distance, total ascent,
  descent, elevation range.
- **Topographic map output**: hillshade, terrain colour ramp, contour lines,
  and the route with start/destination markers.

## Installation

Requires Python 3.9+.

```bash
git clone https://github.com/evaluating-cli/psychic-winner.git
cd psychic-winner
pip install -e ".[dev]"
```

Or, without packaging:

```bash
pip install -r requirements.txt
```

## Quick start

```bash
elevation-route "Paris, France" "Berlin, Germany"
```

Equivalent invocations:

```bash
python -m elevation_route "Paris, France" "Berlin, Germany"
```

The map is written to `route_topomap.png` and the console shows a summary like:

```
Results
-------
Straight-line distance:         877.7 km
Route distance:                 953.2 km
Total ascent:                    4210 m
Total descent:                   4180 m
Total |elevation change|:        8390 m
Elevation range on route:         690 m
```

## Usage

```
elevation-route [-h] [--grid-size N] [--elev-weight W] [--buffer-km KM]
                [--zoom Z] [--output PATH] [--show] [--version]
                city1 city2
```

| Option | Default | Meaning |
| --- | --- | --- |
| `city1`, `city2` | — | Place names, or `lat,lon` coordinates |
| `--grid-size` | `700` | DEM grid resolution (`grid_size × grid_size` samples) |
| `--elev-weight` | `100` | Cost of 1 m of elevation change, in metres of distance |
| `--buffer-km` | auto | Extra margin around the bounding box |
| `--zoom` | auto | Force a terrain-tile zoom level (6–11) |
| `--output` | `route_topomap.png` | Output PNG path |
| `--show` | off | Open an interactive plot window |
| `--version` | — | Print the version and exit |

### Examples

Flatter routes — raise the elevation penalty:

```bash
elevation-route "Paris, France" "Berlin, Germany" --elev-weight 500
```

Near-straight routes — lower it:

```bash
elevation-route "Paris, France" "Berlin, Germany" --elev-weight 1
```

Coordinates instead of names, wider search corridor, custom output:

```bash
elevation-route "48.8566,2.3522" "52.5200,13.4050" \
    --buffer-km 40 --output paris-berlin.png
```

Mountain example — Chamonix to Zermatt, high resolution:

```bash
elevation-route "Chamonix, France" "Zermatt, Switzerland" \
    --grid-size 900 --elev-weight 200 --show
```

## How it works

1. **Geocode.** Both endpoints are resolved with the
   [Nominatim](https://nominatim.org/) search API (two requests per run).
   `"lat,lon"` input skips the network.
2. **Bounding box.** The box around both points is padded by 15 % of the
   straight-line distance (or `--buffer-km`).
3. **Zoom selection.** The highest zoom level (finest terrain) whose tile count
   stays ≤ 300 is chosen — zoom 11 down to 6.
4. **Tiles.** Terrarium PNG tiles (256×256, Web Mercator) are downloaded with 8
   parallel workers into `~/.elevation_route_cache/`. Elevation is decoded as
   `(R * 256 + G + B / 256) − 32768` metres.
5. **DEM.** Tiles are sampled onto a regular `grid_size × grid_size` lon/lat
   grid. Missing samples fall back to 0 m with a warning.
6. **Pathfinding.** A\* on the 8-connected grid with step cost
   `distance + elev_weight · |Δelevation|`, using a local metric projection and
   straight-line distance as the heuristic.
7. **Statistics & map.** Ascent/descent are summed along the path; the plot
   combines a `LightSource` hillshade, the `terrain` colour ramp, contour
   lines, and the red route.

## Caching and network use

- Terrain tiles are cached in `~/.elevation_route_cache/` and never
  re-downloaded. Delete that directory to force a refresh.
- Geocoding and tile downloads need internet access; pathfinding and plotting
  are fully local.
- Please respect the
  [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/)
  (this tool makes at most two lookups per run).

## Limitations

- Tuned for European city pairs; the DEM quality depends on the underlying
  terrain tiles (SRTM-class, ~30 m source data).
- The corridor is the bounding box of the two endpoints — a route that would
  want to leave that box is out of reach (widen it with `--buffer-km`).
- Travel is over pure terrain: no roads, rivers, borders, or land cover.
- Distances use a spherical Earth model (haversine) and a local equirectangular
  projection for cost calculations.

## Development

```bash
pip install -e ".[dev]"
pytest
```

The test suite is fully offline — network calls are stubbed and DEMs are
synthesised.

Project layout:

```
src/elevation_route/
    cli.py          # argparse CLI and orchestration
    geo.py          # haversine, geocoding, slippy-map tile math
    tiles.py        # Terrarium tile download, cache and decoding
    dem.py          # DEM grid assembly and local projection
    pathfinding.py  # A* least-cost search and route statistics
    plotting.py     # hillshaded topographic map rendering
tests/              # offline unit + end-to-end tests
```

## Data credits

- Elevation: [Terrain Tiles](https://registry.opendata.aws/terrain-tiles/)
  (Mapzen / AWS Open Data), derived from USGS SRTM and other public sources.
- Geocoding: [OpenStreetMap Nominatim](https://nominatim.org/), © OpenStreetMap
  contributors, [ODbL](https://www.openstreetmap.org/copyright).

## License

[MIT](LICENSE)
