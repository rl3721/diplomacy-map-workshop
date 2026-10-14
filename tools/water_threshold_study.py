"""Calibrate water-label thresholds and build a paired, local HTML review gallery."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import copy
import csv
import json
import math
from pathlib import Path
import random
import statistics

from mapgen.generator import Config, Grid, generate, write_svg
from mapgen.names import assign_names
from mapgen.water_names import eligible, kind_from_features

TARGETS = {'strait': [.10, .15, .20, .40, .60, .80], 'gulf': [.35, .50, .65, .80, .90, 1.0]}
METRICS = {'strait': 'width_ratio', 'gulf': 'mouth_depth_ratio'}


def fit_threshold(values, target):
    """Closest attainable pooled rate, respecting ties; lower cutoff wins ties."""
    if not values:
        return None
    counts = Counter(values)
    options = [(0.0, 0)]
    count = 0
    for cutoff, n in sorted(counts.items()):
        count += n
        options.append((cutoff, count))
    cutoff, count = min(options, key=lambda p: (abs(p[1] / len(values) - target), p[0]))
    return {'threshold': cutoff, 'qualified': count, 'eligible': len(values),
            'achieved': count / len(values), 'target': target}


def sample_quantile(values, fraction):
    values = sorted(values)
    position = (len(values)-1)*fraction
    lower, upper = math.floor(position), math.ceil(position)
    return values[lower] + (values[upper]-values[lower])*(position-lower)


def generate_sample(job):
    root, number, seed = job
    folder = Path(root) / 'maps' / f'map-{number:02d}'
    try:
        report = generate(Config(global_seed=seed, hex_count=5000, province_count=99,
                                 terrain_style='peninsula', topology='flat'), folder, lambda _: None)
        return {'number': number, 'seed': seed, 'path': str(folder),
                'score': report['scoring']['total'], 'ok': True}
    except ValueError as exc:
        return {'number': number, 'seed': seed, 'path': str(folder), 'ok': False, 'error': str(exc)}


def region_rows(sample):
    report = json.loads((Path(sample['path']) / 'report.json').read_text(encoding='utf-8'))
    by_id = {p['id']: p for p in report['provinces']}
    rows = []
    for region in report['high_oceans']['regions']:
        province = by_id[region['id']]
        if province['terrain'] != 'water':
            continue
        rows.append(dict(province['water_classification'], map_number=sample['number'],
                         seed=sample['seed'], region_id=region['id'], baseline_name=province['name']))
    return rows


def calibrate(rows, require_wider=True):
    output = {}
    for kind, targets in TARGETS.items():
        pool = [row for row in rows if eligible(row, kind, require_wider)]
        by_map = {}
        for row in pool:
            by_map.setdefault(row['map_number'], []).append(row[METRICS[kind]])
        values = [row[METRICS[kind]] for row in pool]
        presets = []
        for target in targets:
            result = fit_threshold(values, target)
            if result is None:
                presets.append({'target': target, 'threshold': None, 'eligible': 0})
                continue
            per_map = [sample_quantile(v, target) for v in by_map.values()]
            mean_threshold = statistics.mean(per_map)
            result.update(per_map_mean_threshold=mean_threshold,
                          per_map_median_threshold=statistics.median(per_map),
                          mean_threshold_pooled_rate=sum(v <= mean_threshold for v in values) / len(values),
                          mean_per_map_rate=statistics.mean(sum(v <= result['threshold'] for v in vals) / len(vals)
                                                           for vals in by_map.values()),
                          maps_with_eligible=len(by_map))
            result['per_map_threshold_method'] = 'Mean of linearly interpolated per-map empirical quantiles, excluding maps with no eligible candidates'
            result['all_water_rate'] = result['qualified'] / len(rows)
            presets.append(result)
        output[kind] = presets
    return output


def render_sample(sample, rows, calibration, root, exploratory):
    folder = Path(sample['path'])
    report = json.loads((folder / 'report.json').read_text(encoding='utf-8'))
    data = json.loads((folder / 'map.json').read_text(encoding='utf-8'))
    cfg = report['parameters']
    grid = Grid(len(data['province_ids']), cfg['aspect_ratio'], cfg['wrap_x'])
    owners = [p - 1 for p in data['province_ids']]
    base = {row['region_id']: row for row in rows if row['map_number'] == sample['number']}
    power_colors = {p['id']: p['color'] for p in report['powers']['players']}
    variants = {}
    combinations = [('baseline', .65, 1.0, True)]
    for mode, fits, require_wider in [('strict',calibration,True),('exploratory',exploratory,False)]:
        combinations += [(f'{mode}-s{round(s["target"]*100)}-g{round(g["target"]*100)}', s['threshold'], g['threshold'], require_wider)
                         for s in fits['strait'] for g in fits['gulf']
                         if s['threshold'] is not None and g['threshold'] is not None]
    destination = root / 'comparisons' / f'map-{sample["number"]:02d}'
    destination.mkdir(parents=True, exist_ok=True)
    for key, strait, gulf, require_wider in combinations:
        classes = {}
        for pid, features in base.items():
            kind, reason = kind_from_features(features, strait, gulf, require_wider)
            classes[pid] = dict(features, kind=kind, reason=reason)
        provinces, movement = copy.deepcopy(report['provinces']), copy.deepcopy(report['high_oceans'])
        movement['region_of'] = {int(pid): region for pid, region in movement['region_of'].items()}
        assign_names(provinces, movement, cfg['division_seed'], classes)
        palette = {}
        colors = {'strait':'#e5a5ee', 'gulf':'#f4ce78', 'ocean':'#82b8dd', 'sea':'#c3dce8'}
        for p in provinces:
            palette[p['id']-1] = '#dce4d2' if p['terrain'] == 'land' else colors[p['water_kind']]
        file = destination / (key + '.svg')
        write_svg(file, f'Map {sample["number"]}: {key}', grid, owners, palette, True, movement,
                  report['impassable']['province_ids'], report['supply_centers']['province_ids'],
                  {p['id']:p.get('owner') for p in provinces},
                  {p['id']:p['name'] for p in provinces},
                  {p['id']:power_colors[p['core']] for p in provinces if p.get('core') in power_colors})
        classified = [{'region_id':pid, 'name':next(p['name'] for p in provinces if p['id']==pid),
                       'kind':c['kind']} for pid,c in classes.items()]
        counts = dict(Counter(c['kind'] for c in classes.values()))
        variants[key] = {'svg':file.relative_to(root).as_posix(), 'counts':counts,
                         'strait_width_max':strait, 'gulf_mouth_depth_max':gulf,
                         'strait_require_wider':require_wider,
                         'eligible':{kind:sum(eligible(c,kind,require_wider) for c in base.values()) for kind in TARGETS},
                         'regions':classified}
        file.with_suffix('.json').write_text(json.dumps(variants[key],indent=2),encoding='utf-8')
    return {'number':sample['number'], 'seed':sample['seed'], 'variants':variants}


def write_gallery(root, results, rows, calibration, selected, exploratory):
    table = []
    for kind, presets in calibration.items():
        for p in presets:
            if p['threshold'] is None:
                table.append(f'<tr><td>{kind}</td><td>{p["target"]:.0%}</td><td colspan="5">No eligible regions</td></tr>')
            else:
                table.append(f'<tr><td>{kind.title()}</td><td>{p["target"]:.0%}</td><td>{p["threshold"]:.6f}</td>'
                             f'<td>{p["qualified"]}/{p["eligible"]} = {p["achieved"]:.1%}</td>'
                             f'<td>{p["per_map_mean_threshold"]:.6f}</td><td>{p["mean_threshold_pooled_rate"]:.1%}</td>'
                             f'<td>{p["maps_with_eligible"]}</td></tr>')
    links = ' '.join(f'<a href="maps/map-{r["number"]:02d}/index.html">Map {r["number"]}</a>' if r['ok']
                     else f'<span>Map {r["number"]}: failed</span>' for r in results)
    options = ''.join(f'<option value="{i}">Map {m["number"]} — seed {m["seed"]}</option>' for i,m in enumerate(selected))
    extra = ''.join(f'<tr><td>{p["target"]:.0%}</td><td>{p["threshold"]:.6f}</td><td>{p["qualified"]}/{p["eligible"]} = {p["achieved"]:.1%}</td><td>{p["per_map_mean_threshold"]:.6f}</td></tr>'
                    for p in exploratory['strait'] if p['threshold'] is not None)
    strict_count = calibration['strait'][0]['eligible']
    target_options = {kind: ''.join(f'<option{" selected" if round(t*100)==default else ""}>{round(t*100)}</option>'
                                   for t in TARGETS[kind]) for kind, default in [('strait',60),('gulf',90)]}
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Water threshold review</title><style>
body{font:16px system-ui;margin:24px;background:#eef2f5;color:#18343e}section{background:white;padding:20px;margin:20px 0;border-radius:10px}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd5da;padding:8px;text-align:left}label{display:inline-block;margin:10px}
select,button{padding:8px} .pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}img{width:100%;background:white}a{color:#126b7d}
#all a,#all span{display:inline-block;margin:6px}pre{white-space:pre-wrap}.legend span{padding:8px;display:inline-block}
@media(max-width:900px){.pair{grid-template-columns:1fr}table{font-size:12px}}
</style><h1>Water classification threshold review</h1>
<section><p>50 attempted seeds, Peninsula, flat topology, 5,000 cells, 99 source provinces, 7 players. Only labels change between configurations.</p>
<p>Eligible Strait: exactly two significant mouths, at least two banks, both mouths reach wider water. Eligible Gulf: one significant mouth, at least 60% coastline, and wider water beyond it. High oceans are excluded. Each merged geographical water region is counted once, not once per source province or slot.</p>
<p>Cutoffs below are calibrated to pooled eligible regions. The mean of interpolated per-map percentile cutoffs is also reported, but does not in general achieve the requested pooled rate. Ties make some target percentages unattainable exactly. Maps with zero eligible candidates are excluded from per-map averages, never counted as zero-percent successes.</p>
<p>Strait cutoff = estimated channel width / sqrt(mean water-province cell count). Gulf cutoff = mouth boundary contacts / maximum distance from shore (approximately half the interior width). A larger cutoff admits broader channels or openings. Current defaults are 0.65 and 1.0.</p>
<p>This is exploratory calibration on these maps, not an independent validation set. The six comparison maps are deliberately chosen for eligible features; use the all-map data for unbiased sample rates. No application defaults were changed.</p>
<p><a href="summary.json">Full summary</a> · <a href="regions.csv">Region measurements CSV</a> · <a href="manifest.json">Seeds and failures</a></p>
<table><thead><tr><th>Type</th><th>Requested eligible rate</th><th>Pooled cutoff (used)</th><th>Achieved</th><th>Mean per-map cutoff</th><th>Rate using mean cutoff</th><th>Maps with candidates</th></tr></thead><tbody>TABLE</tbody></table></section>
<section><h2>Exploratory Strait eligibility</h2><p>The current checks leave STRICTCOUNT eligible Straits in this sample; small pools cannot represent every target percentage exactly. The additional experiment keeps two mouths and two banks, but disables the wider-water check. It uses a different denominator and is not a default change or a geographical guarantee.</p><table><tr><th>Target</th><th>Width cutoff</th><th>Achieved (broader eligible pool)</th><th>Mean per-map percentile cutoff</th></tr>EXTRA</table></section>
<section><h2>Paired comparison</h2><label>Map <select id="map">OPTIONS</select></label>
<label>Strait eligibility <select id="mode"><option value="strict">Current checks (STRICTCOUNT candidates)</option><option value="exploratory" selected>Exploratory: two mouths + two banks</option></select></label>
<label>Strait target <select id="strait">STRAITOPTIONS</select>%</label>
<label>Gulf target <select id="gulf">GULFOPTIONS</select>%</label>
<div class="legend"><span style="background:#e5a5ee">Strait SOxx</span><span style="background:#f4ce78">Gulf GOxx</span><span style="background:#82b8dd">Ocean xxxO</span><span style="background:#c3dce8">Sea xxxS</span></div>
<p>The percentages refer to the entire eligible sample, not quotas on this individual map. Province IDs in the JSON remain stable when codes change.</p>
<div class="pair"><div><h3>Current defaults (0.65 / 1.0)</h3><a id="base-link" target="_blank"><img id="base" alt="Baseline map"></a><pre id="base-info"></pre></div>
<div><h3>Selected thresholds</h3><a id="new-link" target="_blank"><img id="new" alt="Selected map"></a><pre id="new-info"></pre></div></div></section>
<section id="all"><h2>All generated maps</h2>LINKS</section>
<script>const maps=DATA;
function show(){const map=maps[Number(document.getElementById('map').value)];if(!map)return;
const key=document.getElementById('mode').value+'-s'+document.getElementById('strait').value+'-g'+document.getElementById('gulf').value;
for(const [panel,v] of [['base',map.variants.baseline],['new',map.variants[key]]]){
if(!v){document.getElementById(panel+'-info').textContent='No eligible data for this preset';continue;}
document.getElementById(panel).src=v.svg;document.getElementById(panel+'-link').href=v.svg;
document.getElementById(panel+'-info').textContent='Cutoffs: Strait '+v.strait_width_max.toFixed(6)+'; Gulf '+v.gulf_mouth_depth_max.toFixed(6)+'\\n'+
'Eligible: '+JSON.stringify(v.eligible)+'\\nClassified: '+JSON.stringify(v.counts);}}
for(const id of ['map','mode','strait','gulf'])document.getElementById(id).addEventListener('change',show);show();</script></html>'''
    page = page.replace('STRAITOPTIONS',target_options['strait']).replace('GULFOPTIONS',target_options['gulf'])
    page = page.replace('TABLE',''.join(table)).replace('EXTRA',extra).replace('OPTIONS',options).replace('LINKS',links).replace('STRICTCOUNT',str(strict_count)).replace('DATA',json.dumps(selected))
    page = page.replace('50 attempted seeds',f'{len(results)} attempted seeds')
    (root/'index.html').write_text(page,encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('output/water-threshold-study'))
    parser.add_argument('--seed',type=int,default=20261014)
    parser.add_argument('--count',type=int,default=50)
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--resume',action='store_true')
    args = parser.parse_args()
    if not 1 <= args.count <= 50:
        parser.error('count must be between 1 and 50')
    root = args.output.resolve()
    root.mkdir(parents=True,exist_ok=True)
    seeds = random.Random(args.seed).sample(range(2**31),args.count)
    results, jobs = [], []
    for number,seed in enumerate(seeds,1):
        folder=root/'maps'/f'map-{number:02d}'
        if args.resume and (folder/'report.json').exists():
            report=json.loads((folder/'report.json').read_text(encoding='utf-8'))
            if report['parameters']['global_seed'] != seed:
                raise ValueError('Resume seed mismatch')
            results.append({'number':number,'seed':seed,'path':str(folder),'ok':True,'score':report['scoring']['total']})
        else:
            jobs.append((str(root),number,seed))
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(generate_sample,job) for job in jobs]
        for future in as_completed(futures):
            result=future.result()
            results.append(result)
            print(f'{len(results)}/{args.count}: map {result["number"]} '+('complete' if result['ok'] else result['error']),flush=True)
    results.sort(key=lambda r:r['number'])
    (root/'manifest.json').write_text(json.dumps({'study_seed':args.seed,'maps':results},indent=2),encoding='utf-8')
    rows=[row for sample in results if sample['ok'] for row in region_rows(sample)]
    calibration=calibrate(rows)
    exploratory=calibrate(rows,require_wider=False)
    summary={'study_seed':args.seed, 'attempted':args.count,'successful':sum(r['ok'] for r in results),'water_regions':len(rows),
             'high_oceans':sum(r['high_ocean'] for r in rows),'calibration':calibration,
             'baseline_counts':dict(Counter(r['kind'] for r in rows))}
    summary['exploratory_calibration']=exploratory
    (root/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    if rows:
        with (root/'regions.csv').open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0])+['eligible_strait','eligible_gulf'])
            writer.writeheader()
            writer.writerows(dict(row,eligible_strait=eligible(row,'strait'),eligible_gulf=eligible(row,'gulf')) for row in rows)
    counts={r['number']:{kind:sum(eligible(row,kind,False) and row[METRICS[kind]] <= (exploratory[kind][-1]['threshold'] or 0)
                               for row in rows if row['map_number']==r['number'])
                         for kind in TARGETS} for r in results if r['ok']}
    # Alternate feature-rich Strait and Gulf maps to expose both classifications.
    strict_candidates=[row for row in rows if eligible(row,'strait')]
    chosen=[min(strict_candidates,key=lambda r:r['width_ratio'])['map_number']] if strict_candidates else []
    for i in range(min(6,len(counts))-len(chosen)):
        kind='strait' if i%2==0 else 'gulf'
        available=[n for n in counts if n not in chosen]
        chosen.append(max(available,key=lambda n:(counts[n][kind],sum(counts[n].values()),-n)))
    if args.resume and (root/'comparisons.json').exists():
        previous=json.loads((root/'comparisons.json').read_text(encoding='utf-8'))
        retained=[m['number'] for m in previous if m['number'] in counts]
        if retained:
            chosen=retained
    selected=[]
    for n in chosen:
        selected.append(render_sample(next(r for r in results if r['number']==n),rows,calibration,root,exploratory))
        print(f'Rendered comparison map {n}: {len(selected)}/{len(chosen)}',flush=True)
    (root/'comparisons.json').write_text(json.dumps(selected,indent=2),encoding='utf-8')
    write_gallery(root,results,rows,calibration,selected,exploratory)
    print(json.dumps(summary,indent=2),flush=True)
    print('Gallery: '+str(root/'index.html'),flush=True)


if __name__ == '__main__':
    main()
