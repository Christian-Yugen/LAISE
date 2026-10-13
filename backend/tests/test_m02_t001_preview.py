"""Validate encoded M02-T001 delivery artifacts without rerendering audio."""
from pathlib import Path
import hashlib
import json
import wave
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
PROJECT=ROOT/'projects/music_02'
sys.path.insert(0,str(ROOT/'backend/spatial'))
from stem_importer import iter_blocks
from music02_preview import transient_check
from tukana_preview_renderer import read_segment
from tukana_multistem_preview import apply_scene_gain

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def main():
    report=json.loads((PROJECT/'reports/M02_T001_preview_validation.json').read_text(encoding='utf-8'))
    assert report['status']=='PASS' and all(report['checks'].values()),report['checks']
    frames=report['interval']['frames']
    assert 30<=report['interval']['duration_seconds']<=45
    files=[(Path(o['path']),o['sha256']) for o in report['outputs'].values()]
    files += [(Path(o['output']),o['output_sha256']) for o in report['source_reports'].values()]
    assert len(files)==15
    boundary_checks={}
    phase=(-round(report['interval']['preroll_seconds']*48000))%report['processing']['block_size']
    for path,expected in files:
        assert path.is_relative_to(PROJECT),path
        assert digest(path)==expected,path
        with wave.open(str(path)) as w:
            assert (w.getnframes(),w.getframerate(),w.getnchannels(),w.getsampwidth())==(frames,48000,2,3),path
        audio=np.concatenate(list(iter_blocks(path)),axis=0)
        boundaries=np.arange(phase if phase else 256,len(audio),256)
        boundary=float(np.max(np.abs(audio[boundaries]-audio[boundaries-1])))
        maximum=float(np.max(np.abs(np.diff(audio,axis=0))))
        assert np.isfinite(audio).all() and np.max(np.abs(audio))<1
        assert boundary<=max(0.25,maximum*0.8),str(path)
        boundary_checks[path.name]=dict(plugin_boundary_phase_frames=phase,
            maximum_plugin_boundary_delta=boundary,maximum_adjacent_sample_delta=maximum,status='PASS')
    scene=json.loads(Path(report['scene']).read_text(encoding='utf-8'))
    assert len(scene['sources'])==11 and {s['source_id'] for s in scene['sources']}==set(report['source_reports'])
    for source in scene['sources']:
        keys=source['keyframes']
        assert keys[0]['time_seconds']==0 and keys[-1]['time_seconds']==scene['duration_seconds']
        assert all(a['time_seconds']<b['time_seconds'] for a,b in zip(keys,keys[1:]))
    assert scene['renderer_policy']['distance_m']==3 and not scene['renderer_policy']['dynamic_distance']
    # Recheck transient timing using encoded delivery audio and a wider search.
    for source in scene['sources']:
        role=source['source_id']
        encoded=boundary_checks[Path(report['source_reports'][role]['output']).name]
        record=report['source_reports'][role]
        record['encoded_boundary_metrics']=encoded
        record['staged_metrics']['max_block_boundary_delta']=encoded['maximum_plugin_boundary_delta']/report['processing']['common_output_gain']
        record['staged_metrics']['plugin_boundary_phase_frames']=phase
        record['staged_metrics']['boundary_measurement_source']='Encoded PCM24, divided by common final gain; includes export quantization.'
        if role not in ('drums','percussion','brass','woodwinds'):continue
        start=report['interval']['start_seconds'];duration=report['interval']['duration_seconds'];pre=report['interval']['preroll_seconds']
        raw,rate=read_segment(source['input_file'],start-pre,duration+pre)
        dry=apply_scene_gain(raw,source,start-pre,rate,256)[:,round(pre*rate):]
        audio=np.concatenate(list(iter_blocks(record['output'])),axis=0).T
        record['transient_diagnostic']=transient_check(dry,audio)
        assert not record['transient_diagnostic']['search_edge'],role
    report['checks']['rhythm_envelope_timing']=all(abs(report['source_reports'][r]['transient_diagnostic']['best_lag_ms'])<=10 for r in ('drums','percussion'))
    assert report['checks']['rhythm_envelope_timing']
    report['encoded_artifact_validation']='M02_T001_encoded_artifacts_validation.json'
    (PROJECT/'reports/M02_T001_preview_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    result=dict(test_id='M02-T001-ENCODED-ARTIFACTS',status='PASS',verified_pcm24_files=len(files),
        frames=frames,scene_roles=11,scene_timeline_keyframes=True,
        actual_cropped_plugin_boundary_checks=boundary_checks)
    (PROJECT/'reports/M02_T001_encoded_artifacts_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='actual_cropped_plugin_boundary_checks'},indent=2))

if __name__=='__main__':main()
