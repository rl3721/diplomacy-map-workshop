# Water threshold calibration study — 14 October 2026

[Documentation index](README.md) | [Classification rules](province-names.md)

## Selected defaults

After reviewing this study, the user selected **exploratory Strait 20%**
(width cutoff `1.0421002114378124`, wider-water check disabled) and **Gulf 100%**
(mouth/depth cutoff `8.25`) as application defaults. The results below and the
gallery baseline describe the earlier classifier; references to unchanged
defaults refer to the study phase before this selection.

## Sample and method

Generated **50/50 successful maps** using study seed `20261014`, 50 distinct
global seeds, and the default Peninsula terrain: flat topology, 5,000 cells,
99 provinces, seven players, 12 province iterations. No generation failures were
discarded or replaced. This sample contains **1,105 geographical water regions**,
including 56 merged high oceans. Count a merged region once, not once per source
province or movement slot. Current defaults classified two Straits and three Gulfs.

The experiment changes classification thresholds only; it does not regenerate
geometry for each profile. Application defaults remain unchanged.

Eligibility excludes high oceans and holds the non-width rules fixed:

- Strait: two significant mouths, at least two banks, both mouths reach wider water.
- Gulf: one significant mouth, coastline fraction at least 60%, wider water beyond the mouth.

For each requested percentage, choose the cutoff giving the closest achievable
pooled eligible-region rate. Tied measurements cannot be split; prefer the lower
cutoff when equally close. Also report the mean of per-map interpolated empirical
percentile cutoffs, excluding maps with no eligible candidates. That mean is a
different estimator and generally does not reproduce the requested pooled rate.
Full-precision cutoffs are saved in JSON; rounded values below are for reading.

## Gulf results

There are **123 eligible regions across 45 maps**. The cutoff is mouth boundary
contacts divided by maximum distance from shore (roughly half interior width).
The default is 1.0; higher values allow wider openings.

| Requested | Pooled cutoff used | Actual eligible rate | Mean per-map percentile cutoff |
|---|---:|---:|---:|
| 35% | 2.333333 | 43/123 = 34.96% | 2.977923 |
| 50% | 3.428571 | 61/123 = 49.59% | 3.346667 |
| 65% | 4.142857 | 80/123 = 65.04% | 3.696526 |
| 80% | 4.666667 | 99/123 = 80.49% | 4.078268 |
| 90% | 5.400000 | 111/123 = 90.24% | 4.353296 |
| 100% | 8.250000 | 123/123 = 100.00% | 4.628325 |

The first three presets label 3.89%, 5.52% and 7.24% of **all** geographical water
regions. The higher presets label 8.96%, 10.05% and 11.13% of all water. Even the
100% setting means all eligible Gulf candidates, not all water provinces.
They intentionally loosen the earlier narrow-mouth definition;
manual review should decide whether the resulting shapes deserve Gulf names.

## Strait results under current eligibility

Only **five regions across five maps** pass the non-width rules. Available rates
advance by 20 percentage points. A 10% target is equally close to 0% and 20%; the
conservative fit selects 0%. The 15% and 20% targets both select cutoff
`0.5278615073083401`, giving 1/5 = 20%. These cannot be three meaningfully distinct
Strait presets without changing eligibility or collecting a different sample.

The added higher targets are achievable exactly within this small pool:

| Requested | Pooled cutoff used | Actual eligible rate |
|---|---:|---:|
| 40% | 0.556319 | 2/5 = 40% |
| 60% | 0.732252 | 3/5 = 60% |
| 80% | 1.042100 | 4/5 = 80% |

These are thresholds for only five candidates, not robust estimates for new maps.

## Additional exploratory Strait comparison

To provide useful visual alternatives, a separately labeled experiment keeps
two mouths and at least two banks but **disables the wider-water requirement**.
This expands the denominator to **146 regions across 46 maps**. It is not the
same population as the strict experiment and is not a default change.

The cutoff is estimated channel width divided by
`sqrt(mean source-water-province cell count)`. The default width cutoff is 0.65.

| Requested | Pooled cutoff used | Actual eligible rate | Mean per-map percentile cutoff |
|---|---:|---:|---:|
| 10% | 0.906100 | 15/146 = 10.27% | 1.217042 |
| 15% | 0.921043 | 21/146 = 14.38% | 1.240989 |
| 20% | 1.042100 | 29/146 = 19.86% | 1.264149 |
| 40% | 1.211406 | 58/146 = 39.73% | 1.372739 |
| 60% | 1.473669 | 88/146 = 60.27% | 1.512424 |
| 80% | 1.795763 | 117/146 = 80.14% | 1.693386 |

The first three label 1.36%, 1.90% and 2.62% of all water regions; the higher
presets label 5.25%, 7.96% and 10.59%. Removing the wider-water
check may admit coast-hugging water or features that do not resemble straits;
this is why the gallery provides both eligibility modes for inspection.

## Reviewing the maps

Open `output/water-threshold-study/index.html`. The gallery contains:

- All 50 original maps and their generation reports.
- Six selected comparison maps: 40, 5, 38, 22, 3 and 21.
- Baseline beside any of 36 Strait/Gulf target combinations, for each of two
  eligibility modes: **432 comparison SVGs plus six baseline SVGs**. The higher
  targets reuse the same six review maps for direct comparison with earlier rates.
- Purple Strait regions, gold Gulf regions, blue Oceans and pale-blue Seas,
  with the generated four-letter codes. Click either map for the full SVG.
- Full thresholds and achieved rates, seed manifest, raw region CSV and per-map
  JSON classifications. The geometry and numeric region IDs stay fixed.

The first selected map includes a strict Strait candidate. Other maps were
deliberately selected to show classified Straits/Gulfs under the wider presets;
these six maps are not a random evaluation sample. Population rates above use
all 50 maps, not just the gallery selection. Calibration and visual selection
use the same data; this is exploratory tuning, not independent validation or
evidence that the classifications will occur at these rates on other presets.

After choosing settings, validate on new seeds and on wrapped/spherical maps,
other terrain presets, and other province counts before changing defaults.

## Reproduce

```powershell
python -m tools.water_threshold_study --count 50 --workers 3
```

Use `--resume` to reuse completed base maps and rebuild the analysis/gallery.
`--seed` changes the study seed; `--output` changes the output directory. The
utility caps generation at 50 attempts. Generated maps are ignored by Git;
[the summary](../research/water_threshold_summary.json) is versioned with the
study code. No new generation controls were added to the public UI.
