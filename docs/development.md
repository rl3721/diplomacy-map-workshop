# Development and verification

[Home](../README.md) | [Documentation index](README.md)

Work from the repository root with Python 3.10+. Production Python code uses the
standard library; optional browser checks use Playwright from a development
environment. No Python package installation is required for normal local use.

## Entry points

```sh
python -m mapgen.app
python -m mapgen.generator --config examples/example.json --output output/example
python -m mapgen.generator --help
python -m tools.build_site
python -m http.server 8000 --bind 127.0.0.1 --directory _site
```

The old root-level `app.py`, `generator.py` and `build_site.py` scripts have moved.
Use the module commands above; do not run package files directly by path.
The Windows launcher is updated. To import the engine in Python:

```python
from mapgen.generator import Config, generate

generate(Config(global_seed=42), "output/example")
```

The browser uses an explicit runtime manifest in [tools/build_site.py](../tools/build_site.py).
If a runtime module or data file is added, include it there. The worker preserves
package subdirectories when loading files; test with a clean build and a nested
URL such as `http://127.0.0.1:8000/_site/` when serving the repository root.

## Tests

```sh
python -m unittest discover -s tests -q
python -m unittest tests.test_powers tests.test_pipeline -q
python -m unittest tests.test_browser_api tests.test_app -q
node --check web/ui.js
node --check web/browser.js
node --check web/worker.js
```

The full Python suite checks coverage/connectivity, topology, shape repair,
high-ocean slots, impassables, SC budgeting, power rules, seed/reuse semantics,
HTTP validation and browser artifacts. The static-build test verifies packaged
runtime files and relative asset paths. Pure renames should preserve generated
results and all invariants.

Use focused tests while changing an isolated feature. Run the full suite for
pipeline or import changes and before publishing. CI runs it before deployment.
Documentation-only edits need a link/path check rather than map-generation runs.
Study scripts can generate many maps and are not part of routine verification.

For browser-adapter or build changes, also exercise the real Pyodide runtime:
initial load, generation, stage reruns, saved-settings replay, SVG/JSON downloads,
cancellation/recovery, and an independent tab/session. Check the local HTTP UI
if shared assets or API rules changed. Verify desktop and mobile viewports.
The first browser load needs network access to the runtime CDN.

## Research utilities

Run these intentionally; some produce large galleries or use multiple processes:

| Command | Purpose |
|---|---|
| `python -m tools.terrain_sweep` | Paired terrain-only elevation sweep |
| `python -m tools.classified_study` | Ten province maps for each selected terrain preset |
| `python -m tools.high_ocean_study` | Low-land-share maps for inspecting ocean merging |
| `python -m tools.inspect_maps` | Shape and profile inspection gallery |
| `python -m tools.analyze_vdip --download` | Download pinned public variant files and recompute statistics |

The analysis download cache stays under ignored `research/vdip_sources/`.
See [research notes](research.md) for historical parameters and limitations.
