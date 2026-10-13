[Home](../README.md) | [Documentation index](README.md)

# Generation logic and gameplay setup

The pipeline is terrain -> cleaned terrain -> province partition -> high oceans and impassables -> supply centers -> powers. The structural map score, SC placement score and power-assignment heuristic assess different things; none establishes gameplay balance.

## Algorithm and limits

1. Build an odd-row-offset hex grid, optionally wrapping left to right.
2. Sum five scales of smooth value noise. Rank elevations to hit initial land coverage exactly to rounding.
3. Repeatedly flip the smallest undersized terrain component. Each flip reduces component count, avoiding
   simultaneous island/lake oscillation. The sole remaining component cannot be flipped into a surrounding
   region and is retained even if the threshold exceeds total map size. Cleanup can change land coverage.
4. Allocate the land/water province budget to components, at least one province each. Infeasible requests
   fail with an explanation, rather than silently changing province count. Local generation retains both intermediate SVGs for diagnosis; the browser
   keeps the previous successful map when a new generation fails. Increase cleanup thresholds, adjust province budgets, or change seed in that case.
5. Sample lognormal size weights **within each component**, reserve one hex per province, normalize and
   round to the component area. Thus geography constrains the overall size distribution.
6. Place dispersed coastal/interior seeds and grow connected regions by competing spatial fronts.
   Priority combines accumulated travel and the added perimeter (6 - 2 * existing contacts), divided
   by sqrt(target area). Small random step costs follow the compactness setting. Crowded regions may
   finish smaller; they do not get unconditional priority to chase an area quota. Boundary repair
   descends a combined energy for size, internal perimeter, and distance from the seed. It preserves
   seed ownership, terrain class, and donor connectivity. Size targets remain soft.
7. Validate exact coverage, province count, connectivity, and terrain homogeneity.
8. Merge high oceans, designate impassables and reject illegal movement graphs.
9. Place supply centers, then assign symmetric powers where feasible.
10. Export vector paths, statistics, power assignments and raw map data.

Size targets are soft. Enclosed or trapped provinces may remain far from their target; report.json exposes
actual sizes and mean absolute log error. Compactness primarily affects growth, and repairs prioritize size.
The highest-scoring iteration is selected; boundary repair itself uses size and shape costs.
The structural score does not establish gameplay balance.

## Spherical maps

In Diplomacy Map Workshop, select **Terrain → Map topology → Sphere**. All three preview stages
remain rectangular. From the command line:

```powershell
python -m mapgen.generator --topology sphere --output output/sphere-default
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

Run `python -m tools.high_ocean_study` for ten Peninsula maps at 5,000 cells,
99 source provinces and 0.2 land province share, seeds 1001–1010.
Open `output/high-ocean-study/index.html` for the inspection gallery.
Generates a hex-based map through elevation, land/water cleanup, and connected province partitioning.
It also places impassable areas, supply centers and symmetric powers. Starting
units and asymmetric power assignment are still planned; see [roadmap](roadmap.md).

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
coastal preference (0-2), distribution (0-1), and placement
iterations (1-100). Starting/neutral budget controls are removed. Historical
sc_starting_per_player and sc_neutral_per_player fields are ignored when loading
old UI or CLI JSON settings. An API request to set sc_base_per_player is rejected.
Centers are placed first; symmetric power assignment then designates starting home centers.

Only passable land is eligible, with at most one center per province. A budget
larger than eligible land produces an explicit error, never a silently reduced
count. Disable placement for province-only generation. Use Supply centers onward
to rerandomize SCs and powers while preserving terrain and province division.
The global seed and actual stage seeds follow the [seed rules](settings.md#global-seed-and-pipeline-reruns).

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

## Symmetric powers and asymmetric capacity

See [roadmap](roadmap.md) for the balance-design and asymmetric-setup roadmap.

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
