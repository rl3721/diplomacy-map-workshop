"""Synchronous worker API. All outputs live in Pyodide's in-memory filesystem."""
import json
from pathlib import Path
import re
import shutil

from generator import generate
from profiles import targets_for
from supply_centers import center_budget
from workshop_core import ARTIFACTS, config_payload, parse_config, prepare_rerun, result_summary

OUTPUT = Path('/workshop/output')


def dispatch(path, values=None, job_id=None, progress=lambda _: None):
    if path == '/api/config':
        return config_payload()
    if path == '/api/targets':
        config = parse_config(values, random_seeds=False)
        return {**targets_for(config), 'supply_center_budget': center_budget(config)}
    if path not in ('/api/generate', '/api/rerun'):
        raise ValueError('Unknown browser operation')
    if not isinstance(job_id, str) or not re.fullmatch(r'[a-f0-9]{16}', job_id):
        raise ValueError('Invalid generation ID')
    if path == '/api/rerun':
        if not isinstance(values, dict):
            raise ValueError('Rerun request must be an object')
        config, resume, stage = prepare_rerun(OUTPUT, values.get('parameters'), values.get('source_id'), values.get('stage'))
    else:
        config, resume, stage = parse_config(values), None, 'terrain'
    folder = OUTPUT / job_id
    try:
        generate(config, folder, progress, resume=resume, stage=stage)
        result = result_summary(folder, job_id)
        files = {name: (folder / name).read_text(encoding='utf-8') for name in sorted(ARTIFACTS)}
    except Exception:
        if folder.is_dir():
            shutil.rmtree(folder)
        raise
    # Only the displayed successful run is needed for subsequent stage reruns.
    for old in OUTPUT.iterdir():
        if old.is_dir() and old != folder and re.fullmatch(r'[a-f0-9]{16}', old.name):
            shutil.rmtree(old)
    return {'result': result, 'files': files}


def request(payload, progress=lambda _: None):
    data = json.loads(payload)
    return json.dumps(dispatch(data['path'], data.get('values'), data.get('job_id'), progress))
