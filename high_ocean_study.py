"""Generate the requested ten reproducible 5,000-cell high-ocean previews."""
import html
import json
from pathlib import Path

from generator import Config, generate


def main():
    root = Path('output/high-ocean-study')
    root.mkdir(parents=True, exist_ok=True)
    cards = []
    results = []
    for number in range(1, 11):
        seed = 1000 + number
        destination = root / f'map-{number:02d}'
        report = generate(Config(hex_count=5000, province_count=99,
                                 land_province_fraction=.2, seed=seed, division_seed=seed), destination)
        oceans = report['high_oceans']['oceans']
        results.append({'map': number, 'seed': seed, 'score': report['scoring']['total'],
                        'regions': report['geographical_region_count'],
                        'locations': report['playable_location_count'],
                        'oceans': [{'id': o['id'], 'capacity': o['capacity']} for o in oceans]})
        title = f'Map {number:02d} — seed {seed} — {len(oceans)} high oceans / {report["playable_location_count"]} playable locations'
        cards.append(f'<article><h2>{html.escape(title)}</h2>'
                     f'<a href="map-{number:02d}/03_provinces.svg"><img src="map-{number:02d}/03_provinces.svg" alt="{title}"></a>'
                     f'<p><a href="map-{number:02d}/index.html">Report and terrain</a> · '
                     f'<a href="map-{number:02d}/map.json">Connectivity JSON</a></p></article>')
        print(f'Completed {title}', flush=True)
    (root / 'summary.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    (root / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>High ocean study</title>'
        '<style>body{font:16px system-ui;background:#edf2f5;margin:24px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(480px,1fr));gap:24px}article{background:white;padding:16px;border-radius:12px}img{width:100%}h2{font-size:18px}</style>'
        '<h1>High ocean study</h1><p>5,000 hexes · 99 source provinces · 20% land provinces · Peninsula terrain. '
        'Circles are named, one-fleet slots. All slots in an ocean share its external exits and connect to each other.</p>'
        '<main>' + ''.join(cards) + '</main>', encoding='utf-8')


if __name__ == '__main__':
    main()
