[Home](../README.md) | [Documentation index](README.md)

# Generated artifacts and data format

## Outputs

| File | Contents |
|---|---|
| `01_elevation.svg` | Initial terrain; elevation shades within land and water |
| `02_cleaned.svg` | Terrain after undersized connected regions are flipped |
| `03_provinces.svg` | Terrain-colored province outlines and numeric IDs |
| `04_powers.svg` | Power-colored starting centers and neutral land |
| `index.html` | Browser preview of all generated SVG stages |
| `parameters.json` | Exact generation parameters |
| `report.json` | Sizes, target sizes, degree distributions, adjacency and diagnostic score |
| `map.json` | Full hex elevations, initial/cleaned terrain, province IDs and graph |

SVG files contain vector paths, no embedded raster images. Coordinates retain hex geometry.
These SVGs are standalone visuals, **not** DiplomacyGM's game-import schema.
Provinces display four-letter codes; merged oceans display code-plus-slot labels.
Supply-center circles use a common size per map. See [province names](province-names.md).
Numeric IDs remain machine identifiers; province `name` and movement
`display_name`/`neighbor_display_names` fields provide the label mapping.
Land is green and water blue. Initial elevation remains available in map.json; cleanup changes terrain
classification, not the stored height. Reclassified cells use their new terrain's color ramp.

The browser demo offers downloads backed by the current tab; local runs write
these artifacts into a run folder. `map.json` currently uses schema version 10.
It includes source province IDs, elevation and terrain arrays, high-ocean named
locations, impassable provinces, SC budgets/IDs, power ownership and cores, and
pipeline metadata with actual stage seeds. `report.json` adds diagnostics and
requested/resolved parameters. See [generation](generation.md) for field semantics.
