"""Build the static GitHub Pages application: python build_site.py."""
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
PYTHON_FILES = ['browser_api.py', 'workshop_core.py', 'generator.py', 'profiles.py',
                'scoring.py', 'shapes.py', 'sphere.py', 'label_placement.py',
                'high_oceans.py', 'slot_placement.py', 'impassable.py',
                'supply_centers.py', 'powers.py', 'random_seeds.py',
                'classic_reference.json', 'variant_profiles.json']


def build(destination=None):
    destination = Path(destination) if destination else ROOT / '_site'
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'python').mkdir(exist_ok=True)
    for name in PYTHON_FILES:
        shutil.copyfile(ROOT / name, destination / 'python' / name)
    (destination / 'python' / 'manifest.json').write_text(json.dumps(PYTHON_FILES), encoding='utf-8')
    for name in ('ui.js', 'style.css'):
        shutil.copyfile(ROOT / 'ui' / name, destination / name)
    for name in ('worker.js', 'browser.js'):
        shutil.copyfile(ROOT / 'web' / name, destination / name)
    html = (ROOT / 'ui' / 'index.html').read_text(encoding='utf-8')
    html = html.replace('href="/style.css"', 'href="./style.css"').replace('src="/ui.js"', 'src="./ui.js"')
    html = html.replace('<script src="./ui.js"', '<script src="./browser.js" defer></script><script src="./ui.js"')
    html = html.replace('<h2 id="random-heading">Random seed</h2>', '<p class="hint">Browser demo: generation runs on your device. Download maps/settings to keep them; refreshing clears this session.</p><h2 id="random-heading">Random seed</h2>')
    html = html.replace('Connecting to Diplomacy Map Workshop', 'Loading browser generator')
    (destination / 'index.html').write_text(html, encoding='utf-8')
    (destination / '.nojekyll').write_text('', encoding='utf-8')
    return destination


if __name__ == '__main__':
    print(f'Static site built in {build()}')
