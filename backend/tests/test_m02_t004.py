"""Independent encoded, preservation and control regressions for T004."""
import sys
import wave
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend/spatial'))
from music02_t004 import OUT,PROJECT,load,_sha256,dump,DIST
from dearvr_adapter import interpolate_pose,interpolate_keyframe_value

def main():
    report=load(OUT/'reports/M02_T004_validation.json')
    assert report['technical_status']=='PASS' and all(report['checks'].values())
    allowed={96000,384000,1080000,1152000,1440000}
    for entry in report['exports']:
        path=Path(entry['path']);assert path.is_relative_to(OUT) and _sha256(path)==entry['sha256']
        with wave.open(str(path)) as w:
            assert w.getnframes() in allowed
            assert (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())==(2,3,48000,entry['signal']['frames'])
    scene=load(OUT/'spatial_scenes/M02_T004_scene.json');by={s['source_id']:s for s in scene['sources']}
    assert len(by)==11
    for s in by.values():
        for field in ('keyframes','distance_keyframes'):
            keys=s[field];assert keys[0]['time_seconds']==0 and keys[-1]['time_seconds']==scene['duration_seconds']
            assert all(a['time_seconds']<b['time_seconds'] for a,b in zip(keys,keys[1:]))
        assert all(.25<=k['distance_m']<=1.8 for k in s['distance_keyframes'])
    assert min(k['distance_m'] for k in by['percussion']['distance_keyframes'])==.25
    assert min(k['distance_m'] for k in by['woodwinds']['distance_keyframes'])==.35
    for role in ('lead_vocal','drums','bass'):
        assert len({(k['azimuth_deg_unwrapped'],k['elevation_deg']) for k in by[role]['keyframes']})==1
        assert all(k['gain_db']==0 for k in by[role]['keyframes'])
    assert interpolate_pose(by['guitar']['keyframes'],210)[0]<0<interpolate_pose(by['keyboards']['keyframes'],210)[0]
    assert report['maximum_active_angular_movers']<=2
    correction=report.get('gain_reference_correction')
    if correction:assert correction['status']=='PASS'
    for role,s in by.items():
        assert s['growth_reference_distance_m']==s['home']['distance_m']
        growth=correction['roles'][role]['maximum_event_retained_growth_db'] if correction else max(t['retained_growth_db'] for t in report['source_reports'][role]['trace'])
        assert growth==0 if role not in ('woodwinds','percussion') else 1.5<=growth<=3
    assert report['objects']['exact_same_waveform_all_objects']
    assert [x['cue'] for x in report['objects']['schedule']]==['A','B','C','D','A+B','A+C','B+D','C+D','A+B+C+D']
    near=report['near_field'];assert near['distances_m']==[.25,.35,.5,.75,1.,1.5]
    assert len(near['exports'])==3 and near['excluded_distance_m']==.1
    records=near['calibration'];comp=np.array([r['total_compensation_db'] for r in records])
    adjusted=np.array([r['rms'] for r in records])*10**(comp/20)
    assert np.max(adjusted)/np.min(adjusted)<1.00001
    for policy,trace in near['traces'].items():
        maximum=max(t['retained_growth_db'] for t in trace)
        assert maximum<=dict(total=0,partial=2.5,natural_limited=4.5)[policy]+1e-9
        assert all(t['distance_m']>=.25 for t in trace)
    levels=[x['loudness']['integrated_lufs'] for x in report['comparison']['matched'].values()]
    assert max(levels)-min(levels)<=.2
    before=load(OUT/'reports/music02_integrity_before.json');after=load(OUT/'reports/music02_existing_integrity_after.json')
    assert before==after
    for relative,record in before.items():
        path=PROJECT/relative;assert path.stat().st_size==record['size'] and path.stat().st_mtime_ns==record['mtime_ns']
        assert _sha256(path)==record['sha256']
    tukana=load(OUT/'reports/tukana_integrity_before.json')
    assert tukana==load(OUT/'reports/tukana_integrity_after.json')
    for relative,record in tukana.items():assert _sha256(ROOT/'projects/tukana'/relative)==record['sha256']
    assessment=load(OUT/'reports/M02_T003_human_review.json')
    assert assessment['promoted'] is False and assessment['extreme_near_field']=='INSUFFICIENT'
    result=dict(test_id='M02-T004-ENCODED-REGRESSION',status='PASS',verified_wavs=len(report['exports']),
        protected_music02_files=len(before),protected_tukana_files=len(tukana),
        distance_controls_and_gain_caps='PASS',object_sequence='PASS',comparison_spread_lu=max(levels)-min(levels),
        perceptual_status='PENDING_HUMAN_REVIEW')
    dump(OUT/'reports/M02_T004_encoded_regression.json',result);print(result)

if __name__=='__main__':main()
