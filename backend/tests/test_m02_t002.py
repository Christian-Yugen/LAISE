"""Read-only delivery validation and fixed-distance renderer regression."""
from pathlib import Path
import json
import sys
import wave
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend/spatial'))
from music02_t002 import OUT,PROJECT,load,_sha256,render,DISTANCES,raw_for_distance,dump
from dearvr_adapter import DearVRRenderer,PLUGIN_PATH,configure_direct_signal,set_pose
from pedalboard import load_plugin

def main():
    report=load(OUT/'reports/M02_T002_validation.json')
    assert report['objective_status']=='PASS' and all(report['checks'].values())
    for record in report['exported_files']:
        path=Path(record['path']);assert path.is_relative_to(OUT)
        assert _sha256(path)==record['sha256'],str(path)
        with wave.open(str(path)) as w:
            assert (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())==(2,3,48000,record['frames'])
    scene=load(OUT/'spatial_scenes/M02_T002_proximity_centering_scene.json')
    for s in scene['sources']:
        for name in ('keyframes','distance_keyframes'):
            if name in s:
                keys=s[name]
                assert all(a['time_seconds']<b['time_seconds'] for a,b in zip(keys,keys[1:]))
    source=dict(gain_db=0,keyframes=[dict(time_seconds=0,azimuth_deg_unwrapped=0,elevation_deg=0,gain_db=0),
        dict(time_seconds=2,azimuth_deg_unwrapped=360,elevation_deg=10,gain_db=-1)])
    t=np.arange(96000)/48000;a=np.vstack((.03*np.sin(2*np.pi*440*t),.02*np.sin(2*np.pi*660*t))).astype(np.float32)
    baseline=DearVRRenderer().render(a,source)
    experimental,_=render(a,source,0)
    error=float(np.max(np.abs(baseline-experimental)))
    # Experimental linked gain ramps differ from baseline block-hold gain; verify constant gain separately.
    source['keyframes'][-1]['gain_db']=0
    baseline=DearVRRenderer().render(a,source);experimental,_=render(a,source,0)
    constant_error=float(np.max(np.abs(baseline-experimental)));assert constant_error<1e-6
    p=load_plugin(str(PLUGIN_PATH));configure_direct_signal(p)
    for distance in DISTANCES:
        p.parameters['distance'].raw_value=raw_for_distance(distance);before=p.parameters['distance'].raw_value
        for az in (-180,180,440):
            set_pose(p,az,5);assert p.parameters['distance'].raw_value==before
    comparison=report['comparison']
    lu=[e['level_matched']['loudness']['integrated_lufs'] for e in comparison.values()]
    assert max(lu)-min(lu)<=.2
    before=load(OUT/'reports/music02_integrity_before.json');after=load(OUT/'reports/music02_existing_integrity_after.json')
    assert before==after
    protected='renders/M02_T001_binaural_200_230_level_matched_24bit.wav'
    assert _sha256(PROJECT/protected)==before[str(Path(protected))]['sha256']
    result=dict(test_id='M02-T002-REGRESSION',status='PASS',verified_pcm24_wavs=len(report['exported_files']),
        fixed_3m_constant_gain_renderer_max_error=constant_error,experimental_gain_ramp_vs_baseline_block_hold_max_error=error,
        pose_preserves_each_tested_distance=True,comparison_loudness_spread_lu=max(lu)-min(lu),
        M02_T001_reference_hash_preserved=True,human_superiority='PENDING')
    target=OUT/'reports/M02_T002_encoded_regression.json'
    if target.exists():
        assert load(target)==result,'Existing regression evidence differs; preserve it and use a new report namespace.'
    else:
        dump(target,result)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
