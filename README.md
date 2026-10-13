# Diplomacy Map Workshop

Generate Diplomacy-style maps with adjustable terrain, provinces, supply centers
and starting powers. Preview the result and download SVG maps or JSON data.

**[Open the browser demo](https://rl3721.github.io/diplomacy-map-workshop/)**

No installation or account is needed. Generation runs on your device; the first
visit downloads the Python browser runtime. Download your maps and settings
before refreshing or closing the tab, because results are not stored online.

## Try it

1. Choose a terrain preset and adjust the province settings, or keep the defaults.
2. Click **Generate map** and inspect the Terrain, Provinces and Powers tabs.
3. Use **Rerun** to randomize a stage onward while keeping earlier stages.
4. Download the displayed SVG, or open **Details** for settings, statistics and map data.

This is a proof of concept. Symmetric power assignment is available; asymmetric
mode currently increases map capacity but does not assign powers. Balance is
heuristic, and exports are not yet a complete adjudicator-ready variant package.

## Run locally

With Python 3.10+ installed, run from the repository root:

```sh
python -m mapgen.app
```

No pip packages are required. On Windows, you can also double-click
`Start Map Workshop.cmd`.

## Documentation

- [Getting started locally and CLI usage](docs/getting-started.md)
- [Settings, advanced controls and seeds](docs/settings.md)
- [Generation logic and power rules](docs/generation.md)
- [Scoring and balance limitations](docs/scoring.md)
- [SVG and JSON outputs](docs/outputs.md)
- [Code architecture](docs/architecture.md) and [development/testing](docs/development.md)
- [Browser build and GitHub Pages deployment](docs/deployment.md)
- [Research notes and generation studies](docs/research.md)
- [Future roadmap: better balance and asymmetric powers](docs/roadmap.md)

See the [documentation index](docs/README.md) for the full guide.
