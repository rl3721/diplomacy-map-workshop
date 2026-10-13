"""Generate ten unclassified groups of five cleaned-terrain maps, without provinces."""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import random

from generator import Config, Grid, clean_terrain, components, elevation, write_terrain_svg
from profiles import targets_for


def group_parameters(group, broad_scale=.36, fine_scale=.045, smooth=.1, rough=.7):
    if not 1 <= group <= 10:
        raise ValueError('Group must be between 1 and 10')
    if not (.01 <= fine_scale <= broad_scale <= 2 and 0 <= smooth <= rough <= 1):
        raise ValueError('Require .01 <= fine_scale <= broad_scale <= 2 and 0 <= smooth <= rough <= 1')
    t = (group - 1) / 9
    return {'landmass_scale': broad_scale * (fine_scale / broad_scale) ** t,
            'roughness': smooth + (rough - smooth) * t}


def generate_study(output, seed=20261013, base=None, broad_scale=.36, fine_scale=.045,
                   smooth=.1, rough=.7, progress=print):
    base = base or Config()
    base.validate()
    group_parameters(1, broad_scale, fine_scale, smooth, rough)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    seeds = random.Random(seed).sample(range(2 ** 31), 5)
    grid = Grid(base.hex_count, base.aspect_ratio, base.wrap_x)
    baseline = targets_for(base)
    manifest = {'schema_version': 1, 'study_seed': seed, 'sample_seeds': seeds,
                'description': 'Increasing spatial elevation variation: shorter wavelength and more fine-scale noise. '
                               'Land fraction and cleanup thresholds stay fixed. Classification intentionally unset.',
                'province_targets': baseline, 'groups': []}
    sections = []
    for group in range(1, 11):
        settings = group_parameters(group, broad_scale, fine_scale, smooth, rough)
        group_record = {'group': group, 'elevation_parameters': settings, 'maps': []}
        cards = []
        for sample, terrain_seed in enumerate(seeds, 1):
            config = replace(base, seed=terrain_seed, **settings)
            config.validate()
            map_id = f'G{group:02d}-M{sample}'
            relative = Path(f'group-{group:02d}') / f'map-{sample}'
            folder = output / relative
            folder.mkdir(parents=True, exist_ok=True)
            heights, initial, sea_level = elevation(config, grid)
            cleaned, flips = clean_terrain(initial, grid, config)
            write_terrain_svg(folder / '02_cleaned.svg', grid, heights, cleaned, sea_level)
            (folder / 'parameters.json').write_text(json.dumps(asdict(config), indent=2), encoding='utf-8')
            groups = components(cleaned, grid)
            land_sizes = sorted((len(c) for c in groups if cleaned[c[0]]), reverse=True)
            water_sizes = sorted((len(c) for c in groups if not cleaned[c[0]]), reverse=True)
            land_area = sum(cleaned)
            record = {'id': map_id, 'seed': terrain_seed, 'path': relative.as_posix(),
                      'classification': None, 'cleaned_land_fraction': land_area / grid.count,
                      'land_components': land_sizes, 'water_components': water_sizes,
                      'largest_landmass_share': max(land_sizes, default=0) / max(1, land_area),
                      'changed_hex_count': sum(a != b for a, b in zip(initial, cleaned)),
                      'cleanup_flip_operations': flips}
            group_record['maps'].append(record)
            url = relative.as_posix()
            cards.append(f'''<article><h3>{map_id}</h3><a href="{url}/02_cleaned.svg" target="_blank">
<img loading="lazy" src="{url}/02_cleaned.svg" alt="Cleaned terrain {map_id}"></a>
<p>Seed {terrain_seed}<br>Land {record['cleaned_land_fraction']:.1%}; {len(land_sizes)} land components<br>
Largest landmass: {record['largest_landmass_share']:.0%} of land</p>
<a href="{url}/02_cleaned.svg" target="_blank">Full SVG</a> · <a href="{url}/parameters.json">Parameters</a></article>''')
            progress(f'{map_id}: {len(land_sizes)} land components; {record["cleaned_land_fraction"]:.1%} land')
        manifest['groups'].append(group_record)
        sections.append(f'''<section id="group-{group}"><h2>Group {group}</h2>
<p>Feature scale {settings['landmass_scale']:.4f}; roughness {settings['roughness']:.3f}</p>
<div class="maps">{''.join(cards)}</div></section>''')
    nav = ' '.join(f'<a href="#group-{g}">{g}</a>' for g in range(1, 11))
    resolved = base.resolved()
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>Terrain comparison: groups 1–10</title>
<style>body{{font:16px system-ui;background:#edf2f5;color:#18343e;margin:auto;padding:24px;max-width:1800px}}
header,section{{padding:22px;background:white;border-radius:12px;margin-bottom:24px}}p{{line-height:1.6}}
.maps{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px}}
article{{background:#f2f6f8;border-radius:8px;padding:14px}}img{{width:100%;aspect-ratio:1.5;object-fit:contain}}
h3{{margin:0 0 10px}}a{{color:#126b7d}}nav{{display:flex;gap:10px;flex-wrap:wrap}}nav a{{padding:8px 14px;background:#edf2f5;border-radius:6px}}
section{{scroll-margin:20px}}</style><header><h1>Terrain comparison: groups 1–10</h1>
<p>50 cleaned-terrain maps, with no province division. Group 1 has broad, smooth elevation features;
group 10 has finer, rougher features. Both feature scale and roughness change, so this is a visual
exploration rather than a single-variable experiment. The same five random seeds repeat across groups.</p>
<p>Fixed: {base.hex_count:,} hexes, initial land {resolved.land_fraction:.0%}, cleanup thresholds
{base.min_land_component}/{base.min_water_component} hexes, horizontal wrap {base.wrap_x}.
Cleanup can alter the final land fraction and remove fine detail. Multiplying elevation heights alone
would not change ranked land/water classification, so spatial variation is changed instead.</p>
<p>Classifications are deliberately blank. Refer to a group number or a map ID such as <b>G04-M2</b>
when choosing island, peninsula, or continental examples. Province targets remain unchanged
({baseline['province_count']} provinces at the default player settings).</p>
<p><a href="manifest.json">Reproducibility data and terrain statistics</a></p><nav>{nav}</nav></header>
{''.join(sections)}</html>'''
    (output / 'index.html').write_text(page, encoding='utf-8')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('output/terrain-study'))
    parser.add_argument('--seed', type=int, default=20261013)
    parser.add_argument('--hex-count', type=int, default=50000)
    parser.add_argument('--land-fraction', type=float, default=.4)
    parser.add_argument('--cleanup', type=int, default=180)
    parser.add_argument('--broad-scale', type=float, default=.36)
    parser.add_argument('--fine-scale', type=float, default=.045)
    parser.add_argument('--smooth', type=float, default=.1)
    parser.add_argument('--rough', type=float, default=.7)
    args = parser.parse_args()
    try:
        generate_study(args.output, args.seed,
                       Config(hex_count=args.hex_count, land_fraction=args.land_fraction,
                              min_land_component=args.cleanup, min_water_component=args.cleanup),
                       args.broad_scale, args.fine_scale, args.smooth, args.rough)
    except (ValueError, OSError) as error:
        parser.exit(2, f'Error: {error}\n')


if __name__ == '__main__':
    main()
