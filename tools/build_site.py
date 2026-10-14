"""Build the static GitHub Pages application: python -m tools.build_site."""
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PYTHON_FILES = ['mapgen/' + name for name in ['__init__.py', 'browser_api.py', 'workshop_core.py', 'generator.py', 'profiles.py',
                'scoring.py', 'shapes.py', 'sphere.py', 'label_placement.py',
                'high_oceans.py', 'slot_placement.py', 'impassable.py', 'names.py',
                'supply_centers.py', 'powers.py', 'random_seeds.py',
                'data/classic_reference.json', 'data/variant_profiles.json']]


def build(destination=None):
    destination = Path(destination) if destination else ROOT / '_site'
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'python').mkdir(exist_ok=True)
    for name in PYTHON_FILES:
        (destination / 'python' / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination / 'python' / name)
    (destination / 'python' / 'manifest.json').write_text(json.dumps(PYTHON_FILES), encoding='utf-8')
    for name in ('ui.js', 'style.css'):
        shutil.copyfile(ROOT / 'web' / name, destination / name)
    for name in ('worker.js', 'browser.js'):
        shutil.copyfile(ROOT / 'web' / name, destination / name)
    html = (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')
    html = html.replace('href="/style.css"', 'href="./style.css"').replace('src="/ui.js"', 'src="./ui.js"')
    html = html.replace('<script src="./ui.js"', '<script src="./browser.js" defer></script><script src="./ui.js"')
    html = html.replace('<h2 id="random-heading">Random seed</h2>', '<p class="hint">Browser demo: generation runs on your device. Download maps/settings to keep them; refreshing clears this session.</p><h2 id="random-heading">Random seed</h2>')
    html = html.replace('Connecting to Diplomacy Map Workshop', 'Loading browser generator')
    (destination / 'index.html').write_text(html, encoding='utf-8')
    (destination / '.nojekyll').write_text('', encoding='utf-8')
    return destination


if __name__ == '__main__':
    print(f'Static site built in {build()}')
