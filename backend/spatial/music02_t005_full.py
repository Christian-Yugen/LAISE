"""Full-song winner render, exact source timeline and independent section QA."""
import copy
import time
import numpy as np
from music02_t005_common import *
from music02_t005_common import _sha256
from music02_t005_render import render
from music02_t005_selection import evaluate

def recipe(scene):
    name=scene['selected_source_variant'];recipes={};base_gain=scene['gain_staging']['common_input_gain']
    if name.startswith('T002'):
        report=load(PROJECT/'experiments/M02_T002/reports/M02_T002_validation.json')
        for s in scene['sources']:
            role=s['source_id'];table=scene.get('distance_gain_calibration',{}).get(role)
            recipes[role]=dict(curve=table['linked_gain_db'] if table else None,grid=table['distances_m'] if table else DIST,
                policy='total',trim_db=report['main_stem_level_control_db'].get(role,0.))
    elif name=='T003':
        report=load(PROJECT/'experiments/M02_T003/reports/M02_T003_validation.json');table=scene['linked_distance_gain_calibration']
        for s in scene['sources']:
            role=s['source_id'];recipes[role]=dict(curve=table['gain_db'],grid=table['distance_m'],policy='total',trim_db=report['source_reports'][role]['linked_level_trim_db'])
    elif name=='T004':
        report=load(PROJECT/'experiments/M02_T004/reports/M02_T004_validation.json')
        for s in scene['sources']:
            role=s['source_id'];detail=report['source_reports'][role]
            recipes[role]=dict(curve=detail['role_curve_db'],grid=[.25,.35,.5,.75,1.,1.5],policy='partial',trim_db=detail['static_home_trim_db'])
    else:
        for s in scene['sources']:recipes[s['source_id']]=dict(curve=None,grid=DIST,policy='total',trim_db=0.)
    return float(base_gain),recipes

def render_role(source,base_gain,settings):
    role=source['source_id'];a,_=read_segment(source['input_file'],0,FRAMES/RATE)
    assert a.shape==(2,FRAMES)
    original=a.copy();conditioning=None
    if source.get('preprocess'):
        a,conditioning=compact(a,source['preprocess']['side_factor'])
    padded=np.concatenate((np.zeros((2,RATE),np.float32),a*np.float32(base_gain),np.zeros((2,512),np.float32)),axis=1)
    def progress(f,seconds):print(f'T005 full {role}: {f*100:.1f}% ({seconds:.1f}s)',flush=True)
    wet,_,trace=render(padded,source,-1.,curve=settings['curve'],policy=settings['policy'],grid=settings['grid'],progress=progress,gain_time_offset=-512/RATE)
    wet=wet[:,RATE+512:RATE+512+FRAMES]*np.float32(10**(settings['trim_db']/20))
    # Dry comparison keeps the original stereo source, same musical gain automation, no HRTF/distance processing.
    times=np.arange(FRAMES)/RATE;keys=source['keyframes']
    gains=float(source.get('gain_db',0))+np.interp(times,[k['time_seconds'] for k in keys],[k.get('gain_db',0) for k in keys])
    dry=original*np.float32(base_gain)*np.power(10.,gains/20).astype(np.float32)
    path=OUT/f'spatial_stems/full_float32/{role}.wav';write_float(path,wet)
    report=dict(path=str(path),sha256=_sha256(path),frames=wet.shape[1],conditioning=conditioning,recipe=settings,
        metrics=cropped_render_metrics(wet,BLOCK,RATE+512),transients=transient_proxy(original,wet,latency_samples=0),trace=trace,
        source_start_frame=0,source_sha256=_sha256(Path(source['input_file'])))
    dump(OUT/f'reports/full_roles/{role}.json',report)
    return wet,dry,report

