"""Documented variant baselines and user-adjusted generation targets."""
from collections import Counter
from functools import lru_cache
import json
from pathlib import Path
import statistics


# User classifications of the 2026-10-13 terrain study. The original study used
# 40% land and isotropic features for every group. Province modifiers stay separate.
TERRAIN_GROUPS = {'continental': 4, 'peninsula': 6, 'islands': 8}
STYLES = {}
for name, group in TERRAIN_GROUPS.items():
    t = (group - 1) / 9
    inland_factor, sea_fraction = {'peninsula': (1.0, None), 'continental': (1.8, .22),
                                  'islands': (.3, .4)}[name]
    STYLES[name] = {'land_fraction': .4, 'landmass_scale': .36 * (.045 / .36) ** t,
                    'roughness': .1 + (.7 - .1) * t, 'stretch': (1.0, 1.0),
                    'inland_factor': inland_factor, 'sea_fraction': sea_fraction}


@lru_cache(maxsize=1)
def catalog():
    return {row['key']: row for row in json.loads(Path(__file__).with_name('variant_profiles.json').read_text(encoding='utf-8'))['maps']}


def reference_members(profile):
    keys = {'classic': ('Classic',), 'peninsula': ('Classic', 'AncMed', 'Modern2'),
            'world': ('Imperial2', 'WWIV')}[profile]
    return [catalog()[key] for key in keys]


def profile_name(config):
    return config.reference_profile if config.reference_profile != 'auto' else 'peninsula'


def targets_for(config, province_count=None):
    name = profile_name(config)
    members = reference_members(name)
    density = statistics.median(row['province_count'] / row['players'] for row in members)
    count = province_count or config.province_count or max(1, round(config.players * density * config.size_ratio))
    inland_base = statistics.mean(row['category_counts']['inland'] /
                                  (row['province_count'] - row['category_counts']['sea']) for row in members)
    land_base = statistics.mean(1 - row['category_counts']['sea'] / row['province_count'] for row in members)
    style = STYLES[config.province_style]
    inland_base = min(1.0, inland_base * style['inland_factor'])
    if style['sea_fraction'] is not None:
        land_base = 1 - style['sea_fraction']
    land_share = config.land_province_fraction if config.land_province_fraction >= 0 else land_base
    inland_share = min(1.0, inland_base * config.inland_ratio)
    degree_histograms = {}
    for category in ('inland', 'coastal', 'sea'):
        histogram = Counter()
        for member in members:
            raw = member['degree_histograms'][category]
            for degree, frequency in raw.items():
                histogram[float(degree) * config.connectivity_ratio] += frequency / sum(raw.values()) / len(members)
        degree_histograms[category] = dict(histogram)
    fractions = {'inland': land_share * inland_share,
                 'coastal': land_share * (1 - inland_share), 'sea': 1 - land_share}
    means = {category: sum(k * v for k, v in histogram.items()) for category, histogram in degree_histograms.items()}
    global_profile = 'world' if config.wrap_x else name
    return {'profile': name, 'global_profile': global_profile, 'members': [row['name'] for row in members],
            'sources': [row['source'] for row in members], 'players': config.players,
            'baseline_provinces_per_player': density, 'province_count': count,
            'province_count_override': config.province_count > 0,
            'inland_baseline': inland_base, 'inland_target': inland_share,
            'land_province_fraction': land_share, 'category_fractions': fractions,
            'degree_histograms': degree_histograms, 'degree_means': means,
            'mean_degree_target': sum(means[k] * fractions[k] for k in fractions),
            'province_style': config.province_style,
            'style_note': ('Peninsula reference selection is a design classification of coastal regional maps, not a vDiplomacy category.'
                           if config.province_style == 'peninsula' else
                           'Continental/island inland and sea-share adjustments are designed presets, not fitted variant measurements.')}
