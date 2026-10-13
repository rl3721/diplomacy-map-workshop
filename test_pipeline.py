from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import Workshop, parse_config
from generator import Config, generate
from random_seeds import derive_seeds


class PipelineTests(unittest.TestCase):
    def test_seed_streams_are_independent(self):
        base = derive_seeds(Config(global_seed=42))
        self.assertEqual(base, derive_seeds(Config(global_seed=42)))
        self.assertEqual(len({base.seed, base.division_seed, base.sc_seed}), 3)
        changed = derive_seeds(replace(base, global_seed=43))
        self.assertNotEqual((base.seed, base.division_seed), (changed.seed, changed.division_seed))
        self.assertNotEqual(base.sc_seed, changed.sc_seed)

    def test_rerun_pipeline_reuses_and_replays_upstream(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / ('a'*16)
            config = parse_config({'global_seed': 0, 'players': 1, 'province_count': 12,
                                   'hex_count': 600, 'land_province_fraction': .65,
                                   'min_land_component': 12, 'min_water_component': 12})
            generate(config, source, lambda _: None)
            original = json.loads((source/'map.json').read_text())
            workshop = Workshop(root)
            random_patch = patch('app.secrets.randbelow', return_value=42)
            random_patch.start()
            self.addCleanup(random_patch.stop)
            with patch.object(workshop, 'start', return_value='job') as start:
                workshop.rerun({'global_seed':0, 'hex_count':10000, 'players':7, 'sc_richness':1.2}, source.name, 'sc')
                sc_config, saved, stage = start.call_args.args
                self.assertEqual(sc_config.hex_count,600)
                self.assertEqual(sc_config.players,1)
                self.assertEqual(sc_config.sc_richness,1.2)
                self.assertEqual((sc_config.seed, sc_config.division_seed), (config.seed, config.division_seed))
                self.assertNotEqual(sc_config.sc_seed,config.sc_seed)
            with patch('generator.elevation', side_effect=AssertionError('Terrain reran')), patch('generator.partition', side_effect=AssertionError('Provinces reran')):
                generate(sc_config,Path(root)/'sc',lambda _:None,resume=saved,stage=stage)
            result=json.loads((Path(root)/'sc/map.json').read_text())
            for key in ('elevations','initial_land','cleaned_land','province_ids','high_oceans','impassable'):
                self.assertEqual(original[key],result[key])
            generate(sc_config,Path(root)/'replay',lambda _:None)
            replay=json.loads((Path(root)/'replay/map.json').read_text())
            for key in ('province_ids','elevations','supply_centers'):
                self.assertEqual(result[key],replay[key])
            with patch.object(workshop,'start',return_value='job') as start:
                workshop.rerun({'global_seed':0,'hex_count':10000},source.name,'province')
                province_config,saved,stage=start.call_args.args
                self.assertEqual(province_config.hex_count,600)
                self.assertEqual(province_config.seed,config.seed)
                self.assertNotEqual(province_config.division_seed,config.division_seed)
                self.assertNotEqual(province_config.sc_seed,config.sc_seed)
            with patch('generator.elevation',side_effect=AssertionError('Terrain reran')):
                generate(province_config,Path(root)/'province',lambda _:None,resume=saved,stage=stage)
            result=json.loads((Path(root)/'province/map.json').read_text())
            self.assertEqual(result['elevations'],original['elevations'])
            self.assertEqual(result['cleaned_land'],original['cleaned_land'])
            self.assertNotEqual(result['province_ids'],original['province_ids'])
            with patch.object(workshop,'start',return_value='job') as start:
                workshop.rerun({'global_seed':0},source.name,'terrain')
                terrain_config,saved,stage=start.call_args.args
                self.assertIsNone(saved)
                for field in ('seed','division_seed','sc_seed'):
                    self.assertNotEqual(getattr(terrain_config,field),getattr(config,field))
            for stage, source_id, values in [('power',source.name,{}),('sc','../outside',{}),('sc',source.name,{'global_seed':2})]:
                with self.assertRaises(ValueError):
                    workshop.rerun(values,source_id,stage)