def output_qa(scene,library,stem_arrays,mixed,drymix):
    mapping=load(PROJECT/'analysis/musical_map.json');sections=[]
    sources={s['source_id']:s for s in scene['sources']}
    for section in mapping['sections']:
        a,b=section['start_seconds'],section['end_seconds'];left,right=round(a*RATE),round(b*RATE)
        original={role:read_segment(s['input_file'],a,b-a)[0] for role,s in sources.items()}
        outputs={r:v[:,left:right] for r,v in stem_arrays.items()}
        result=evaluate(outputs,scene,original,library,start=a,step=1.,details=True,transient_latency=0)
        record=dict(section_id=section['section_id'],start_seconds=a,end_seconds=b,actual_binaural_output=True,
            components=result['components'],lead_masking=result['lead_masking_windows'],transient_masking=result['transient_masking_windows'],
            pairwise_matrix=result['pairwise_matrix'],stem_features=result['stem_features'],transients=result['transient_by_role'])
        dump(OUT/f'reports/full_sections/{section["section_id"]}.json',record)
        sections.append(dict(section_id=section['section_id'],start_seconds=a,end_seconds=b,components=result['components'],
            lead_intelligibility_proxy=float(np.mean([p['clarity_proxy'] for p in result['lead_masking_windows']])) if result['lead_masking_windows'] else None,
            minimum_coactive_pair_score=min((p['minimum_score'] for p in result['pairwise_matrix'].values() if p['minimum_score'] is not None),default=None)))
        print('T005 full-section QA: '+section['section_id'],flush=True)
    return sections

