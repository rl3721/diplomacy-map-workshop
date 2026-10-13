"""Generate ten 99-province maps for each of the user-selected terrain presets."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import html
import json
from pathlib import Path
import random

from generator import Config, generate
from profiles import TERRAIN_GROUPS, targets_for


def sample_configs(seed=20261013):
    # Matching seed columns keep the terrain comparison paired. First five
    # seeds reproduce the earlier terrain-only study's selected examples.
    seeds = random.Random(seed).sample(range(2 ** 31), 10)
    return [(style, group, sample, Config(terrain_style=style, province_style='peninsula',
                                        hex_count=50000, min_land_component=180, min_water_component=180,
                                        land_province_fraction=-1,
                                        province_count=99, players=7, size_ratio=1.0,
                                        inland_ratio=1.0, connectivity_ratio=1.0,
                                        seed=terrain_seed, division_seed=42))
            for style, group in TERRAIN_GROUPS.items()
            for sample, terrain_seed in enumerate(seeds, 1)]


def generate_sample(job):
    output, style, group, sample, config = job
    relative = f'{style}/map-{sample:02d}'
    report = generate(config, Path(output) / relative, lambda _: None)
    return {'id': f'G{group:02d}-M{sample:02d}', 'style': style, 'study_group': group,
            'sample': sample, 'path': relative, 'parameters': asdict(config),
            'province_count': report['province_count'], 'score': report['scoring']['total'],
            'categories': report['scoring']['composition']['actual_counts'],
            'shape': report['scoring']['shape'], 'elapsed_seconds': report['elapsed_seconds']}


def write_gallery(output, rows, study_seed):
    sections = []
    for style, group in TERRAIN_GROUPS.items():
        cards = []
        for row in sorted((r for r in rows if r['style'] == style), key=lambda r: r['sample']):
            relative, shape = row['path'], row['shape']
            cards.append(f'''<article><h3>{row['id']}</h3>
<a href="{relative}/03_provinces.svg" target="_blank"><img loading="lazy"
src="{relative}/03_provinces.svg" alt="{html.escape(style)} {row['id']}"></a>
<p>Seed {row['parameters']['seed']} · {row['province_count']} provinces<br>
Score {row['score']:.1f}; mean shape efficiency {shape['mean_perimeter_efficiency']:.2f}<br>
Shape-review flags: {len(shape['flagged_province_ids'])}</p>
<p><a href="{relative}/index.html">Stages and statistics</a> ·
<a href="{relative}/03_provinces.svg">Province SVG</a> ·
<a href="{relative}/02_cleaned.svg">Cleaned terrain</a></p></article>''')
        sections.append(f'<section id="{style}"><h2>{style.capitalize()} — group {group}</h2>'
                        f'<div class="maps">{"".join(cards)}</div></section>')
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>Classified province map study</title>
<style>body{{font:16px system-ui;background:#edf2f5;color:#18343e;max-width:1800px;margin:auto;padding:24px}}
header,section{{background:white;border-radius:12px;padding:24px;margin-bottom:24px}}
.maps{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}}
article{{background:#f2f6f8;padding:14px;border-radius:8px}}img{{width:100%;aspect-ratio:1.5;object-fit:contain}}
p{{line-height:1.6}}a{{color:#126b7d}}h3{{margin-top:0}}nav a{{margin-right:24px}}</style>
<header><h1>Continental, peninsula, and island province maps</h1>
<p>Your classifications: group 4 = continental; group 6 = peninsula; group 8 = islands.
Ten random maps per group. Every map uses 99 provinces, seven-player reference settings,
size/inland/connectivity ratios 1.0, and the same peninsula province-target profile.
Only terrain presets and terrain seeds differ. Each map selects the best of 12 province divisions.</p>
<p>Terrain: 50,000 hexes, initial land 40%, cleanup 180/180 hexes, no wrap.
The first five seed columns match the earlier terrain-only study; five more extend the comparison.
Completed maps: {len(rows)}/30. <a href="manifest.json">Manifest and parameters</a></p>
<nav><a href="#continental">Continental</a><a href="#peninsula">Peninsula</a><a href="#islands">Islands</a></nav>
</header>{''.join(sections)}</html>'''
    (output / 'index.html').write_text(page, encoding='utf-8')
    manifest = {'schema_version': 1, 'study_seed': study_seed, 'classifications': TERRAIN_GROUPS,
                'province_targets': targets_for(Config(province_count=99)),
                'maps': sorted(rows, key=lambda r: (r['study_group'], r['sample']))}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('output'))
    parser.add_argument('--seed', type=int, default=20261013)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error('workers must be between 1 and 8')
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    write_gallery(args.output, rows, args.seed)
    jobs = [(str(args.output.resolve()), *sample) for sample in sample_configs(args.seed)]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(generate_sample, job): job for job in jobs}
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            write_gallery(args.output, rows, args.seed)
            print(f'{len(rows)}/30: {row["id"]} {row["style"]}, score {row["score"]:.1f}', flush=True)


if __name__ == '__main__':
    main()
