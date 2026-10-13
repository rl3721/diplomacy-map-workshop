[Home](../README.md) | [Documentation index](README.md)

# Running locally and from the command line

Run commands from the repository root. Python 3.10+ is supported; no pip dependencies are needed for local generation.

## Run

From this directory:

```powershell
python -m mapgen.app
```

This opens **Diplomacy Map Workshop** at `http://127.0.0.1:8765` in your browser. Generation runs locally
in a background thread; no internet connection or extra Python packages are required. You can also
double-click `Start Map Workshop.cmd` on Windows. Keep the terminal open while using the app.
Use `python -m mapgen.app --port 8766` if the default port is occupied, or `--no-open` to start without
opening a browser. The old Tkinter editor remains available with `python -m mapgen.legacy_app`.

The command-line generator remains available:

```powershell
python -m mapgen.generator --config examples/example.json --output output --open
python -m mapgen.generator --seed 123 --hex-count 50000 --province-count 75 --output output/seed123
python -m mapgen.generator --help
python -m unittest discover -s tests -v
```

Command-line options override JSON parameters. Save separate runs in separate output folders.
The generator replaces its named artifacts in an existing output folder.

Entry points now use Python modules (`python -m mapgen.app`, `python -m mapgen.generator`); the previous root-level scripts have moved. The Windows launcher continues to work.

See [settings](settings.md) for controls and seeds, [development](development.md) for tests, and [deployment](deployment.md) for the browser build.