def run():
    assert not (OUT/'reports/full_render_validation.json').exists()
    scene=load(OUT/'spatial_scenes/selected_architecture_final.json');library=load(OUT/'reports/probe_library_native256.json')
    base_gain,settings=recipe(scene);mix=np.zeros((2,FRAMES),np.float32);drymix=np.zeros_like(mix);roles={};arrays={}
    for i,s in enumerate(scene['sources'],1):
        wet,dry,report=render_role(s,base_gain,settings[s['source_id']]);mix+=wet;drymix+=dry
        roles[s['source_id']]=report;arrays[s['source_id']]=wet
        print(f'T005 full role {i}/11 complete',flush=True)
    assert np.isfinite(mix).all() and np.isfinite(drymix).all()
    # Linked common headroom for dry/spatial and delivered stems; no master processing during rendering.
    dry_gain=rms(mix)/max(rms(drymix),1e-15)
    common=min(1.,10**(-6/20)/max(float(np.max(np.abs(mix))),float(np.max(np.abs(drymix)))*dry_gain))
    mix*=np.float32(common);drymix*=np.float32(common*dry_gain)
    paths=dict(binaural=OUT/'renders/M02_full_binaural_float32.wav',dry=OUT/'renders/M02_full_dry_comparison_float32.wav')
    for label,a in [('binaural',mix),('dry',drymix)]:write_float(paths[label],a)
    for role,a in arrays.items():
        a*=np.float32(common);path=OUT/f'spatial_stems/full_pcm24/{role}_spatial_24bit.wav';assert not path.exists();write24(path,a)
        roles[role]['delivery']=file_metrics(path)
    originals=output_qa(scene,library,arrays,mix,drymix)
    outputs={label:file_metrics(path) for label,path in paths.items()}
    for label,a in [('binaural',mix),('dry',drymix)]:
        outputs[label]['dc_offset_lr']=np.mean(a.astype(np.float64),axis=1).tolist()
        outputs[label]['block_metrics']=cropped_render_metrics(a,BLOCK,RATE)
        # Boundary jumps are flagged against the actual programme derivatives, not mistaken for clicks by magnitude alone.
        delta=np.max(np.abs(np.diff(a,axis=1)),axis=0);boundaries=np.arange((-RATE)%BLOCK,a.shape[1],BLOCK)
        boundary=delta[boundaries-1];threshold=max(.05,float(np.percentile(delta,99.99))*2)
        outputs[label]['click_proxy']=dict(threshold=threshold,unusual_block_boundary_events=int(np.sum(boundary>threshold)),
            interpretation='Derivative-based block discontinuity screen; musical transients and other non-boundary artifacts remain covered by onset comparisons and spectral metrics, not a guarantee of inaudibility.')
    checks=dict(eleven_independent_roles=len(roles)==11,frame_equality=all(r['frames']==FRAMES for r in roles.values()),
        full_duration_frames=all(o['signal']['frames']==FRAMES for o in outputs.values()),timeline_origin_0=True,no_activity_trimming=True,
        finite_unclipped=all(o['signal']['finite'] and o['signal']['sample_peak']<1 for o in outputs.values()),
        true_peak_headroom=all(o['loudness']['true_peak_dbtp']<=-3 for o in outputs.values()),
        dc_safe=all(max(abs(v) for v in o['dc_offset_lr'])<.001 for o in outputs.values()),
        no_detected_block_clicks=outputs['binaural']['click_proxy']['unusual_block_boundary_events']==0,
        exact_full_stem_delivery=all(r['delivery']['signal']['frames']==FRAMES for r in roles.values()),
        dry_rms_matched=abs(db(rms(mix)/rms(drymix)))<.01,approved_cached_renderer_equivalence=load(OUT/'reports/cached_renderer_equivalence.json')['status']=='PASS',
        all_sections_measured=len(originals)==len(load(PROJECT/'analysis/musical_map.json')['sections']))
    weights=[s['end_seconds']-s['start_seconds'] for s in originals]
    overall={key:float(np.average([s['components'][key] for s in originals],weights=weights)) for key in originals[0]['components']}
    selected=load(OUT/'reports/objective_selection_final.json');overall['orbit_integrity']=selected['scores'][scene['selected_source_variant']]['components']['orbit_integrity']
    final_score=sum(overall[k]*WEIGHTS[k] for k in WEIGHTS)
    scene.update(full_render_frames=FRAMES,sample_rate=RATE,uniform_output_gain=common,
        role_render_recipes=settings,dry_comparison='Original stereo sources, musical role gains/automation, global RMS matching; no HRTF or pre-dearVR M/S')
    dump(OUT/'spatial_scenes/M02_final_spatial_scene.json',scene)
    dump(OUT/'spatial_scenes/automation_manifest.json',dict(source_variant=scene['selected_source_variant'],frames=FRAMES,rate=RATE,
        block_size=BLOCK,float32_internal=True,pre_roll_seconds=1.,source_timeline_origin=0.,common_input_gain=base_gain,
        common_plugin_latency_compensated_samples=512,post_gain_control_offset_samples=-512,tail_padding_samples=512,interaural_delays_preserved=True,
        uniform_output_gain=common,dry_comparison_gain=common*dry_gain,
        roles=[dict(source_id=s['source_id'],input_file=s['input_file'],input_sha256=roles[s['source_id']]['source_sha256'],
            keyframes=s['keyframes'],distance_keyframes=s.get('distance_keyframes',[]),preprocess=s.get('preprocess'),
            recipe=settings[s['source_id']],growth_reference_distance_m=s.get('growth_reference_distance_m')) for s in scene['sources']]))
    report=dict(test_id='M02-T005-FULL',status='PASS' if all(checks.values()) else 'FAIL',checks=checks,frames=FRAMES,
        duration_seconds=FRAMES/RATE,selected_variant=scene['selected_source_variant'],outputs=outputs,source_reports=roles,
        actual_full_section_scores=originals,final_spatial_components=overall,final_spatial_score=final_score,
        mastering_applied=False,limitation='All masking, intelligibility, naturalness and discriminability scores are measured technical proxies; absence of proxy failures does not establish universal perception.')
    dump(OUT/'reports/full_render_validation.json',report);assert all(checks.values()),checks
    print(json.dumps(dict(status=report['status'],checks=checks,full_spatial_score=final_score,components=overall),indent=2),flush=True)

if __name__=='__main__':run()
