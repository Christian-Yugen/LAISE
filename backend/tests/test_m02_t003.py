"""Validate T003 delivery; perceptual separation remains a human criterion."""
import json
import sys
import wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend/spatial'))
from music02_t003 import OUT,PROJECT,load,_sha256,dump

def main():
    report=load(OUT/'reports/M02_T003_validation.json');assert report['objective_status']=='PASS' and all(report['checks'].values())
    allowed={2*48000,15*48000,30*48000,round(27.5*48000)}
    for record in report['exported_files']:
        path=Path(record['path']);assert path.is_relative_to(OUT)
        assert _sha256(path)==record['sha256']
        with wave.open(str(path)) as w:
            assert w.getnframes() in allowed
            assert (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())==(2,3,48000,record['frames'])
    scene=load(OUT/'spatial_scenes/M02_T003_scene.json')
    assert len(scene['sources'])==11
    for source in scene['sources']:
        for name in ('keyframes','distance_keyframes'):
            keys=source[name];assert keys[0]['time_seconds']==0 and keys[-1]['time_seconds']==scene['duration_seconds']
            assert all(a['time_seconds']<b['time_seconds'] for a,b in zip(keys,keys[1:]))
    assert [s['azimuth_unwrapped_deg'] for s in scene['sector_events']]==[45,90,135,180,225,270,315,360]
    expected={'front-right','right','rear-right','rear','rear-left','left','front-left','front'}
    cues=report['simplified_monitor']['schedule'];assert {c['expected_direction'] for c in cues[:8]}==expected
    assert len({c['distance_m'] for c in cues})==1
    assert report['excluded_success_criterion']=='Ability to name the instrument'
    lu=[x['level_matched']['loudness']['integrated_lufs'] for x in report['comparison'].values()]
    assert max(lu)-min(lu)<=.2
    before=load(OUT/'reports/music02_integrity_before.json');after=load(OUT/'reports/music02_existing_integrity_after.json');assert before==after
    for key in ('renders/M02_T001_binaural_200_230_level_matched_24bit.wav',
        'experiments/M02_T002/renders/audition_main_energy_controlled/M02_T002_T002_proximity_compact_lead_200_230_level_matched_24bit.wav'):
        assert _sha256(PROJECT/key)==before[str(Path(key))]['sha256']
    result=dict(test_id='M02-T003-ENCODED-REGRESSION',status='PASS',verified_pcm24_wavs=len(report['exported_files']),
        musical_preview_frames=1440000,comparison_loudness_spread_lu=max(lu)-min(lu),
        eight_ordered_sectors=True,same_sound_monitor_equal_distance=True,T001_T002_reference_hashes_preserved=True,
        perceptual_separation='PENDING_HUMAN_REVIEW')
    dump(OUT/'reports/M02_T003_encoded_regression.json',result);print(json.dumps(result,indent=2))

if __name__=='__main__':main()
