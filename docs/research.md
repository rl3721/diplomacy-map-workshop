[Home](../README.md) | [Documentation index](README.md)

# Research notes and generation studies

These notes preserve the historical experiments behind the current defaults.
Old measurements are not guarantees for a new generator version. Terrain seeds
and source hashes document the earlier studies; later gameplay stages can change
new outputs. The current default is Peninsula. See [settings](settings.md) and
[generation](generation.md) for current behavior.

## vDiplomacy comparison research

`research/variant_statistics.csv` and `research/variant_statistics.json` contain a six-map comparison
(Classic, Ancient Mediterranean, Modern II, Gobble-Earth, Imperial II, and World War IV).
The JSON includes every normalized province adjacency list, full degree distributions, exact all-source
travel statistics, land/sea graph measurements, source hashes, source caveats, and URLs.
This is a selected sample, not a census or a ranking of game balance.

```powershell
python -m tools.analyze_vdip --download  # Fetch and verify public files at a pinned revision
python -m tools.analyze_vdip             # Recompute offline from the downloaded cache
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

Run `python -m tools.inspect_maps` to generate seven inspection cases under `output/` and a gallery at
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

Run `python -m tools.terrain_sweep` and open `output/terrain-study/index.html`. This produces exactly
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
python -m tools.terrain_sweep --seed 123 --broad-scale 0.4 --fine-scale 0.06 --smooth 0.1 --rough 0.6 --output output/terrain-study-2
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

At the time of this study, the default was island terrain with an independent peninsula province-target profile; the current terrain default is Peninsula.
The classification and hashes of the original fifteen selected terrain examples are saved in
`examples/terrain_selection.json`. This allows verification that the first five terrain samples in each
new group exactly reproduce the earlier study.

Run `python -m tools.classified_study` to generate ten maps per preset and open `output/index.html`.
Every map uses exactly 99 provinces, seven-player settings, size/inland/connectivity ratios of 1.0,
`province_style=peninsula`, division seed 42, and 12 candidate divisions. Terrain seeds are shared
across groups; the first five match the prior study and five more extend it. The original study predates gameplay assignment. Running this tool with the current
generator also uses the current default impassable/SC/power stages; exact historical
outputs require the corresponding historical revision. SVG stages, map data, parameters
and score reports are available for each sample. Use IDs such as `G06-M07` for feedback.

The script uses three worker processes by default (`--workers 1` runs sequentially), writes an
incrementally updated gallery, and does not delete unrelated output. The old output was explicitly
cleared for the user-requested regeneration. Generated files remain git-ignored.


## Stored reference data

- [Variant statistics JSON](../research/variant_statistics.json)
- [Variant statistics CSV](../research/variant_statistics.csv)
- [Runtime variant profiles](../mapgen/data/variant_profiles.json)
- [Terrain selection record](../examples/terrain_selection.json)
