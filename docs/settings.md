[Home](../README.md) | [Documentation index](README.md)

# Settings and advanced controls

## Normal workflow

The defaults are seven players, Peninsula terrain, 5,000 cells, 99 provinces,
75% land provinces, 12 province iterations, and SC richness 1.0. The ordinary
SC budget is 36; symmetric allocation requests three home SCs per player.

Hover or keyboard-focus underlined parameter labels for explanations. Escape
dismisses a note. Terrain, Provinces and Powers are separate preview tabs;
Terrain shows cleaned elevation. The raw elevation SVG is still exported for
diagnostics. Fit, zoom and scrolling control the preview; Download SVG saves
the displayed stage. Details provides statistics and JSON downloads.

Local refresh restores the most recent successful map from disk. The public
browser demo holds only the current tab's session, so refresh clears it.

## Terrain controls

| UI control | Parameter | Effect |
|---|---|---|
| Preset | `terrain_style` | Continental, Peninsula, Islands or Custom; affects elevation, not the province-reference profile |
| Land coverage | `land_fraction` | Initial fraction of cells classified as land; cleanup can change the final fraction |
| Feature scale | `landmass_scale` | Larger values create broader elevation features |
| Elevation detail | `roughness` | Higher values add stronger fine-scale variation |
| Map topology | `topology` | Flat, horizontal wrap or sphere; rectangular display in all cases |

Dragging a terrain slider selects Custom while preserving the other values.
Choosing a named preset resets all three terrain sliders. Terrain preset
selection is documented in the [research notes](research.md).

Advanced terrain contains hex resolution, aspect ratio, and minimum land/water
area percentages. Cleanup defaults to 3.6% per terrain type: 180 cells at
resolution 5,000, 1,800 at 50,000, or 18 at 500, rounded up. The physical scale
is comparable across resolutions; coastlines are not guaranteed identical.
Legacy absolute cleanup values are converted to fractions when loaded in the UI.

## Province controls

| UI control | Parameter | Effect |
|---|---|---|
| Number of players | `players` | Sets the province baseline and requested power count |
| Province count | `province_count`, `size_ratio` | Exact count, normally within 0.5-1.5 times the player-based capacity; manual entries clamp to the range |
| Asymmetric | `asymmetric` | Multiplies capacity by 1.5 before division; SCs scale through the final province count; asymmetric power assignment is not implemented |
| Land province share | `land_province_fraction` | Share of source provinces on land, independent of land area; default 0.75 |
| Landlocked rate | `inland_ratio` | 0.8-1.2 multiplier for desired landlocked provinces among land provinces |
| Connectivity | `connectivity_ratio` | 0.8-1.2 multiplier for the reference neighbor-count distributions; a soft selection target |

At seven players, symmetric capacity is 99 with a count range of 50-148.
Asymmetric capacity is 148.5 before integer rounding, giving 149 provinces at
normal size, range 75-222, and 55 SCs at richness 1.0. Explicit province counts
are already final; the asymmetric factor must not be applied a second time.
Changing player count or mode preserves the current size multiplier.

Advanced provinces contains shape regularity, size flexibility, Iterations
(`candidates`), size variation, compactness, repair passes, impassable enablement
and impassable land share. Shape targets are soft; terrain can impose narrow
regions. Impassables default to the highest-elevation 2% of land provinces,
rounded down, and remain subject to legal movement connectivity.

## Automatic variant reference and target profile

The normal baseline uses Classic (75 provinces / 7 players), Ancient Mediterranean
(79 / 5), and Modern II (141 / 10). Median province density is 14.1 per player,
rounded to 99 at seven players. Each reference contributes equally to category
fractions and conditional neighbor distributions. The reference landlocked share
is approximately 26.6% of land provinces. At 99 provinces and land share 0.75,
the allocation is 74 land and 25 sea, with roughly 20 landlocked land provinces
as a soft target.

The automatic province profile uses the Peninsula reference independently of the
terrain preset. "Peninsula" is this project's design classification, not an
official variant label. Coast adjacency is classified consistently from geometry;
river-coast exceptions can differ from a variant's declared category.
Horizontal wrap and sphere use Imperial II / World War IV for global travel
comparisons, without changing the player-based count or composition baseline.

Profile selection and scoring weights are fixed in the workshop. Research/CLI
configuration retains overrides such as `province_style`, `reference_profile`,
`weight_*` and `*_tolerance`; these are not ordinary UI controls. Their meaning
and limitations are in [scoring](scoring.md), with source data in
[mapgen/data/variant_profiles.json](../mapgen/data/variant_profiles.json).

## Supply centers and powers

SC controls are enablement (`sc_enabled`), richness (`sc_richness`, 0.8-1.2),
coastal preference (`sc_coastal_preference`, 0-2), distribution
(`sc_distribution`, 0-1), and placement iterations (`sc_iterations`, 1-100).
Richness scales the total budget, not the fixed three starting SCs per symmetric
power. Coastal preference is a soft target. Distribution favors nearby centers
at 0 and wider separation at 1. The fixed 5.2 centers/player budget base is not
editable. See [generation logic](generation.md) for formulas and placement rules.

Symmetric powers are assigned after SC placement. Their hard rules and majority
victory threshold are automatic; a failed assignment reports its reason without
discarding the province map. Asymmetric mode currently generates the larger map
and SC budget, then reports power assignment as "To be implemented".

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
global seed requires Generate map. Local runs preserve source files and write
a new output folder. The browser retains only the latest successful result in
memory. Reruns create a new random variation even when the global
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
