"""Regenerate a small, reproducible map inspection gallery: python inspect_maps.py."""
from dataclasses import replace
import html
import json
from pathlib import Path

from generator import Config, generate


def main():
    output = Path(__file__).parent / 'output'
    samples = [
        ('profile-default', 'Default peninsula', {}),
        ('division-43', 'Same terrain, division seed 43', {'division_seed': 43}),
        ('small', 'Size ratio 0.8', {'size_ratio': .8}),
        ('large', 'Size ratio 1.2', {'size_ratio': 1.2}),
        ('continental', 'Continental', {'terrain_style': 'continental'}),
        ('islands', 'Islands', {'terrain_style': 'islands'}),
        ('wrap', 'Peninsula with horizontal wrap', {'wrap_x': True}),
    ]
    summaries, cards = [], []
    for folder, title, changes in samples:
        report = generate(replace(Config(), **changes), output / folder, lambda text: print(f'{folder}: {text}', flush=True))
        shape = report['scoring']['shape']
        summary = {'folder': folder, 'title': title, 'province_count': report['province_count'],
                   'shape': shape, 'score': report['scoring']['total'],
                   'size_mean_absolute_log_error': report['size_mean_absolute_log_error']}
        summaries.append(summary)
        cards.append(f'''<section><h2>{html.escape(title)}</h2>
<p>{report['province_count']} provinces. Perimeter efficiency: mean {shape['mean_perimeter_efficiency']:.2f},
worst 10% {shape['worst_decile_perimeter_efficiency']:.2f}, minimum {shape['min_perimeter_efficiency']:.2f}.
Review flags: {len(shape['flagged_province_ids'])}. Structural score: {report['scoring']['total']:.1f}.</p>
<p><a href="{folder}/index.html">All stages and shape checks</a> ·
<a href="{folder}/03_provinces.svg">Province SVG</a> · <a href="{folder}/report.json">Statistics</a></p>
<a href="{folder}/03_provinces.svg"><img src="{folder}/03_provinces.svg" alt="{html.escape(title)}"></a></section>''')
    baseline_path = Path(__file__).with_name('shape_baseline.tmp.json')
    comparison = ''
    if baseline_path.exists():
        before = json.loads(baseline_path.read_text())
        after = summaries[0]['shape']
        (output / 'shape-comparison.json').write_text(json.dumps({'before': before, 'after': summaries[0]}, indent=2))
        comparison = f'''<p>Default map before → after: mean perimeter efficiency
{before['mean_efficiency']:.2f} → {after['mean_perimeter_efficiency']:.2f};
worst 10% {before['worst_decile_efficiency']:.2f} → {after['worst_decile_perimeter_efficiency']:.2f};
minimum {before['min_efficiency']:.2f} → {after['min_perimeter_efficiency']:.2f}.
Terrain seed is unchanged; province numbering does not identify the same region across generations.</p>'''
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>Map shape inspection</title>
<style>body{{font:16px system-ui;max-width:1280px;margin:auto;padding:28px;background:#edf2f5;color:#18343e}}
section{{background:white;margin:24px 0;padding:24px;border-radius:12px}}p{{line-height:1.6}}
img{{width:100%;display:block}}a{{color:#126b7d}}</style>
<h1>Map shape inspection</h1><p>Seven fresh maps using shape-aware growth and boundary repair.
Every sample includes elevation, cleaned terrain, province SVGs, parameters, and detailed statistics.
Narrow coastlines can still impose long regions. Review flags are diagnostics, not validity failures.</p>
{comparison}{''.join(cards)}</html>'''
    (output / 'index.html').write_text(page, encoding='utf-8')
    (output / 'inspection-summary.json').write_text(json.dumps(summaries, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
