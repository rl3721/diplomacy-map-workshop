# Code architecture

[Home](../README.md) | [Documentation index](README.md)

## Repository layout

```text
mapgen/                  Python application and generation package
  data/                  Bundled Classic graph and variant profiles
web/                     Shared HTML/CSS/UI plus the Pyodide browser adapter
tools/                   Static-site build and reproducible research utilities
tests/                   Python regression tests
examples/                Example settings and terrain-selection records
research/                Committed variant statistics; ignored download cache
docs/                    User guides, implementation details, studies and roadmap
  design/                Original UI concept and design notes
.github/workflows/       Automated tests, build and Pages deployment
output/                  Generated maps and studies (ignored)
_site/                   Built static website (ignored)
```

## Python modules

| Module | Responsibility |
|---|---|
| [generator.py](../mapgen/generator.py) | Configuration, hex grid, elevation, cleanup, province growth/repair, SVG export and pipeline orchestration |
| [sphere.py](../mapgen/sphere.py) | Equal-area spherical cells and topology-aware elevation |
| [profiles.py](../mapgen/profiles.py) | Terrain presets and variant-derived province targets |
| [scoring.py](../mapgen/scoring.py), [shapes.py](../mapgen/shapes.py) | Structural graph/shape diagnostics and candidate scoring |
| [high_oceans.py](../mapgen/high_oceans.py), [slot_placement.py](../mapgen/slot_placement.py) | Merged ocean regions, named movement slots and circle placement |
| [impassable.py](../mapgen/impassable.py) | Elevation-ranked impassables and movement validation |
| [supply_centers.py](../mapgen/supply_centers.py) | Fixed-base SC budget and placement scoring |
| [powers.py](../mapgen/powers.py) | Symmetric starting groups, hard rules and assignment heuristic |
| [label_placement.py](../mapgen/label_placement.py) | Labels inside projected region outlines |
| [random_seeds.py](../mapgen/random_seeds.py) | Global-seed derivation and saved stage overrides |
| [workshop_core.py](../mapgen/workshop_core.py) | Shared settings validation, target limits, summaries and rerun preparation |
| [app.py](../mapgen/app.py) | Local HTTP server, background generation jobs and artifact serving |
| [browser_api.py](../mapgen/browser_api.py) | Synchronous worker adapter and in-memory artifact lifecycle |
| [legacy_app.py](../mapgen/legacy_app.py) | Historical Tkinter interface; the web UI is the primary interface |

Imports within the engine use package-relative names. Runtime reference JSON is
loaded relative to `mapgen/data/`, not the caller's working directory.
The package initializer intentionally does not import the engine, keeping CLI
entry points and Pyodide startup free of import-time generation work.

## Execution paths

The local app serves `web/index.html`, `web/style.css` and `web/ui.js` at
localhost. Its `/api/config`, `/api/targets`, `/api/generate`, `/api/rerun`,
`/api/jobs/<id>` and `/api/latest` routes expose configuration and job state.
Jobs run in a background thread and write to `output/app-runs/` by default.

The Pages build injects `web/browser.js` into the same UI. This adapter implements
the local API contract in the tab; these are method calls, not requests to a
generation server. `web/worker.js` loads pinned Pyodide and the packaged engine,
then calls `mapgen.browser_api` in a Web Worker. Progress messages update the UI.
Generated files live in Pyodide's virtual filesystem and become Blob URLs for
previews/downloads. Only the latest successful run is retained for stage reruns.
Cancellation terminates the worker; saved artifacts restore the previous run
when the next worker starts. Refreshing the tab loses the session.

Both paths share configuration and rerun rules in `workshop_core.py`, and both
call the same `generator.generate`. The static build deliberately excludes
the HTTP server, Tkinter app, tests, research cache and generated output folders.

See [generation](generation.md) for algorithms, [outputs](outputs.md) for
artifacts, and [deployment](deployment.md) for publishing.
