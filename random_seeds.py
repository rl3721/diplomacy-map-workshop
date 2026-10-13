"""Global-seed defaults with saved random stage overrides for rerun replay."""
from dataclasses import replace
import hashlib


def derive_seeds(config):
    if config.global_seed is None:
        return config  # Compatibility with historical CLI configurations.
    result = {}
    for stage, field in [('terrain', 'seed'), ('province', 'division_seed'), ('sc', 'sc_seed'), ('power', 'power_seed')]:
        override = getattr(config, stage + '_seed_override')
        if override is not None:
            result[field] = override
            continue
        value = f'map-seeds-v1:{config.global_seed}:{stage}'.encode()
        result[field] = int.from_bytes(hashlib.sha256(value).digest()[:4], 'big') & 0x7fffffff
    return replace(config, **result)
