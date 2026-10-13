"""Correct event growth reference with linked per-source gain; no DSP or old experiments changed."""
import copy
import json
import numpy as np
from pathlib import Path
from music02_t004 import (OUT,EXPORTS,DIST,RATE,BLOCK,load,dump,read,emit,matched_group,
    db,cropped_render_metrics,interpolate_keyframe_value)

def run():
    report=load(OUT/'reports/M02_T004_validation.json');scene=load(OUT/'spatial_scenes/M02_T004_scene.json')
    assert 'gain_reference_correction' not in report
    assert all('growth_reference_distance_m' not in s for s in scene['sources']),'Native home-referenced outputs already correct; do not apply historical correction twice.'
    EXPORTS.extend(report['exports']);arrays={};evidence={}
    # Previously exported source PCM24 is the independent post-dearVR signal. Both gain envelopes
    # act after the plugin, so their ratio is equivalent to rerendering with the corrected gain.
    # Quantization is the sole approximation; each old file remains preserved as intermediate evidence.
    for s in scene['sources']:
        role=s['source_id'];details=report['source_reports'][role];curve=np.array(details['role_curve_db'])
        home=float(s['home']['distance_m']);home_comp=float(np.interp(home,DIST,curve))
        ratio=np.empty(31*RATE,np.float32);old_previous=None;new_previous=None;retained=[]
        for cursor in range(0,len(ratio),BLOCK):
            end=min(cursor+BLOCK,len(ratio));t=199+cursor/RATE
            radius=interpolate_keyframe_value(s['distance_keyframes'],t,'distance_m',home)
            comp=float(np.interp(radius,DIST,curve));base=float(s.get('gain_db',0))+interpolate_keyframe_value(s['keyframes'],t,'gain_db',0)
            old_growth=min(max(0,-comp),2.5);new_growth=min(max(0,home_comp-comp),2.5)
            old_gain=10**((base+comp+old_growth)/20);new_gain=10**((base+comp+new_growth)/20)
            if old_previous is None:old_previous=old_gain;new_previous=new_gain
            old_ramp=np.linspace(old_previous,old_gain,end-cursor,dtype=np.float32)
            new_ramp=np.linspace(new_previous,new_gain,end-cursor,dtype=np.float32)
            ratio[cursor:end]=new_ramp/old_ramp;old_previous=old_gain;new_previous=new_gain
            retained.append(new_growth)
        s['growth_reference_distance_m']=home
        original=read(Path(details['export']['path']));arrays[role]=original*ratio[RATE:]
        evidence[role]=dict(home_distance_m=home,home_compensation_db=home_comp,
            maximum_event_retained_growth_db=float(max(retained)),home_event_growth_db=0.,
            ratio_range=[float(ratio.min()),float(ratio.max())],input_pcm24_quantization_error_bound_dbfs=db(.5*2**(-23)*float(ratio.max())))
    mixed=np.sum(np.stack(list(arrays.values())).astype(np.float64),axis=0).astype(np.float32)
    previous=read(OUT.parents[1]/'experiments/M02_T003/renders/comparison/M02_T003_T003_near_field_200_230_level_matched_24bit.wav')
    comparison=matched_group('renders/final_comparison',dict(T003_200_230=previous,T004_200_230=mixed),-6)
    scale=10**(-6/20)/max(float(np.max(np.abs(mixed))),float(np.max(np.abs(previous))))
    for role,a in arrays.items():
        details=report['source_reports'][role];details['pre_correction_export']=details['export']
        details['export']=emit(OUT/f'spatial_stems/final/{role}_200_230_24bit.wav',a*np.float32(scale))
        details['gain_reference_correction']=evidence[role]
        details['final_boundary']=cropped_render_metrics(a,BLOCK,RATE)
    report['pre_correction_comparison']=report['comparison'];report['comparison']=comparison
    report['gain_reference_correction']=dict(method='New/old sample-smoothed linked post-plugin control gain ratio; distance/pose/DSP unchanged',
        status='PASS',earlier_T004_outputs='Preserved as superseded intermediate evidence, not listening recommendation',
        event_growth_reference='Own spatial home, not 1.5m; monitors retain 1.5m starting reference',roles=evidence,
        quantization_limitation='Equivalent post-plugin gain change, within prior PCM24 half-LSB times gain ratio; no limiter or EQ')
    scene['near_field_policy']='partial: up to 2.5dB additional calibrated growth relative to each source home; selected events only'
    report['checks']['event_growth_zero_at_home']=all(v['home_event_growth_db']==0 for v in evidence.values())
    report['checks']['selected_event_growth_cap']=all(v['maximum_event_retained_growth_db']<=2.5+1e-9 for v in evidence.values())
    report['checks']['final_block_continuity']=all(d['final_boundary']['max_block_boundary_delta']<=max(.25,d['final_boundary']['max_sample_delta']*.8) for d in report['source_reports'].values())
    assert all(report['checks'].values()),report['checks']
    report['exports']=EXPORTS
    dump(OUT/'spatial_scenes/M02_T004_scene.json',scene);dump(OUT/'reports/M02_T004_validation.json',report)
    dump(OUT/'reports/event_gain_reference.json',report['gain_reference_correction'])
    print(json.dumps(dict(status='PASS',wav_files=len(EXPORTS),event_growth={k:v['maximum_event_retained_growth_db'] for k,v in evidence.items()},
        matched_lufs={k:v['loudness']['integrated_lufs'] for k,v in comparison['matched'].items()}),indent=2))

if __name__=='__main__':run()
