# Random province map generator

Standalone Python 3.10+ application, independent of DiplomacyGM. No pip dependencies.
Generates a hex-based map through elevation, land/water cleanup, and connected province partitioning.
It does not place supply centers, powers, units, or impassable areas.

## Run

From this directory:

```powershell
python app.py
```

The desktop form runs generation in a background thread. Open the preview after completion.
Tkinter ships with standard Windows Python; Linux installations may need their OS tkinter package.
The command-line interface does not require tkinter:

```powershell
python generator.py --config example.json --output output --open
python generator.py --seed 123 --hex-count 50000 --province-count 75 --output output/seed123
python generator.py --help
python -m unittest -v
```

Command-line options override JSON parameters. Save separate runs in separate output folders.
The generator replaces its named artifacts in an existing output folder.

## Player and terrain controls

Default: 7 players, island-like terrain, peninsula province targets, three multipliers at 1.0, and 12 candidate divisions.
`players` sets a map-size baseline only; powers and supply centers are not assigned.

| Control | Meaning |
|---|---|
| `players` | 1 to 100; province count = round(players * baseline density * size_ratio) |
| `size_ratio` | 0.8 to 1.2; default density is 14.1 provinces per player |
| `inland_ratio` | 0.8 to 1.2; multiplies the province-profile inland provinces / land provinces target |
| `connectivity_ratio` | 0.8 to 1.2; multiplies the support of each reference degree distribution |
| `terrain_style` | islands (default), peninsula, continental; elevation only |
| `province_style` | peninsula (default), continental, islands; province-composition targets only |
| `seed` | Terrain seed; coastline stays fixed when division controls change |
| `division_seed` | Independent province-placement seed |
| `candidates` | Best weighted score from 1 to 100 connected divisions; default 12 |
| `reference_profile` | auto/peninsula, classic, world |
| `wrap_x` | Left/right adjacency and periodic terrain; default false |

`land_fraction`, `landmass_scale`, `roughness`, and `land_province_fraction` use -1 for automatic defaults.
Positive `province_count` overrides the players/size formula. Reports retain requested and resolved parameters.
Changing weights can select a different candidate; it does not alter terrain. Seeds reproduce results within this version.

The peninsula baseline uses **Classic (7 players, 75 provinces), Ancient Mediterranean (5, 79),
and Modern II (10, 141)**. Their median provinces/player is 14.1, giving 99 provinces at seven players.
Category fractions and conditional degree distributions give each reference map equal weight.
The baseline inland share is approximately 26.6% of land provinces; approximately 24.7% of all provinces are sea.
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
| `hex_count` | Exact grid cell count (default 50,000, maximum 500,000) |
| `aspect_ratio` | Approximate physical width/height; final row may be partial |
| `seed` | Reproducibility within this generator version |
| `land_fraction` | Initial land hex fraction, rounded to a whole hex |
| `landmass_scale` | Noise wavelength relative to map span; higher gives broader features |
| `roughness` | Relative amplitude of each additional noise octave |
| `min_land_component` | Flip connected islands smaller than this area to water |
| `min_water_component` | Flip connected water bodies smaller than this area to land |
| `province_count` | 0 derives count from players; positive values override the exact count |
| `land_province_fraction` | Requested share of provinces on land, rounded; all-land/water maps override this |
| `size_variation` | Lognormal sigma, 0 gives approximately equal target areas within a component |
| `compactness` | 0 = random frontier preference; 1 = preference for proximity to seed |
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
This version scores each generated map but does not automatically search candidates or optimize boundaries
against the weighted score. It does not promise gameplay balance.

## Weighted, size-adaptive scoring

The desktop form has **Score weights** and **Score tolerances** tabs. JSON and CLI expose the same fields.
Existing parameter files remain compatible. Higher tolerance is more forgiving; higher weight gives a
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

The desktop app and CLI share exactly the same generator. No network requests are made during generation.

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
The default run has no shape-review flags. Province IDs are reassigned when generation changes, so
new province 42 is not necessarily the former province 42. Terrain remains unchanged.

More compact provinces can depart further from their sampled area targets; the size score still reports
that mismatch without discounting the new repair flexibility. Increasing size flexibility permits more
deviation during repair, while increasing shape regularity discourages unnecessary borders. Coastlines
and narrow land/water components can still impose irregular regions; the controls do not promise convex shapes.

## Unclassified terrain study

The default terrain preset is now `islands`: initial land fraction 0.40, feature scale 0.09,
roughness 0.20, and equal horizontal/vertical feature stretch. This is a provisional visual starting
point pending user classification. `province_style=peninsula` independently retains the previous
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
