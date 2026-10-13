[Home](../README.md) | [Documentation index](README.md)

# Scoring and balance evaluation

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
python -m mapgen.generator --province-count 150 --output output/150
python -m mapgen.generator --province-count 300 --weight-shape 0 --weight-global 30 --output output/300
```

Reference graph: [python-diplomacy standard.map](https://raw.githubusercontent.com/diplomacy/diplomacy/master/diplomacy/maps/standard.map),
bundled as `mapgen/data/classic_reference.json` so scoring needs no network connection.
Count distinct playable neighboring provinces, collapse named coasts, exclude Switzerland. Adjacency is
geographical, not army/fleet move legality. The reference has 14 inland, 42 coastal, and 19 sea provinces.

The browser app, legacy desktop editor, and CLI share exactly the same generator. No network requests are made during generation.

## Power assignment heuristic

Hard rules require three starting home centers per regional power, at least one
coastal starting center, and the two-move rule described in [generation](generation.md).
The allocator searches 160 complete assignments. During construction it prefers
separation from already chosen groups and shorter internal routes, with random
variation to explore alternatives.

For power i, neutral access is `A_i = sum(1 / (1 + d(i,n)))` over neutral SCs,
where distance starts at the nearest home center. The final assignment score is
`min(D,4) + min(A_i) - (max(A_i) - min(A_i))`, where D is the smallest distance
between opposing home centers. This rewards separation, the weakest access value,
and lower disparity. It has no minimum acceptable balance threshold.

These soft distances use the combined movement graph, not legal unit-specific
travel. Neutrals may be credited to multiple powers; starting units, contested
expansion, defensibility and likely first-year captures are not modeled. The
hard two-move rule does check army/fleet types separately. Planned improvements
and provisional weights are in the [roadmap](roadmap.md).
