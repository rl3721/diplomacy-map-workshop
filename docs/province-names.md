# Province codes and water classification

[Documentation index](README.md)

## Implemented

Provinces have unique uppercase four-letter display names, generated from a
separate deterministic random stream based on the province seed. Naming does
not consume the generation random streams or change layout, SCs or powers.
SC/power reruns preserve names. Province reruns can change them.

Each connected landmass shares one starting letter. Landmasses are found using
the original land-province adjacency graph, including wrap and sphere edges
and land later designated impassable. Islands count as separate landmasses.
The largest landmass by cell count uses A, the next B, and so on; the remaining
three letters are random. More than 26 landmasses reuse prefixes, while full
codes remain unique; `continent_id` distinguishes them. Four-letter namespaces
are finite and exhaustion produces an explicit error.

Water uses geographic classification to select a four-letter pattern:
`xxxO` (Ocean), `xxxS` (Sea), `GOxx` (Gulf), or `SOxx` (Strait).
Classification measurements and reasons are exported as `water_classification`
on water provinces and movement regions. `water_kind` stores the category.
Names remain unique across land and water. A land code can incidentally match
one of the water patterns; terrain/category metadata is authoritative.

A merged high ocean takes its representative province's code; its separate
movement slots are displayed as `ABCD.1`, `ABCD.2`, etc. Merged source provinces
retain their own unique source names in JSON. Numeric province IDs and existing
movement keys remain stable; `name`, `display_name` and `neighbor_display_names`
provide the human-readable mapping without breaking graph references.

Supply-center circles share one radius and outline width
throughout a map, identical in the Province and Power SVGs. The common size is
capped relative to the displayed map and reduced uniformly if needed to fit.
Each SC uses its largest fitting visible fragment, so a tiny fragment at the
projection seam does not shrink every marker. Label fonts can still vary to
fit province geometry. Starting home-core circles are filled with the assigned power color in both
Province and Power views; neutral centers are white circles. Existing `core`
metadata determines the color. Marker sizes are unchanged by ownership.

## Implemented water rules (version 2)

The classifier uses cleaned land/water cells and the final merged geographical
regions. It measures native mesh adjacency, so wrap and polar links work without
using distorted rectangular SVG coordinates. Boundary contact counts approximate
coastline lengths; cell-hop distances approximate widths. These are deliberately
heuristic geographic labels and do not change any movement or capacity rules.

The reference length is `sqrt(mean source-water-province cell count)`. A
multi-source flood from all coastal water cells measures distance from shore.
For each water region, collect adjacent land cells and outside-water cells,
then find connected groups within each set. The outside-water groups are mouth
candidates; discard groups accounting for less than 15% of water exit contacts.
Land groups act as a proxy for separate banks.

A bounded search outside each mouth checks for substantial wider water: at least
15% of typical water-province area (minimum four cells), and shore distance more
than 1.25 times the region's maximum. Search approximately half a typical
water-province area (minimum eight cells). These small cell minima prevent
single-cell noise; low resolutions may still change marginal classifications.

Apply these rules in order:

1. **Merged high ocean -> Ocean** regardless of the other measurements.
2. **Strait (`SOxx`)**: exactly two substantial mouths, at least two separate
   banks, both mouths reach wider water, and estimated channel width
   (`2 * maximum shore distance`) is at most 0.65 times the reference length.
3. **Gulf (`GOxx`)**: one substantial mouth reaching wider water; at least 60%
   of boundary contacts are land; mouth contact count does not exceed maximum
   shore distance (approximately half the estimated interior width).
4. **Ocean (`xxxO`)**: no land boundary, or coastline contact fraction at most
   20% with maximum shore distance at least 0.35 times the reference length.
5. **Sea (`xxxS`)**: everything else, including enclosed lakes and ambiguous
   channels. A lake has zero mouths and cannot qualify as a Gulf.

These thresholds are initial tuning values, not geological definitions. Native
cell measurements scale with resolution, and synthetic Gulf/Strait tests check
two resolutions; discretization and province boundaries can still change labels.
Features spanning multiple ordinary provinces may not be recognized as a whole
bay or channel. Separate-bank detection is a local connectivity approximation,
not a geometric proof that banks face each other. The exported reason/metrics
make these cases inspectable for later refinement.

Classification runs after province division and is unaffected by SC/power
reruns. It uses physical land, including impassables, rather than movement
restrictions. Numeric graph keys stay unchanged; high-ocean slots inherit their
region's Ocean code with a numeric suffix.
