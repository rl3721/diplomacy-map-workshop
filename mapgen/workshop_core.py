"""Shared local/browser workshop configuration and stage-reuse rules."""
from dataclasses import asdict, fields
import json
import math
from pathlib import Path
import re
import secrets

from .generator import Config
from .profiles import STYLES, targets_for
from .scoring import connectivity_policy
from .supply_centers import center_budget
from .random_seeds import derive_seeds

ARTIFACTS = {'01_elevation.svg', '02_cleaned.svg', '03_provinces.svg', '04_powers.svg',
             'parameters.json', 'report.json', 'map.json', 'index.html'}

LOCKED_SETTINGS = {f.name: getattr(Config(), f.name) for f in fields(Config)
                   if f.name.startswith('weight_') or f.name.endswith('_tolerance')
                   or f.name in ('province_style', 'reference_profile')}


def province_limits(players, hex_count, asymmetric=False):
    base = targets_for(Config(players=players))['province_count'] * (1.5 if asymmetric else 1)
    return base, min(hex_count, math.ceil(base * .5)), min(hex_count, math.floor(base * 1.5))


def parse_config(values, random_seeds=True):
    if not isinstance(values, dict):
        raise ValueError('Parameters must be a JSON object')
    values = {key: value for key, value in values.items()
              if key not in ('sc_starting_per_player', 'sc_neutral_per_player')}
    unknown = set(values) - {f.name for f in fields(Config)}
    if unknown:
        raise ValueError('Unknown parameters: ' + ', '.join(sorted(unknown)))
    settings = dict(values)
    settings.update(LOCKED_SETTINGS)
    if settings.get('global_seed') in (None, ''):
        if 'global_seed' in settings:
            for key in ('terrain_seed_override', 'province_seed_override', 'sc_seed_override', 'power_seed_override'):
                settings[key] = None
        # Import old settings using their terrain seed as the new master seed.
        settings['global_seed'] = settings.get('seed') if 'global_seed' not in settings and settings.get('seed') not in (None, '') else (secrets.randbelow(2 ** 31) if random_seeds else 42)
    for name in ('seed', 'division_seed', 'sc_seed', 'power_seed'):
        settings[name] = 42  # Internal values are always derived below.
    config = Config(**settings)
    # Migrate old absolute cleanup settings to fractions in the workshop.
    for kind in ('land', 'water'):
        absolute = getattr(config, f'min_{kind}_component')
        if type(absolute) is int and absolute >= 0 and type(config.hex_count) is int and config.hex_count > 0:
            setattr(config, f'min_{kind}_fraction', min(1., absolute / config.hex_count))
            setattr(config, f'min_{kind}_component', -1)
    if config.land_province_fraction == -1:
        config.land_province_fraction = .75
    if type(config.players) is int and 1 <= config.players <= 100 and type(config.hex_count) is int and config.hex_count > 0:
        if type(config.province_count) is not int:
            raise ValueError('province_count must be an integer')
        base, minimum, maximum = province_limits(config.players, config.hex_count, config.asymmetric)
        if isinstance(config.size_ratio, (int, float)) and not isinstance(config.size_ratio, bool) and .5 <= config.size_ratio <= 1.5:
            requested = config.province_count or math.floor(base * config.size_ratio + .5)
            config.province_count = max(minimum, min(maximum, requested))
    config.validate()
    return derive_seeds(config)


def result_summary(folder, job_id):
    report = json.loads((folder / 'report.json').read_text(encoding='utf-8'))
    if not connectivity_policy(report['provinces'])['legal']:
        raise ValueError('Historical map contains a one-neighbor province; regenerate it under the current rule.')
    parameters = json.loads((folder / 'parameters.json').read_text(encoding='utf-8'))
    if report.get('high_oceans', {}).get('one_neighbor_region_ids'):
        raise ValueError('Map contains a one-neighbor merged region; regenerate it.')
    if not report.get('impassable', {}).get('legal', True):
        raise ValueError('Impassable placement invalidates movement connectivity; regenerate it.')
    return {'id': job_id, 'state': 'complete', 'message': 'Map ready', 'progress': 1,
            'parameters': parameters, 'province_count': report['province_count'],
            'impassable_count': report.get('impassable', {}).get('count', 0),
            'supply_centers': report.get('supply_centers'), 'powers': report.get('powers'),
            'province_names': {p['id']: p.get('name', str(p['id'])) for p in report['provinces']},
            'playable_location_count': report.get('playable_location_count', report['province_count']),
            'categories': report['scoring']['composition']['actual_counts'],
            'scoring': report['scoring'], 'elapsed_seconds': report['elapsed_seconds'],
            'degree': report['degree_statistics']['all'],
            'urls': {name: f'/runs/{job_id}/{name}' for name in ARTIFACTS if (folder / name).is_file()}}


def prepare_rerun(output, values, source_id, stage):
    if stage not in ('terrain', 'province', 'sc', 'power'):
        raise ValueError('Choose terrain, province, sc, or power.')
    if not isinstance(source_id, str) or not re.fullmatch(r'[0-9a-f]{16}', source_id):
        raise ValueError('Select an existing generated map first.')
    source = Path(output) / source_id
    if not (source / 'map.json').is_file():
        raise ValueError('The source map is unavailable. Generate a new map first.')
    saved = json.loads((source / 'parameters.json').read_text(encoding='utf-8'))
    if saved.get('global_seed') is None:
        raise ValueError('Generate a map with a global seed before using stage reruns.')
    if not isinstance(values, dict):
        raise ValueError('Parameters must be an object')
    if values.get('global_seed') not in (None, '', saved['global_seed']):
        raise ValueError('The global seed changed. Use Generate map to apply it to the whole pipeline.')
    terrain_keys = {'terrain_style', 'topology', 'wrap_x', 'hex_count', 'aspect_ratio', 'land_fraction',
                    'landmass_scale', 'roughness', 'min_land_component', 'min_water_component',
                    'min_land_fraction', 'min_water_fraction'}
    seed_keys = {'global_seed', 'seed', 'division_seed', 'sc_seed', 'power_seed',
                 'terrain_seed_override', 'province_seed_override', 'sc_seed_override', 'power_seed_override'}
    allowed = {f.name for f in fields(Config)} - seed_keys
    if stage == 'province':
        allowed -= terrain_keys
    elif stage == 'sc':
        allowed = {k for k in allowed if k.startswith('sc_')}
    elif stage == 'power':
        allowed = set()
    saved.update({k: v for k, v in values.items() if k in allowed})
    current = parse_config(saved)
    stages = [('terrain', 'seed'), ('province', 'division_seed'), ('sc', 'sc_seed'), ('power', 'power_seed')]
    for name, field in stages[['terrain', 'province', 'sc', 'power'].index(stage):]:
        # Uniformly choose another seed, excluding the current one.
        value = secrets.randbelow(2**31 - 1)
        saved[name + '_seed_override'] = value + (value >= getattr(current, field))
    return parse_config(saved), source if stage != 'terrain' else None, stage


def config_payload():
    return {'defaults': asdict(Config()), 'presets': STYLES,
            'targets': targets_for(Config()), 'token': '',
            'province_bases': {p: province_limits(p, 500000)[0] for p in range(1, 101)}}
