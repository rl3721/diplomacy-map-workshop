# Diplomacy Map Workshop

Standalone Python 3.10+ application, independent of DiplomacyGM. No pip dependencies.

## Public browser demo

Open **[Diplomacy Map Workshop](https://rl3721.github.io/diplomacy-map-workshop/)**.
No installation or GitHub account is needed. The Python generator runs on your
device through Pyodide in a Web Worker, while GitHub Pages hosts the static files.
The first visit downloads the pinned Pyodide 314.0.7 runtime from jsDelivr;
an internet connection and a modern browser with WebAssembly are required.

Generate maps, rerun stages, inspect Terrain/Provinces/Powers, and download SVGs,
settings, statistics and map JSON. Cancel stops generation while preserving the
previous displayed map; the engine restarts on the next operation. Generation
speed and practical map size depend on the visitor's device. Start with 5,000 cells.
Map data stays in this tab's memory and is not uploaded to a generation server.
Refreshing or closing the tab clears it: download results/settings first.
Each visitor and tab has an independent session. The demo has no shared gallery,
accounts, persistent storage or multiplayer adjudication.

### Build and deploy

```powershell
python build_site.py
python -m http.server 8000 --bind 127.0.0.1 --directory _site
```

Open `http://127.0.0.1:8000/`; opening the HTML directly as a file will not work.
The build copies only the runtime modules/data and UI into ignored `_site/`.
Relative asset paths support the GitHub Pages repository subdirectory.
The local `python app.py` application remains available and does not need Pyodide.

The `.github/workflows/pages.yml` workflow tests and builds on pushes to `master`,
then publishes the artifact to GitHub Pages. Repository Settings -> Pages ->
Build and deployment must use **GitHub Actions**. The workflow uses the standard
`GITHUB_TOKEN`; no personal token or secrets belong in the site or repository.
Keep `web/worker.js`'s Pyodide version pinned; verify generation and reruns before
updating it. Browser and local execution share `workshop_core.py` configuration,
validation and rerun rules.

## High oceans

Connected groups of two or more water provinces that have no land neighbors
automatically become one visible high ocean. The lowest original province ID
names the region; its single-fleet locations are `13.1`, `13.2`, etc. The requested
province count controls the source partition. Slot count is
`min(source province count, ceil(distinct external neighboring regions / 2), 6)`.
The final playable location count can therefore be smaller; it is reported separately.
Zero-capacity high oceans invalidate a candidate.
Each slot connects to every sibling and every external neighboring location,
as in DiplomacyGM's Origin of Storms. Orders must name a specific slot; there is
no automatic vacancy allocation. A single deep-water province stays unchanged.

SVGs remove internal boundaries and show named circles inside the ocean. All slot circles have the same radius within a map. Slots are packed inside
the merged projected outline with separation and border clearance. One radius
is chosen for the whole map, reduced uniformly if needed to fit a narrow ocean;
zoom scales all circles together. Each slot is drawn once, including on wrapped maps. Hidden sea paths duplicate the full ocean footprint for each slot;
SVG metadata records the explicit movement graph. This is a generator SVG,
not a complete DiplomacyGM variant package with all required layers/configuration.

`map.json` schema 10 preserves original `province_ids` and `provinces` for
partition diagnostics. `region_ids` describes merged geography.
`high_oceans.locations` is the authoritative movement graph, with string names,
reciprocal neighbors, region IDs and capacity 1. `high_oceans.regions` describes
geographical connectivity; `high_oceans.oceans` records membership and capacity.
Movement and geographical degree summaries are exported in `report.json`.
The profile score still evaluates the original partition. Both original and
merged geographical dead ends invalidate a candidate; the larger of their
two-neighbor penalties is deducted, avoiding double charging.

Run `python high_ocean_study.py` for ten Peninsula maps at 5,000 cells,
99 source provinces and 0.2 land province share, seeds 1001–1010.
Open `output/high-ocean-study/index.html` for the inspection gallery.
Generates a hex-based map through elevation, land/water cleanup, and connected province partitioning.
It also places impassable areas, supply centers and symmetric powers. Starting
units and asymmetric power assignment are still planned; see [TODO.md](TODO.md).

## Run

From this directory:

```powershell
python app.py
```

This opens **Diplomacy Map Workshop** at `http://127.0.0.1:8765` in your browser. Generation runs locally
in a background thread; no internet connection or extra Python packages are required. You can also
double-click `Start Map Workshop.cmd` on Windows. Keep the terminal open while using the app.
Use `python app.py --port 8766` if the default port is occupied, or `--no-open` to start without
opening a browser. The old Tkinter editor remains available with `python legacy_app.py`.

The command-line generator remains available:

```powershell
python generator.py --config example.json --output output --open
python generator.py --seed 123 --hex-count 50000 --province-count 75 --output output/seed123
python generator.py --help
python -m unittest -v
```

Command-line options override JSON parameters. Save separate runs in separate output folders.
The generator replaces its named artifacts in an existing output folder.

## Player and terrain controls

Default: 7 players, Peninsula terrain, 5,000 cells, automatic regional province targets,
land province share 0.75, and 12 iterations. The workshop initially targets 99 provinces.
`players` sets a map-size baseline only; powers and supply centers are not assigned.

| Control | Meaning |
|---|---|
| `players` | 1 to 100; province count = round(players * baseline density * size_ratio) |
| `size_ratio` | 0.5 to 1.5; workshop displays an exact province-count slider and number box instead |
| `inland_ratio` | 0.8 to 1.2; multiplies the province-profile inland provinces / land provinces target |
| `connectivity_ratio` | 0.8 to 1.2; multiplies the support of each reference degree distribution |
| `terrain_style` | peninsula (default), continental, islands, custom; elevation only |
| `province_style` | auto (default, resolves to peninsula); fixed in the workshop |
| `seed` | Terrain seed; coastline stays fixed when division controls change |
| `division_seed` | Independent province-placement seed |
| `candidates` | Iterations: best weighted score from 1 to 100 connected divisions; default 12 |
| `reference_profile` | auto (fixed in the workshop); CLI retains research overrides |
| `wrap_x` | Left/right adjacency and periodic terrain; default false |
| `topology` | `flat`, `cylinder`, `sphere`, or `auto` (default, reads legacy `wrap_x`) |

`land_fraction`, `landmass_scale`, `roughness`, and `land_province_fraction` use -1 for automatic defaults.
Positive `province_count` overrides the players/size formula. Reports retain requested and resolved parameters.
Changing weights can select a different candidate; it does not alter terrain. Seeds reproduce results within this version.

The peninsula baseline uses **Classic (7 players, 75 provinces), Ancient Mediterranean (5, 79),
and Modern II (10, 141)**. Their median provinces/player is 14.1, giving 99 provinces at seven players.
Category fractions and conditional degree distributions give each reference map equal weight.
The reference inland share is approximately 26.6% of land provinces. The workshop's explicit
land province share is 0.75, overriding the reference's approximately 75.3% land share.
Province seeds are spread along coasts and inland according to that target, followed by connected growth.
Each candidate is scored against the adjusted targets; the highest total wins. These are soft goals, not guarantees.

?Peninsula? is our design classification of these coastal regional maps, not an official variant label.
Their source URLs and pinned revision are bundled in `variant_profiles.json`; raw analysis is in `research/`.
Categories use geometric sea adjacency consistently. Ancient Mediterranean's two river-coast exceptions
are therefore counted as inland here. Continental and island adjustments are designed presets, not
empirical fits to corresponding variant samples. Wrapped global travel comparisons use Imperial II and
World War IV as a world-map heuristic, not an exact cylindrical-topology calibration.

Before the island-like default change, the peninsula seed-42 run yielded **99 provinces: 19 inland, 56 coastal, 24 sea**
versus targets of approximately 20/55/24. Composition scores **96.3/100**. Shape-aware generation improves perimeter efficiency; travel structure and sampled size matching remain imperfect. The score does not establish gameplay balance.
Player scaling preserves fractions and normalizes travel distances; it does not infer a statistically
fitted nonlinear relationship from this small reference sample.

```powershell
python generator.py --players 10 --size-ratio 1.1 --output output/ten-players
python generator.py --division-seed 123 --inland-ratio 0.8 --output output/new-division
python generator.py --terrain-style islands --wrap-x --output output/islands
```

Wrap grids choose a divisor of hex_count near the requested aspect ratio so every row is complete.
An incompatible count produces an explanatory error. SVG edges are the cut in a cylinder, not impassable borders.

## Spherical maps

In Diplomacy Map Workshop, select **Terrain → Map topology → Sphere**. All three preview stages
remain rectangular. From the command line:

```powershell
python generator.py --topology sphere --output output/sphere-default
```

Sphere uses an equal-area latitude-ring mesh with fewer cells near the poles. The exact
requested `hex_count` is preserved (minimum 12), including prime counts; on this topology
the cells are spherical trapezoids and polar triangles, not regular hexagons. Shared
boundaries determine movement. The poles are closed, north does not wrap to south, and
merely touching a pole does not make all polar cells neighbors. Elevation is sampled in
3D on the sphere, so it has no longitude seam or polar discontinuity. Terrain cleanup and
province growth use this same spherical graph.

The rectangular SVG is an equirectangular display: polar areas are visibly stretched.
Left/right edges are a display cut; use exported adjacency to determine movement.
Province numbers use interior positions in the projected outlines, avoiding borders and
holes. Each visible piece of a seam-crossing province repeats its number, with text sized
to fit the available space. Label positioning does not change province geometry or adjacency.
`aspect_ratio` changes only the sphere's display, not terrain or province generation.
Province count, area distribution, and composition targets remain the same. Surface area
is proportional to cell count. Compactness uses surface boundary lengths and a spherical
isoperimetric bound; rectangular image widths/perimeters are not used for scoring.
World-variant travel references remain a provisional heuristic, not a fitted spherical
baseline. Terrain preset names preserve their scale/roughness ordering, but the earlier
flat-map classifications have not been recalibrated for the sphere.

`map.json` schema 3 includes explicit spherical cell neighbors, longitude/latitude centers
in radians, latitude bounds and row counts for reconstruction. Province records include
surface area in steradians and perimeter in radians on a unit sphere. Legacy fields
containing `hex` mean cell counts or shared graph-edge counts for spherical maps.
Explicit `topology` overrides `wrap_x`; old parameter files without it retain their behavior.

## Outputs

| File | Contents |
|---|---|
| `01_elevation.svg` | Initial terrain; elevation shades within land and water |
| `02_cleaned.svg` | Terrain after undersized connected regions are flipped |
| `03_provinces.svg` | Terrain-colored province outlines and numeric IDs |
| `index.html` | Local browser preview of all three maps |
| `parameters.json` | Exact generation parameters |
| `report.json` | Sizes, target sizes, degree distributions, adjacency and diagnostic score |
| `map.json` | Full hex elevations, initial/cleaned terrain, province IDs and graph |

SVG files contain vector paths, no embedded raster images. Coordinates retain hex geometry.
These SVGs are standalone visuals, **not** DiplomacyGM's game-import schema.
Land is green and water blue. Initial elevation remains available in map.json; cleanup changes terrain
classification, not the stored height. Reclassified cells use their new terrain's color ramp.

## Parameters

| Parameter | Meaning |
|---|---|
| `hex_count` | Exact grid cell count (default 5,000, maximum 500,000) |
| `aspect_ratio` | Approximate physical width/height; final row may be partial |
| `seed` | Reproducibility within this generator version |
| `land_fraction` | Initial land hex fraction, rounded to a whole hex |
| `landmass_scale` | Noise wavelength relative to map span; higher gives broader features |
| `roughness` | Relative amplitude of each additional noise octave |
| `min_land_fraction` | Minimum connected land area as a fraction of the whole map; default 0.036 |
| `min_water_fraction` | Minimum connected water area as a fraction of the whole map; default 0.036 |
| `min_land_component` / `min_water_component` | Legacy absolute overrides; -1 (default) uses the relative fractions |
| `province_count` | 0 derives count from players; positive values override the exact count |
| `land_province_fraction` | Requested share of provinces on land, rounded; all-land/water maps override this |
| `size_variation` | Lognormal sigma, 0 gives approximately equal target areas within a component |
| `compactness` | Higher values reduce the small random variation in growth costs |
| `shape_regularity` | 0 to 1; boundary-length and remote-extension penalty (default 0.8) |
| `size_flexibility` | 0 to 1; repair allows target/factor to target * factor, factor = 1 + flexibility (default 0.3) |
| `repair_passes` | Shape/size improvement passes after connected growth (default 12) |

## Algorithm and limits

1. Build an odd-row-offset hex grid, optionally wrapping left to right.
2. Sum five scales of smooth value noise. Rank elevations to hit initial land coverage exactly to rounding.
3. Repeatedly flip the smallest undersized terrain component. Each flip reduces component count, avoiding
   simultaneous island/lake oscillation. The sole remaining component cannot be flipped into a surrounding
   region and is retained even if the threshold exceeds total map size. Cleanup can change land coverage.
4. Allocate the land/water province budget to components, at least one province each. Infeasible requests
   fail with an explanation, rather than silently changing province count. Both intermediate SVGs remain
   available. Increase cleanup thresholds, adjust province budgets, or change seed in that case.
5. Sample lognormal size weights **within each component**, reserve one hex per province, normalize and
   round to the component area. Thus geography constrains the overall size distribution.
6. Place dispersed coastal/interior seeds and grow connected regions by competing spatial fronts.
   Priority combines accumulated travel and the added perimeter (6 - 2 * existing contacts), divided
   by sqrt(target area). Small random step costs follow the compactness setting. Crowded regions may
   finish smaller; they do not get unconditional priority to chase an area quota. Boundary repair
   descends a combined energy for size, internal perimeter, and distance from the seed. It preserves
   seed ownership, terrain class, and donor connectivity. Size targets remain soft.
7. Validate exact coverage, province count, connectivity, and terrain homogeneity. Export paths with shared
   interior hex edges removed, statistics, and raw map data.

Size targets are soft. Enclosed or trapped provinces may remain far from their target; report.json exposes
actual sizes and mean absolute log error. Compactness primarily affects growth, and repairs prioritize size.
The highest-scoring iteration is selected; boundary repair itself uses size and shape costs.
The structural score does not establish gameplay balance.

## Weighted, size-adaptive scoring

Scoring version 4 adds a fixed connectivity policy, applied after the weighted subtotal:

- Any province with exactly **one distinct neighbor** makes the layout illegal and forces
  its final score to zero. Count neighbors across all terrain types, including wrap/polar
  connections; repeated visible seam pieces do not count as extra neighbors.
- Exactly **two neighbors** is legal, with a deduction of `20 * (two-neighbor provinces / total provinces)`
  points, floored at final score zero. For example, 10% two-neighbor provinces costs 2 points.
  This fixed rule applies regardless of scoring weights and scales with province count.
- Illegal iterations are never selected, even if all scores tie at zero. If every iteration
  is illegal, generation fails with an explanatory message, retains terrain intermediates and
  writes `generation_failure.json`; it does not export a final province SVG or map data.
- Successful reports include the weighted subtotal, penalty, affected IDs and rejected iteration
  diagnostics. Structural validity (coverage/connectivity/terrain consistency) is reported separately
  from legality. The special one-province diagnostic case has degree zero, so the degree-one rule
  does not apply to it. Historical maps with degree-one provinces are not restored by the workshop.

High-seas merging and named slots are implemented; see High oceans above.

The workshop fixes scoring weights and tolerances internally. They are not editable controls;
the server also restores these fixed values when settings are imported or posted to the API.
CLI/research tools retain the fields for development. Higher tolerance is more forgiving; higher weight gives a
component more influence. Zero weight disables its contribution. At least one weight must be positive.

| Component | Default weight | Comparison |
|---|---:|---|
| Degree | 40 | Average of inland/coastal/sea degree-distribution similarities |
| Composition | 20 | Inland/coastal/sea proportions versus the adjusted variant profile |
| Global | 20 | Whole-map, land-only, and sea-only graph structure |
| Size | 15 | Actual province areas versus sampled target areas |
| Shape | 5 | Perimeter efficiency versus compact hex regions of the same area |

All components are 0–100. Weights are normalized automatically:
`total = sum(component_score * weight) / sum(weights)`.
For a mismatch D and tolerance T, similarity is `100 * max(0, 1-D/T)`.
Report JSON includes all component scores, weighted contributions, tolerances, intermediate measurements,
reference graph measurements, and warnings. The preview displays a score table. The old
`classic_degree_similarity_score` remains a separate, unadjusted Classic diagnostic; the degree component now uses the selected profile.

### How larger maps are compared

- **Degree:** Wasserstein distance between normalized neighbor-count histograms. A larger map need not
  have more neighbors per province. Missing categories receive zero credit. Tolerance: `degree_tolerance=2`.
- **Composition:** total variation distance (half the sum of absolute fraction differences).
  Tolerance: `composition_tolerance=0.35`. With `reference_profile=classic`, at 150 provinces the comparison targets are 28 inland,
  84 coastal, 38 sea; at 300 they are 56/168/76. Fractional expected counts are retained, not rounded.
  With the Classic profile this preserves classic proportions; it is not a prediction of how coastlines subdivide.
- **Global:** evaluate whole-map, land-only, and sea-only graphs equally. Each receives 50% travel,
  30% fragmentation, and 20% bottleneck score. A missing graph category receives zero credit.
  Travel compares reachable-pair distance distributions after dividing hops by `sqrt(node_count)` for
  that graph; Wasserstein error is divided by the reference normalized mean distance.
  Tolerance: `path_tolerance=0.35`. This square-root rule is an explicit two-dimensional scaling heuristic,
  not an exact invariance theorem. It allows distances to grow as maps get larger without a fixed 75-node target.
  A graph without reachable distinct pairs receives zero travel credit.
  Fragmentation averages the distance between node-weighted component-size-fraction distributions and
  the absolute difference in unreachable-pair fraction. Tolerance: `fragmentation_tolerance=0.25`.
  Bottlenecks average absolute differences in articulation-node fractions and bridge-edge fractions.
  Tolerance: `bottleneck_tolerance=0.15`. Components and bottlenecks are exact. Travel BFS uses all nodes up
  to 128; beyond that, 128 deterministically spaced node IDs are sampled, with this approximation reported.
- **Size:** mean `abs(log(actual_area / target_area))`; scaling the hex resolution leaves this unchanged.
  Tolerance: `size_tolerance=log(1.5)`, approximately 0.405. A factor-of-1.5 mismatch loses all size credit
  when every province has that multiplicative deviation.
- **Shape (score version 3):** raw perimeter efficiency remains
  `min(1, 2*ceil(sqrt(12*area-3)) / perimeter_hex_edges)` for before/after comparisons.
  Scoring discounts coastline/map-edge length to 25% of internal-border length before computing efficiency.
  Each province's error is 70% adjusted perimeter inefficiency, 20% elongation, and 10% avoidable thinness.
  Elongation is `clamp((two_sweep_diameter/sqrt(area) - 3)/3, 0, 1)`; thinness is
  `min(1, thin_hex_fraction/0.05)`. A thin hex has at most two same-province neighbors while at least
  four neighboring hexes have the same terrain type. This avoids punishing terrain-imposed narrow strips.
  Final shape error weights the mean and the worst 10% equally, then uses `shape_tolerance=0.6`.
  Diameter is a lower-bound estimate, not an exact longest shortest path. All traversal respects wrap.
  Single-hex articulation neck severity is also reported (fraction outside the largest piece after
  removing one hex). Review flags mark normalized diameter >4.5, thin fraction >5%, or neck severity >20%.
  Flags are review heuristics, not invalidity rules; natural isthmuses can trigger them.
  These are geometric preferences rather than variant-measured targets. Scores from versions 2 and 3
  should not be compared directly; raw perimeter efficiencies remain comparable.

Exact province count, coverage, connectedness, and terrain homogeneity remain validity requirements;
they cannot be traded for score points. Scores on fewer than 30 provinces carry a small-map warning,
because category proportions and distributions are coarse. Scores are structural diagnostics only.

```powershell
python generator.py --province-count 150 --output output/150
python generator.py --province-count 300 --weight-shape 0 --weight-global 30 --output output/300
```

Reference graph: [python-diplomacy standard.map](https://raw.githubusercontent.com/diplomacy/diplomacy/master/diplomacy/maps/standard.map),
bundled as `classic_reference.json` so scoring needs no network connection.
Count distinct playable neighboring provinces, collapse named coasts, exclude Switzerland. Adjacency is
geographical, not army/fleet move legality. The reference has 14 inland, 42 coastal, and 19 sea provinces.

The browser app, legacy desktop editor, and CLI share exactly the same generator. No network requests are made during generation.

## vDiplomacy comparison research

`research/variant_statistics.csv` and `research/variant_statistics.json` contain a six-map comparison
(Classic, Ancient Mediterranean, Modern II, Gobble-Earth, Imperial II, and World War IV).
The JSON includes every normalized province adjacency list, full degree distributions, exact all-source
travel statistics, land/sea graph measurements, source hashes, source caveats, and URLs.
This is a selected sample, not a census or a ranking of game balance.

```powershell
python research/analyze_vdip.py --download  # Fetch and verify public files at a pinned revision
python research/analyze_vdip.py             # Recompute offline from the downloaded cache
```

Downloaded PHP is parsed as text, never executed. The source cache is ignored by Git; upstream copyright
notices are preserved in downloaded files. File hashes are checked against the pinned Git revision.
Displayed category totals are the variants' declared Land/Coast/Sea types, reconciled to published pages.
Connectivity combines static army/fleet borders into an undirected graph and collapses coast children;
it is not a legal movement graph for a single unit. Dynamic rule-dependent connections are not simulated.
Special river/coast type discrepancies are retained in `category_mismatches`. Imperial II has one army
permission touching a sea-typed province; the union graph retains that connection (also fleet-enabled),
and `source_warnings` records it. The all-source BFS mean is independently recomputed using frontier sets.

Horizontal wrap is now implemented in terrain noise, cleanup, province growth, and adjacency. SVGs show a cut-open cylinder; repeated province labels identify visible pieces of the same province.

## Shape inspection gallery

Run `python inspect_maps.py` to generate seven inspection cases under `output/` and a gallery at
`output/index.html`. Each case contains all three SVG stages, a preview with shape checks, and JSON data.
The cases cover the island-like default, a different division seed on identical terrain, size ratios 0.8/1.2,
continental, peninsula, and horizontal wrap. The script replaces its named files but does not delete other output.

On the earlier peninsula seed-42 shape-comparison run, raw mean perimeter efficiency improved from **0.510 to 0.856**,
worst-decile efficiency from **0.232 to 0.721**, and minimum from **0.180 to 0.675**.
That earlier run had no shape-review flags. Province IDs are reassigned when generation changes, so
new province 42 is not necessarily the former province 42. Terrain remains unchanged.

More compact provinces can depart further from their sampled area targets; the size score still reports
that mismatch without discounting the new repair flexibility. Increasing size flexibility permits more
deviation during repair, while increasing shape regularity discourages unnecessary borders. Coastlines
and narrow land/water components can still impose irregular regions; the controls do not promise convex shapes.

## Unclassified terrain study

The initial provisional island preset used land fraction 0.40, feature scale 0.09, and roughness 0.20.
It has now been replaced by the user-selected group-8 preset described below. `province_style=peninsula` independently retains the previous
99-province default and the same inland, sea, and degree targets. Setting `terrain_style` no longer
changes those province targets. To reproduce older continental/islands target behavior explicitly,
set `province_style` to the corresponding former terrain style.

Run `python terrain_sweep.py` and open `output/terrain-study/index.html`. This produces exactly
10 numbered groups, five maps per group, and only the cleaned-terrain SVG stage. There are no province
divisions, supply centers, powers, or classifications. The same five random seeds are reused across
groups so that each column is a paired comparison. Seed values and full parameters are saved.

Groups increase spatial elevation variation: feature scale decreases geometrically from 0.36 to 0.045,
and octave roughness increases linearly from 0.10 to 0.70. Both parameters vary, so this is a visual
exploration rather than an isolated causal experiment. Initial land coverage stays at 40%, cleanup
thresholds at 180 hexes for land and water, resolution at 50,000 hexes, and wrap is off. Cleanup may
reduce land coverage and remove small features; final fractions and component counts are shown.
Simply increasing elevation amplitude would not change the ranked land/water split.

Use IDs such as `G04-M2` to nominate future island, peninsula, and continental examples. The manifest
records null classifications until those choices are made. The study range and seeds can be adjusted:

```powershell
python terrain_sweep.py --seed 123 --broad-scale 0.4 --fine-scale 0.06 --smooth 0.1 --rough 0.6 --output output/terrain-study-2
```

The study stores `02_cleaned.svg` and `parameters.json` for each map, plus a top-level `manifest.json`
and gallery. Existing province inspection maps are preserved. Generated outputs remain git-ignored.

## Selected terrain presets and 30-map province study

The user classified the terrain study as follows. These settings now define the named terrain
presets in the application; they retain the study's 40% initial land and equal X/Y feature stretch.

| Terrain preset | Original group | Feature scale | Roughness |
|---|---:|---:|---:|
| continental | 4 | 0.180000 | 0.300000 |
| peninsula | 6 | 0.113393 | 0.433333 |
| islands | 8 | 0.071433 | 0.566667 |

The default remains island terrain with the independent peninsula province-target profile.
The classification and hashes of the original fifteen selected terrain examples are saved in
`terrain_selection.json`. This allows verification that the first five terrain samples in each
new group exactly reproduce the earlier study.

Run `python classified_study.py` to generate ten maps per preset and open `output/index.html`.
Every map uses exactly 99 provinces, seven-player settings, size/inland/connectivity ratios of 1.0,
`province_style=peninsula`, division seed 42, and 12 candidate divisions. Terrain seeds are shared
across groups; the first five match the prior study and five more extend it. No gameplay features
(SCs, powers, impassables) are assigned. All three SVG stages, map data, parameters, and score
reports are available for each sample. Use IDs such as `G06-M07` for feedback.

The script uses three worker processes by default (`--workers 1` runs sequentially), writes an
incrementally updated gallery, and does not delete unrelated output. The old output was explicitly
cleared for the user-requested regeneration. Generated files remain git-ignored.

## Diplomacy Map Workshop interface

- **Terrain:** Continental / Peninsula / Islands / Custom buttons, always-visible land coverage,
  feature scale and elevation detail sliders, and topology. Dragging any terrain slider selects Custom
  and preserves the other two values. A named preset resets all three. Advanced contains resolution,
  aspect ratio, relative cleanup percentages and the optional terrain seed.
- **Provinces:** Number of players, Province count, Land province share, Landlocked rate and
  Connectivity are always visible. Province count is an integer slider plus number box, from 0.5 to
  1.5 times the rounded player-based baseline (rounded inward to whole counts). Seven players gives
  base 99 and range 50–148. Manual entries clamp on blur/Enter. Changing players preserves the
  multiplier. Advanced contains shape regularity, size flexibility, Iterations, size variation,
  compactness, repair passes and the optional province seed. Profile/reference selectors and scoring
  controls have been removed; the workshop always uses auto profiles and fixed scoring.
- **Help:** hover or keyboard-focus the underlined parameter labels for detailed notes. Escape
  dismisses a note; notes also work when labels receive focus on touch devices.
- **Preview:** Terrain (cleaned elevation) and Provinces tabs; zoom and fit; scroll to pan a zoomed map;
  download the displayed SVG; open Details for scores, shape-review flags, statistics, exact parameters,
  and full map data. The previous map stays visible if a subsequent generation fails.
- **Supply centers and Powers:** separate reserved panels, visibly marked Coming later. No SC/power
  generation is implied or performed.

Blank seed boxes request fresh random seeds. Enter a whole number to reproduce a run. To reroll
province division while keeping terrain fixed, reuse the shown terrain seed and leave the province
seed blank. The actual seeds are displayed below the preview and included in each run's parameters.
Save settings downloads the current controls; blanks remain random. Download Exact parameters from
Details to save a generated map's actual seeds. Load settings accepts either JSON format and validates
it before replacing controls. Refresh restores the latest successful map and its exact parameters.

Cleanup defaults to **3.6% per terrain type**, equivalent to 180 cells at resolution 5,000,
1,800 at 50,000, or 18 at 500. Effective thresholds round up to whole cells. Percentages remain
constant when resolution changes. This preserves the physical cleanup scale, not identical coastlines:
sampling and grid shape still vary with resolution. Imported absolute thresholds are converted to
percentages at their saved resolution. Raw elevation SVG remains an intermediate output for diagnostics,
but is not a workshop preview tab. Imported scoring/profile overrides are reset to internal defaults;
province counts are clamped to the current player-based range.

The automatic **variant reference** supplies measured baselines from Classic (75 provinces / 7 players),
Ancient Mediterranean (79 / 5), and Modern II (141 / 10). The median province density is 14.1 per player.
Each map contributes equally to the average landlocked fraction and category-specific neighbor
distributions. The automatic **target profile** resolves to the unmodified Peninsula composition
profile, independently of terrain preset or Custom selection. Land province share overrides the
reference land/sea proportion; Landlocked rate multiplies the reference landlocked share among land
provinces; Connectivity scales the reference degree distributions. At 99 provinces and 0.75 land share,
allocation is 74 land / 25 sea, with roughly 20 of the land provinces desired landlocked. Landlocked
and connectivity targets are soft preferences. Horizontal wrap and Sphere use Imperial II / World War IV
only for global travel comparisons; they do not change the province-count baseline or composition.

New maps are saved in unique folders under `output/app-runs/`. The existing 30-map gallery remains
untouched. Set `--output <folder>` to choose a different run directory. One generation runs at a time,
with progress reported in the status bar; controls are disabled during generation. Closing the terminal
stops the server. The server binds only to localhost and serves only UI files and generated artifacts.

The UI uses native HTML/CSS/JavaScript and Python's standard-library HTTP server, preserving the
project's dependency-free runtime. Desktop uses a settings sidebar and map workspace; small screens
stack the preview above the settings. The code-native interface follows the visual concept in
`ui/design/concept.png`; actual maps remain generated SVGs rather than mockup artwork.


## Impassable highlands

Advanced provinces provides an **Impassable highlands** checkbox (on by default)
and **Impassable land share** slider (default 2%, one per 50 land provinces).
The count is `floor(land province count * impassable_ratio)`: 74 land provinces
produce one black zone, 100 produce two, and fewer than 50 produce none.
Turn the checkbox off or set the ratio to zero to disable placement.

Land provinces are ranked by mean elevation across their cells; ties use the
province ID. Selected provinces are filled black and labelled `ID Impassable`
in the province SVG. Terrain previews retain the elevation shading.
`map.json` records each province's `mean_elevation` and `impassable` flag, with
selection details in `impassable`. Physical adjacency remains available for
geographical diagnostics. The authoritative `high_oceans.locations` movement
graph omits impassable locations and every edge to them, even on maps without
high oceans. Region records also expose `traversable_neighbors`.

The original province budget includes black zones. Playable location count is
reported separately. Candidate layouts are rejected if the impassable selection
creates dead ends, disconnects the playable geographical graph, or leaves no
playable region. The greatest two-neighbor penalty across the source, merged,
and passable geographical graphs is applied once. A high ratio can leave no
legal candidate; lower the ratio or change the generation parameters.

CLI examples: `--no-impassable-enabled` disables placement;
`--impassable-ratio 0.04` uses four percent. JSON uses `impassable_enabled`
and `impassable_ratio`.


## Supply-center designation

Supply centers are enabled by default and placed after impassables. Their own
seed and iterations never affect terrain, province division, high oceans, or
impassable selection. The budget is fixed by:

`round_half_up(5.2 * players * province_count_ratio * richness)`

The base **5.2** is an internal constant, not a user setting. Province count ratio
is the actual requested source province count divided by the player-based base
province count at size ratio 1.0. This uses the selected province count even
when an old size_ratio value differs. High-ocean merging and impassable placement
do not reduce this ratio. Round once after multiplying, to the nearest integer
with halves rounded up. Seven players, 99 source provinces (base 99), and
richness 1.0 give 36 centers; richness 1.2 gives 44.

The Supply centers panel offers an enable/disable checkbox, richness (0.8-1.2),
coastal preference (0-2), distribution (0-1), optional SC seed, and placement
iterations (1-100). Starting/neutral budget controls are removed. Historical
sc_starting_per_player and sc_neutral_per_player fields are ignored when loading
old UI or CLI JSON settings. An API request to set sc_base_per_player is rejected.
Centers are placed first; symmetric power assignment then designates starting home centers.

Only passable land is eligible, with at most one center per province. A budget
larger than eligible land produces an explicit error, never a silently reduced
count. Disable placement for province-only generation. Editing SC controls pins
blank map seeds to the displayed map; explicit seed edits are honored. Generate
reruns deterministically rather than using a cached SC-only computation.

Passable land components receive proportional budgets with weighted randomized
rounding, so small islands are not automatically guaranteed a center. Candidate
placements are scored using spacing (40%), regional distribution (30%), coastal
mix (20%), and accessibility (10%). Spacing uses BFS through passable land only.
Sea access is evaluated independently using water-only routes between land
components; this is a heuristic, not a convoy-order simulation or player-balance
test. Distribution 0 favors nearby centers and 1 favors wider separation.
Coastal preference scales the eligible coastal-land share, subject to feasibility.

SC SVG markers are outlined circles with central dots beside province numbers.
SC placement initially leaves centers unassigned. The subsequent symmetric power stage sets owner, home_power and core on its starting centers. map.json schema 10 and report.json export supply_centers, including chosen
IDs, the complete budget formula and factors, seed, component scores, candidate
scores, and regional allocation. The structural map score is unchanged by SC
settings. Symmetric power assignment follows SC placement. Initial armies/fleets and asymmetric power assignment remain unimplemented.


## Global seed and pipeline reruns

The first sidebar control is now **Global seed**. The workshop derives stable,
independent terrain, province, SC and power seeds from that integer and stage names.
A global seed determines the initial stage seeds. Stage reruns instead choose
fresh random seeds for the selected stage and every downstream stage. Earlier
stages keep their saved seeds and generated data.

Leave the global seed blank for a fresh random seed when clicking Generate map.
The actual seed is shown below the map and saved in parameters.json. Save settings
also captures that actual seed when the input is blank. Change the global seed
and use Generate map to create a different random map.

The dropdown beside Generate map selects **Terrain onward**, **Provinces onward**,
**Supply centers onward**, or **Powers**. Click Rerun to recompute:

- Terrain: randomize all stages with current settings.
- Provinces: reuse saved elevation and cleaned terrain, then rebuild provinces,
  high oceans, impassables and supply centers.
- Supply centers: reuse saved terrain and provinces, replace SC designation and rerun powers.
- Powers: preserve terrain, provinces and SC locations; randomize only power assignment.

A rerun keeps the source map's earlier-stage settings; pending changes to those
settings are discarded and the sidebar restores the settings actually used.
To apply them, rerun from their stage or generate the entire map. Changing the
global seed requires Generate map. Source files remain unchanged; each run gets
a new output folder. Reruns create a new random variation even when the global
seed and settings are unchanged. Reruns are available after the first
successful map using a global seed; historical maps need full regeneration first.

The /api/rerun endpoint accepts parameters, source_id and stage (terrain,
province, sc or power). map.json schema 10 includes pipeline stage and actual stage seeds.
Saved settings include hidden terrain_seed_override, province_seed_override and
sc_seed_override and power_seed_override fields. Load those settings and use Generate map to replay a
rerun result; its global seed alone is insufficient. Changing or clearing the
global seed in the UI clears these overrides. Old internal seed fields remain
readable for compatibility. CLI supports
--global-seed. Python callers without a global seed retain historical seed behavior.


## Symmetric powers and asymmetric capacity

See [TODO.md](TODO.md) for the balance-design and asymmetric-setup roadmap.

The Province section's Asymmetric checkbox defaults off. Turning it on multiplies
the player-based province capacity by 1.5, on top of the existing size ratio.
The displayed/explicit province_count remains the final count, rounded to whole
provinces; it is never multiplied a second time. Hex resolution and terrain do
not change. Apply this setting by generating or rerunning from Provinces onward.
SC budgeting divides this final province count by the original symmetric base,
so the capacity increase is included exactly once. At seven players and normal
size/richness: symmetric = 99 provinces / 36 SCs; asymmetric = 149 / 55.

Symmetric powers receive exactly three starting SCs, all owned home cores.
Every power must have at least one coastal starting SC with a water neighbor in
the playable movement graph. Entirely landlocked starting groups are rejected.
Exports record each power's coastal_starting_centers. If there are too few coastal
SCs or no complete valid assignment, the map is preserved with an explanation.
Other SCs remain neutral; no additional precores or starting units are assigned.
Victory is floor(total SCs / 2) + 1. Starting centers need not touch or belong
to a connected landmass. For EACH starting center there must be a single unit
type (army OR fleet) that can reach BOTH other centers in at most two moves.
Different origins may use different types. Paths ignore occupancy and do not
use convoys. Armies use passable land; fleets use water and coastal provinces,
with coastal-to-coastal edges requiring a shared sea neighbor. This is the
generator's unsplit-coast model; split-coast adjudicator export is not provided.
Wrap, sphere, impassables and named high-ocean slots use the saved movement graph.

The allocator searches disjoint valid triples, favoring separation between powers
and comparable nearby neutral access. These preferences are heuristics, not a
claim of gameplay balance. An insufficient SC budget, an immediate starting
victory, or failure to find a full assignment leaves the map intact and reports
why; no partial powers are exported. SCs can be rerun to find another layout.

The Powers preview and 04_powers.svg color each power's home SCs and label them
with P1, P2, etc. Neutral land is gray. map.json/report.json export power IDs,
colors, iscc=3, majority vscc, owner/core fields, and witness routes for the hard
two-move rule. Power-only reruns preserve all previous stages and save a fresh
power seed. In asymmetric mode, the map and SCs generate normally and the Powers
panel says 'Asymmetric power allocation: to be implemented.'
