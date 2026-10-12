"""Full isolated regression. Never renders into the approved project."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import wave

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'backend' / 'spatial'), str(ROOT / 'backend' / 'mastering')]
import numpy as np
from pedalboard import load_plugin
from dearvr_adapter import (PLUGIN_PATH, CALIBRATED_DISTANCE_RAW,
    configure_direct_signal, set_pose, interpolate_pose, interpolate_keyframe_value)
from tukana_spatial_composer import build_tukana_scene
from tukana_full_renderer import render_full
from tukana_mastering import master_tukana, sha256_file
from tukana_transient_refinement import refine_tukana

PROJECT = ROOT / 'projects' / 'tukana'
EXPECTED = '9daf544d7e073d8791f6260eed2630863a9280a2cca7d22053132a881e2c0df9'
MASTER = PROJECT / 'renders/mastering/t017/TUKANA_B2_transient_refinement_24bit.wav'
def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def main():
    before = (MASTER.stat().st_size, MASTER.stat().st_mtime_ns, sha256_file(MASTER))
    assert before[2] == EXPECTED
    with wave.open(str(MASTER)) as wav:
        metadata = dict(channels=wav.getnchannels(), bits=wav.getsampwidth()*8,
                        rate=wav.getframerate(), frames=wav.getnframes())
    assert metadata == dict(channels=2, bits=24, rate=48000, frames=12844801)
    try:
        refine_tukana(PROJECT)
    except FileExistsError:
        pass
    else:
        raise AssertionError('Protected master overwrite guard failed')
    hashes = {}
    for name in ('t015_full_render_validation', 't016_mastering_validation', 't017_transient_refinement'):
        report = load(PROJECT / 'reports' / (name + '.json'))
        assert report.get('status', report.get('objective_result')) == 'PASS'
        assert all(report.get('tests', report.get('validations')).values())
        def verify(node):
            if isinstance(node, dict):
                if 'sha256' in node and ('path' in node or 'output' in node):
                    path = Path(node.get('path', node.get('output')))
                    assert sha256_file(path) == node['sha256'], str(path)
                    hashes[str(path.relative_to(ROOT))] = node['sha256']
                for value in node.values(): verify(value)
            elif isinstance(node, list):
                for value in node: verify(value)
        verify(report)
    scene = load(PROJECT / 'spatial_scenes/tukana_balanced_scene.json')
    rebuilt = build_tukana_scene(load(PROJECT / 'analysis/stem_import_manifest.json'),
        load(PROJECT / 'analysis/musical_map.json'), load(ROOT / 'config/profiles/tukana_spatial.json'))
    assert rebuilt == scene, 'Composer differs from approved scene'
    assert len(scene['sources']) == 10
    plugin = load_plugin(str(PLUGIN_PATH))
    configure_direct_signal(plugin)
    for angle in range(-720, 721, 45):
        set_pose(plugin, angle, 15)
        assert abs(float(plugin.parameters['distance'].raw_value) - CALIBRATED_DISTANCE_RAW) < 1e-6
    keys = [dict(time_seconds=0, azimuth_deg_unwrapped=0, elevation_deg=0, gain_db=0),
            dict(time_seconds=2, azimuth_deg_unwrapped=360, elevation_deg=20, gain_db=-6)]
    assert interpolate_pose(keys, 1) == (180, 10)
    assert interpolate_keyframe_value(keys, 1, 'gain_db', 0) == -3
    del plugin
    scratch_parent = ROOT / 'projects' / '_baseline_validation'
    scratch_parent.mkdir(exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix='t017_', dir=scratch_parent))
    print('Isolated full regression: ' + str(scratch), flush=True)
    full = render_full(PROJECT / 'spatial_scenes/tukana_balanced_scene.json', scratch)
    original = load(PROJECT / 'reports/t015_full_render_validation.json')
    assert not full['processing']['dynamic_distance']
    assert full['processing']['distance_m'] == 3.0
    for role, item in full['source_reports'].items():
        assert item['metrics']['frames'] == 12844801
        assert item['sha256'] == original['source_reports'][role]['sha256'], role
    for name in ('binaural', 'dry_comparison'):
        assert full['outputs'][name]['sha256'] == original['outputs'][name]['sha256'], name
    print('T015 PASS: ten stems and mixes reproduce approved hashes', flush=True)
    mastered = master_tukana(scratch)
    assert mastered['status'] == 'PASS', mastered['tests']
    print('T016 PASS', flush=True)
    refined = refine_tukana(scratch)
    assert refined['status'] == 'PASS', refined['tests']
    assert sha256_file(scratch / 'renders/mastering/t017/TUKANA_B2_transient_refinement_24bit.wav') == EXPECTED
    assert before == (MASTER.stat().st_size, MASTER.stat().st_mtime_ns, sha256_file(MASTER))
    result = dict(status='PASS', baseline='LAISE_T017_APPROVED_BASELINE',
        T015='PASS (full render, exact stem/mix hashes)', T016=mastered['tests'],
        T017=refined['tests'], reproduced_B2_sha256=EXPECTED, protected_master_unchanged=True,
        master_metadata=metadata, duration_seconds=metadata['frames']/metadata['rate'],
        composer_exact_match=True, fixed_distance_pose_orbit=True, gain_interpolation=True,
        verified_historical_artifacts=hashes, scratch_project=str(scratch))
    (ROOT / 'governance/t017_baseline_validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)

if __name__ == '__main__':
    main()
