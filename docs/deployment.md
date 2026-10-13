[Home](../README.md) | [Documentation index](README.md)

# Browser hosting and deployment

## Public browser demo

Open **[Diplomacy Map Workshop](https://rl3721.github.io/diplomacy-map-workshop/)**.
No installation or GitHub account is needed. The Python generator runs on your
device through Pyodide in a Web Worker, while GitHub Pages hosts the static files.
The first visit downloads the pinned Pyodide 314.0.7 runtime from jsDelivr;
an internet connection and a modern browser with WebAssembly are required.

Generate maps, rerun stages, inspect Terrain/Provinces/Powers, and download SVGs,
settings, statistics and map JSON. Cancel stops generation while preserving the
previous displayed map; the engine restarts on the next operation. Generation
speed and practical map size depend on the visitor's device. Start with 5,000 cells.
Map data stays in this tab's memory and is not uploaded to a generation server.
Refreshing or closing the tab clears it: download results/settings first.
Each visitor and tab has an independent session. The demo has no shared gallery,
accounts, persistent storage or multiplayer adjudication.

### Build and deploy

```powershell
python -m tools.build_site
python -m http.server 8000 --bind 127.0.0.1 --directory _site
```

Open `http://127.0.0.1:8000/`; opening the HTML directly as a file will not work.
The build copies the browser runtime modules/data from `mapgen/` and UI assets
from `web/` into ignored `_site/`, preserving Python package paths.
Relative asset paths support the GitHub Pages repository subdirectory.
The local `python -m mapgen.app` application remains available and does not need Pyodide.

The `.github/workflows/pages.yml` workflow tests and builds on pushes to `master`,
then publishes the artifact to GitHub Pages. Repository Settings -> Pages ->
Build and deployment must use **GitHub Actions**. The workflow uses the standard
`GITHUB_TOKEN`; no personal token or secrets belong in the site or repository.
Keep `web/worker.js`'s Pyodide version pinned; verify generation and reruns before
updating it. Browser and local execution share `mapgen/workshop_core.py` configuration,
validation and rerun rules.
