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

Water currently uses neutral random four-letter codes with no category encoded.
Ocean (`xxxO`), Sea (`xxxS`), Gulf (`GOxx`) and Strait (`SOxx`) classification
is pending user review; none of these patterns is intentionally assigned yet.
A random code may incidentally match a proposed pattern without implying a
classification. The geographical term is **strait**, rather than straight.

A merged high ocean takes its representative province's code; its separate
movement slots are displayed as `ABCD.1`, `ABCD.2`, etc. Merged source provinces
retain their own unique source names in JSON. Numeric province IDs and existing
movement keys remain stable; `name`, `display_name` and `neighbor_display_names`
provide the human-readable mapping without breaking graph references.

Supply-center circles share one outer radius, inner radius and outline width
throughout a map, identical in the Province and Power SVGs. The common size is
capped relative to the displayed map and reduced uniformly if needed to fit.
Each SC uses its largest fitting visible fragment, so a tiny fragment at the
projection seam does not shrink every marker. Label fonts can still vary to
fit province geometry. Ownership remains visible through colors and tooltips.

## Proposed richer water rules

Classify using cleaned terrain and local water geometry, then assign the result
to provinces after division. Raw neighbor counts alone are insufficient: three
small neighboring land provinces may be one short shoreline, while one large
land province may surround an entire bay. Measure shared boundary lengths and
distances in the map's native topology, not rectangular projection distances.

1. **Strait (`SOxx`)**: narrow water with land on opposing sides and two mouths
   leading to wider water. Require low channel width relative to typical water
   province scale, and substantial water reachable beyond both mouths. Test
   water connectivity after blocking the candidate channel as strong supporting
   evidence, but not as the only rule: alternative sea routes can exist.
2. **Gulf (`GOxx`)**: a water indentation mostly surrounded by land, with one
   restricted opening into a larger water body. A starting trial could require
   at least 60% of its measured boundary to be coastline and a mouth width below
   half its interior width. Test the enclosure over nearby water cells, since a
   gulf may span several provinces. An enclosed lake has zero mouths and should
   not qualify as a gulf.
3. **Ocean (`xxxO`)**: extensive open water with low coastal enclosure and high
   interior distance from shore. Include merged high oceans explicitly. Do not
   require contact with a map edge: spheres have no physical edges.
4. **Sea (`xxxS`)**: other water, including broad coastal or partly enclosed
   basins. With only these four categories, enclosed lakes can use Sea as a
   documented fallback, or receive a separate Lake category later.

Use precedence Strait, Gulf, Ocean, Sea, with merged high-ocean regions forced
to Ocean. Scale distance thresholds by the square root of typical water-province
area, so changing hex resolution does not alter classification. Store measured
features and classification reasons, and compare identical terrain at multiple
resolutions before choosing final thresholds. Mixed or ambiguous provinces
should fall back to Sea rather than claim a confident Gulf/Strait label.

The percentages above are proposed tuning values, not implemented rules or
geographic definitions. Validate with synthetic channels, bays, island chains,
enclosed lakes, and features crossing wrap/polar seams.
