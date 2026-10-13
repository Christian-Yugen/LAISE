"""Isolated M02-T002 audition experiment. No approved renderer is modified."""
from pathlib import Path
import copy
import json
import math
import sys
import numpy as np
from pedalboard import load_plugin
from dearvr_adapter import (PLUGIN_PATH, configure_direct_signal, set_pose,
    interpolate_pose, interpolate_keyframe_value, wrap_azimuth, DearVRRenderer)
from tukana_preview_renderer import read_segment
from stem_importer import iter_blocks, _sha256
from music02_analysis import ROOT, PROJECT, dump, snapshot
from music02_preview import (write24, preview_signal_metrics, cropped_render_metrics,
    baseline_regressions, transient_check)
sys.path.insert(0,str(ROOT/'backend/mastering'))
from tukana_mastering import ebur128

RATE=48000
BLOCK=256
DISTANCES=np.array([.35,.50,.75,1.,1.5,2.,3.])
OUT=PROJECT/'experiments/M02_T002'

def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def db(x):return float(20*np.log10(max(float(x),1e-15)))
def rms(a):return float(np.sqrt(np.mean(a.astype(np.float64)**2)))

def image(a):
    a=a.astype(np.float64);l,r=a;mid=(l+r)/2;side=(l-r)/2
    levels=np.sqrt(np.mean(a*a,axis=1));peaks=np.max(np.abs(a),axis=1)
    return dict(rms_lr_dbfs=[db(x) for x in levels],peak_lr_dbfs=[db(x) for x in peaks],
        energy_difference_left_minus_right_db=db(levels[0]/max(levels[1],1e-15)),
        correlation=float(np.corrcoef(a)[0,1]),side_to_mid_db=db(rms(side)/max(rms(mid),1e-15)),
        effective_width_side_over_total_energy=float(np.sum(side*side)/max(np.sum(mid*mid)+np.sum(side*side),1e-20)),
        mean_lr_to_linked_stereo_rms_db=db(rms(mid)/max(rms(a),1e-15)))

def compact(a,width):
    # Linked gain only, no independent L/R correction or plugin Stereo Width.
    mid=(a[0]+a[1])/2;side=(a[0]-a[1])/2
    result=np.vstack((mid+side*width,mid-side*width)).astype(np.float32)
    gain=rms(a)/max(rms(result),1e-15)
    return result*np.float32(gain),dict(method='pre-dearVR mid/side attenuation',side_factor=width,linked_rms_restore_gain=gain)

def mono_probe(a):
    # Anticorrelated Lead cannot safely be averaged without losing side material.
    channel=int(np.argmax(np.mean(a.astype(np.float64)**2,axis=1)))
    result=np.vstack((a[channel],a[channel])).astype(np.float32)
    gain=rms(a)/max(rms(result),1e-15)
    return result*np.float32(gain),dict(method='dominant-channel dual mono, diagnostic only',
        selected_channel='L' if channel==0 else 'R',linked_rms_restore_gain=gain,
        limitation='Avoids interchannel phase cancellation; discards other-channel-exclusive content. Not selected for production.')

def raw_for_distance(meters):
    # Derived anew from this plugin's live endpoint labels; agrees with approved 3 m calibration.
    assert .35<=meters<=3.0
    return (float(meters)-.1)/(30.0-.1)

def parameter_audit():
    plugin=load_plugin(str(PLUGIN_PATH));configure_direct_signal(plugin)
    probes=[]
    for value in (0.,.01,.02,.04,.08,.0969899744,.1,.5,1.):
        plugin.parameters['distance'].raw_value=value
        probes.append(dict(raw=value,display=str(plugin.distance)))
    checks=[]
    for meters in DISTANCES:
        raw=raw_for_distance(meters);plugin.parameters['distance'].raw_value=raw
        shown=float(str(plugin.distance).split()[0]);before=float(plugin.parameters['distance'].raw_value)
        set_pose(plugin,80,5)
        assert abs(shown-meters)<=.051 and abs(float(plugin.parameters['distance'].raw_value)-before)<1e-9
        checks.append(dict(target_m=float(meters),raw=raw,display=str(plugin.distance),
            display_resolution_m=.1,continuous_raw_readback=float(plugin.parameters['distance'].raw_value),pose_preserves_distance=True))
    result=dict(test_id='M02-T002-DISTANCE-CONTROL',probes=probes,checks=checks,
        mapping='linear between live raw endpoint labels 0.1 m and 30.0 m; independently agrees with T017 3 m raw',
        limitation='0.35/0.75 are nominal continuous raw targets; plugin display rounds to tenths, not an independent sub-decimeter measurement.',
        forbidden_minimum_01m_not_rendered=True)
    dump(OUT/'reports/distance_parameter_audit.json',result)
    return result

def render(a,source,start,distance_keys=None,compensation=None):
    plugin=load_plugin(str(PLUGIN_PATH));configure_direct_signal(plugin)
    output=np.zeros_like(a,np.float32);trace=[];previous_gain=None
    for cursor in range(0,a.shape[1],BLOCK):
        end=min(cursor+BLOCK,a.shape[1]);time=start+cursor/RATE
        az,el=interpolate_pose(source['keyframes'],time);set_pose(plugin,az,el)
        meters=interpolate_keyframe_value(distance_keys or [],time,'distance_m',3.0)
        plugin.parameters['distance'].raw_value=raw_for_distance(meters)
        processed=plugin.process(a[:,cursor:end],sample_rate=RATE,buffer_size=BLOCK,reset=cursor==0)
        assert processed.shape==a[:,cursor:end].shape
        gain_db=float(source.get('gain_db',0))+interpolate_keyframe_value(source['keyframes'],time,'gain_db',0)
        linked=1.0 if compensation is None else float(10**(np.interp(meters,DISTANCES,compensation)/20))
        gain=10**(gain_db/20)*linked
        if previous_gain is None:previous_gain=gain
        ramp=np.linspace(previous_gain,gain,end-cursor,dtype=np.float32)
        output[:,cursor:end]=processed*ramp;previous_gain=gain
        if cursor%(BLOCK*200)==0:trace.append(dict(time_seconds=time,distance_m=meters,linked_gain_db=db(linked),display=str(plugin.distance)))
    assert np.isfinite(output).all() and np.max(np.abs(output))<.95
    return output,trace

def at_distance(meters):return [dict(time_seconds=0,distance_m=float(meters)),dict(time_seconds=300,distance_m=float(meters))]

def export_group(name,audios,start,duration,peak_limit=-8):
    folder=OUT/'renders'/name;folder.mkdir(parents=True,exist_ok=False)
    scale=float(10**(peak_limit/20)/max(float(np.max(np.abs(a))) for a in audios.values()))
    entries={}
    for label,a in audios.items():
        path=folder/f'M02_T002_{label}_{start:g}_{start+duration:g}_24bit.wav';write24(path,a*scale)
        entries[label]=dict(path=str(path),sha256=_sha256(path),signal=preview_signal_metrics(path),loudness=ebur128(path),common_safety_gain=scale)
        assert entries[label]['loudness']['integrated_lufs'] is not None
    target=min(item['loudness']['integrated_lufs'] for item in entries.values())
    # Offline single linked gain for listening comparison, never a limiter/loudnorm process.
    for label,a in audios.items():
        g=10**((target-entries[label]['loudness']['integrated_lufs'])/20)
        path=folder/f'M02_T002_{label}_{start:g}_{start+duration:g}_level_matched_24bit.wav';write24(path,a*scale*g)
        entries[label]['level_matched']=dict(path=str(path),sha256=_sha256(path),signal=preview_signal_metrics(path),
            loudness=ebur128(path),linked_gain_db=db(g))
    values=[e['level_matched']['loudness']['integrated_lufs'] for e in entries.values()]
    assert max(values)-min(values)<=.2,values
    return entries

def peak_window(a,seconds):
    hop=4800;energy=np.array([rms(a[:,i:i+hop])**2 for i in range(0,a.shape[1],hop)])
    bins=round(seconds*10);score=np.convolve(energy,np.ones(bins),mode='valid')
    return int(np.argmax(score))/10

def distance_calibration(sources,manifest,input_gain):
    tables={};deliveries={};reports={}
    for role,pose in [('woodwinds',(-62,14)),('backing_vocals',(-45,4))]:
        raw,_=read_segment(manifest['stems'][role]['path'],200,30)
        start=200+peak_window(raw,8);a,_=read_segment(manifest['stems'][role]['path'],start-1,9)
        source=copy.deepcopy(sources[role]);source['keyframes']=[dict(time_seconds=0,azimuth_deg_unwrapped=pose[0],elevation_deg=pose[1],gain_db=0),dict(time_seconds=300,azimuth_deg_unwrapped=pose[0],elevation_deg=pose[1],gain_db=0)]
        samples={};records=[]
        for meters in DISTANCES:
            out,trace=render(a*np.float32(input_gain),source,start-1,at_distance(meters));out=out[:,RATE:]
            samples[f'{role}_{meters:.2f}m']=out
            records.append(dict(distance_m=float(meters),raw_metrics=cropped_render_metrics(out,BLOCK,RATE),image=image(out),
                rms=rms(out),distance_trace=trace,localization='PENDING_HUMAN_REVIEW'))
        reference=records[-1]['rms']
        table=np.array([db(reference/max(item['rms'],1e-15)) for item in records])
        for i,item in enumerate(records):
            item['linked_compensation_db']=float(table[i]);item['compensated_rms_dbfs']=db(item['rms'])+table[i]
        exports=export_group('distance_'+role,samples,start,8)
        reference_bands=exports[f'{role}_3.00m']['signal']['spectral_distribution']
        for item in records:
            entry=exports[f"{role}_{item['distance_m']:.2f}m"]
            item['export']=entry
            item['relative_spectral_band_db_vs_3m']={band:value-reference_bands[band] for band,value in entry['signal']['spectral_distribution'].items()}
        report=dict(role=role,interval=dict(start_seconds=start,duration_seconds=8),pose=pose,records=records,
            gain_policy='Per-role empirical static RMS curve vs 3m. Interpolated linked gain only in preview; no spectral filters.',
            human_localization_stability='PENDING')
        dump(OUT/f'reports/distance_{role}.json',report);tables[role]=table;reports[role]=report;deliveries[role]=exports
        print('M02-T002 distance sweep complete: '+role,flush=True)
    return tables,reports,deliveries

def proximity_curve(a,b,duration,points):
    result=[dict(time_seconds=0,distance_m=3.,reason='Baseline distance outside selected preview phrases')]
    times=np.linspace(a,b,len(points))
    result.append(dict(time_seconds=max(0,a-1),distance_m=3.,reason='Smooth approach begins before selected phrase'))
    result += [dict(time_seconds=float(t),distance_m=float(d),reason='Selected expressive phrase proximity, not global automation') for t,d in zip(times,points)]
    result += [dict(time_seconds=min(duration,b+1),distance_m=3.,reason='Return to baseline after selected event'),dict(time_seconds=duration,distance_m=3.,reason='Baseline held outside audition event')]
    return [dict(v) for _,v in sorted({r['time_seconds']:r for r in result}.items())]

def run():
    assert not OUT.exists(),'M02-T002 already exists; choose a new namespace rather than overwrite evidence.'
    # Freeze every pre-existing MUSIC 02 artifact, original and Tukana file.
    before=snapshot(PROJECT);tukana_before=snapshot(ROOT/'projects/tukana')
    OUT.mkdir(parents=True)
    dump(OUT/'reports/music02_integrity_before.json',before);dump(OUT/'reports/tukana_integrity_before.json',tukana_before)
    scene=load(PROJECT/'spatial_scenes/M02_T001_initial_scene.json');manifest=load(PROJECT/'analysis/stem_import_manifest.json')
    mapping=load(PROJECT/'analysis/musical_map.json');old_report=load(PROJECT/'reports/M02_T001_preview_validation.json')
    sources={s['source_id']:s for s in scene['sources']};input_gain=scene['gain_staging']['common_input_gain'];old_final=old_report['processing']['common_output_gain']
    regressions=baseline_regressions(manifest);control=parameter_audit()
    assessment=dict(test_id='M02-T001-HUMAN',status='PASS_WITH_ADJUSTMENTS',preference='BINAURAL',
        findings=dict(lead='Intended front/center perceived toward left ear',bass_drums='INCONCLUSIVE',
            percussion='Right-left-right movement clear; front/back unconfirmed',woodwinds='Angular motion convincing, wants closer',
            backing='Helps envelopment; above left ear and too far',brass='INCONCLUSIVE',other='IDENTITY_PENDING',
            clicks_distortion_discomfort=False),source='User M02-T002 request; original M02-T001 reports remain unchanged')
    dump(OUT/'reports/M02_T001_human_review.json',assessment)
    # Lead A/B/C: all remain front 0 degrees, 0 elevation, fixed 3m.
    lead,_=read_segment(sources['lead_vocal']['input_file'],200,30)
    old_lead=np.concatenate(list(iter_blocks(PROJECT/'spatial_stems/M02_T001_preview_200_230/lead_vocal_spatial_24bit.wav')),axis=0).T
    start=200+peak_window(lead,12);raw,_=read_segment(sources['lead_vocal']['input_file'],start-1,13)
    narrowed,compact_info=compact(raw,.5);mono,mono_info=mono_probe(raw)
    diagnostic={};lead_details={}
    for label,a in [('A_stereo',raw),('B_compact_side50',narrowed),('C_dual_mono_diagnostic',mono)]:
        out,_=render(a*np.float32(input_gain),sources['lead_vocal'],start-1)
        diagnostic[label]=out[:,RATE:]
        lead_details[label]=dict(input_image=image(a[:,RATE:]),output_image=image(out[:,RATE:]),
            pose=dict(azimuth_deg=0,elevation_deg=0,distance_m=3),adoption='NOT_AUTOMATICALLY_SELECTED')
        write24(OUT/f'renders/lead_inputs/M02_T002_{label}_pre_dearVR_24bit.wav',a[:,RATE:])
    lead_exports=export_group('lead_diagnostics',diagnostic,start,12)
    lead_report=dict(test_id='M02-T002-LEAD',original_full_file=image(np.concatenate(list(iter_blocks(sources['lead_vocal']['input_file'])),axis=0).T),
        original_preview=image(lead),T001_processed_preview=image(old_lead),diagnostic_interval=dict(start_seconds=start,duration_seconds=12),
        variants=lead_details,compact_method=compact_info,mono_method=mono_info,exports=lead_exports,
        finding='Input is not left-energy-dominant. Negative L/R correlation and side-heavy image are plausible contributors to diffuse/in-ear perception. HRTF and listener-specific front externalization remain unproven.',
        main_preview_choice='B side factor 0.5 is an audition candidate; A main-mix control also supplied. C mono is never automatically selected.')
    dump(OUT/'reports/lead_diagnosis.json',lead_report)
    print('M02-T002 Lead diagnosis complete',flush=True)
    tables,distance_reports,distance_exports=distance_calibration(sources,manifest,input_gain)
    variant=copy.deepcopy(scene);variant['test_id']='M02-T002';variant['human_review']='PENDING';variant['status']='EXPERIMENTAL_AUDITION_ONLY'
    variant['renderer_policy']['distance_m']='3m default, selected woodwind/backing events only';variant['renderer_policy']['dynamic_distance']=True
    variant['renderer_policy']['authorization']='User M02-T002 near-field experiment; not adoption into T017 baseline';variant['renderer_policy']['T018_logic']=False
    vs={s['source_id']:s for s in variant['sources']}
    candidates=mapping['stem_events']['woodwinds']['phrases']
    phrase=max(candidates,key=lambda r:max(0,min(230,r['end_seconds'])-max(200,r['start_seconds'])))
    a=max(200.,phrase['start_seconds']);b=min(230.,phrase['end_seconds']);assert b-a>=4
    vs['woodwinds']['distance_keyframes']=proximity_curve(a,b,scene['duration_seconds'],[2.5,1.5,.75,1.2,2.])
    vs['woodwinds']['musical_rationale']+=' Selected long phrase approaches and recedes; original angular keyframes preserved exactly.'
    # A measured backing-response moment when lead energy is low limits competition.
    back,_=read_segment(sources['backing_vocals']['input_file'],200,30)
    hop=4800;be=np.array([rms(back[:,i:i+hop]) for i in range(0,back.shape[1],hop)]);le=np.array([rms(lead[:,i:i+hop]) for i in range(0,lead.shape[1],hop)])
    score=be/np.maximum(le,.002);eligible=(be>=np.quantile(be,.6))&(le<=np.quantile(le,.5));assert eligible.any()
    center=200+int(np.argmax(np.where(eligible,score,-1)))*.1
    center=min(228.,max(202.,center))
    back_keys=[dict(time_seconds=0,distance_m=3.),dict(time_seconds=199,distance_m=3.),dict(time_seconds=200,distance_m=1.5),
        dict(time_seconds=center-1.5,distance_m=1.5),dict(time_seconds=center,distance_m=.75),dict(time_seconds=center+1.5,distance_m=1.5),
        dict(time_seconds=230,distance_m=1.5),dict(time_seconds=231,distance_m=3.),dict(time_seconds=scene['duration_seconds'],distance_m=3.)]
    vs['backing_vocals']['distance_keyframes']=[v for _,v in sorted({r['time_seconds']:r for r in back_keys}.items())]
    for k in vs['backing_vocals']['keyframes']:k['azimuth_deg_unwrapped']=-45.;k['elevation_deg']=4.;k['reason']='Less lateral/lower backing audition; maintain envelopment outside front Lead lane.'
    vs['lead_vocal']['preprocess']=dict(method='linked mid-side compact',side_factor=.5,adoption='PROVISIONAL_AUDITION')
    variant['proximity_events']=dict(woodwind_phrase=[a,b],backing_low_lead_response_center_seconds=center)
    variant['distance_gain_calibration']={role:dict(distances_m=DISTANCES.tolist(),linked_gain_db=values.tolist()) for role,values in tables.items()}
    dump(OUT/'spatial_scenes/M02_T002_proximity_centering_scene.json',variant)
    rendereds={};traces={};changed=[];monitors={}
    for role in ('lead_vocal','woodwinds','backing_vocals','percussion'):
        raw,_=read_segment(sources[role]['input_file'],199,31)
        old_path=PROJECT/f'spatial_stems/M02_T001_preview_200_230/{role}_spatial_24bit.wav'
        old=np.concatenate(list(iter_blocks(old_path)),axis=0).T
        current=vs[role]
        if role=='lead_vocal':
            conditioned,info=compact(raw,.5);new,trace=render(conditioned*np.float32(input_gain),current,199)
            new=new[:,RATE:]*old_final
            # Exact-control validation of the isolated experimental renderer at T017 3m.
            replay,_=render(raw*np.float32(input_gain),sources[role],199);replay=replay[:,RATE:]*old_final
            assert np.max(np.abs(replay-old))<2e-6,'T017 replay differs from preserved Lead'
            monitors[role]=export_group('lead_full_preview',dict(baseline=old,compact_candidate=new),200,30)
        elif role=='percussion':
            conditioned,info=compact(raw,.5);new,trace=render(conditioned*np.float32(input_gain),sources[role],199)
            new=new[:,RATE:]*old_final
            monitors[role]=export_group('percussion_orbit',dict(original_orbit=old,compact_orbit=new),200,30)
            traces[role]=trace
            # Compact source is an isolated alternative, not chosen for the main mix.
            continue
        else:
            new,trace=render(raw*np.float32(input_gain),current,199,current['distance_keyframes'],tables[role]);new=new[:,RATE:]*old_final
            monitors[role]=export_group(role+'_proximity',dict(baseline=old,proximity_candidate=new),200,30)
        rendereds[role]=new;traces[role]=trace;changed.append(role)
        print('M02-T002 monitor complete: '+role,flush=True)
    # Preserve remaining eight roles directly from the already-approved exported stems.
    mix=np.zeros((2,30*RATE),np.float64)
    for role in sources:
        a=rendereds.get(role)
        if a is None:a=np.concatenate(list(iter_blocks(PROJECT/f'spatial_stems/M02_T001_preview_200_230/{role}_spatial_24bit.wav')),axis=0).T
        mix+=a
    lead_control=np.concatenate(list(iter_blocks(PROJECT/'spatial_stems/M02_T001_preview_200_230/lead_vocal_spatial_24bit.wav')),axis=0).T
    control_mix=mix-rendereds['lead_vocal']+lead_control
    baseline=np.concatenate(list(iter_blocks(PROJECT/'renders/M02_T001_binaural_200_230_level_matched_24bit.wav')),axis=0).T
    comparison=export_group('main_comparison',dict(T001_baseline=baseline,T002_proximity_compact_lead=mix.astype(np.float32),
        T002_proximity_original_lead_control=control_mix.astype(np.float32)),200,30,peak_limit=-6)
    for role,a in rendereds.items():write24(OUT/f'spatial_stems/M02_T002_{role}_candidate_200_230_24bit.wav',a)
    raw_perc,_=read_segment(sources['percussion']['input_file'],200,30)
    perc_report=dict(original_input_image=image(raw_perc),T001_output_image=image(np.concatenate(list(iter_blocks(PROJECT/'spatial_stems/M02_T001_preview_200_230/percussion_spatial_24bit.wav')),axis=0).T),
        angular_keyframes_unchanged=True,distance_m=3.,elevation_unchanged=True,orbit_deg=[80,440],
        compact_method='Pre-dearVR M/S side factor 0.5 with linked RMS restoration; plugin Stereo Width unchanged.',
        main_mix_adoption=False,remaining_hypotheses=['Listener/HRTF front-back ambiguity','Stem width','Elevation/distance cues'],
        isolation='Same original orbit, pose, elevation and 3m distance in both monitors; only input compactness changes.')
    dump(OUT/'reports/percussion_orbit_diagnosis.json',perc_report)
    # Keep every old file byte-for-byte, and preserve all Tukana metadata too.
    after_existing={relative:dict(size=(PROJECT/relative).stat().st_size,mtime_ns=(PROJECT/relative).stat().st_mtime_ns,sha256=_sha256(PROJECT/relative)) for relative in before}
    tukana_after=snapshot(ROOT/'projects/tukana')
    checks=dict(old_music02_artifacts_intact=before==after_existing,tukana_project_intact=tukana_before==tukana_after,
        baseline_regressions=all(regressions.values()),fixed_3m_replay_verified=True,
        woodwind_angles_exact=vs['woodwinds']['keyframes']==sources['woodwinds']['keyframes'],
        percussion_angles_exact=vs['percussion']==sources['percussion'],brass_unchanged=vs['brass']==sources['brass'],other_unchanged=vs['other']==sources['other'],
        lead_remains_front=all(k['azimuth_deg_unwrapped']==0 and k['elevation_deg']==0 for k in vs['lead_vocal']['keyframes']),
        mono_not_adopted=True,compact_percussion_not_adopted=True,no_T018_reuse=True,no_full_render_or_mastering=True)
    files=[]
    for folder in (OUT/'renders',OUT/'spatial_stems'):
        for path in folder.rglob('*.wav'):
            stats=preview_signal_metrics(path);loud=ebur128(path)
            assert stats['finite'] and stats['sample_peak']<1 and loud['true_peak_dbtp']<=-3,path
            files.append(dict(path=str(path),sha256=_sha256(path),frames=stats['frames'],sample_peak_dbfs=stats['sample_peak_dbfs'],true_peak_dbtp=loud['true_peak_dbtp']))
    checks['all_exported_audio_finite_unclipped_headroom']=True
    boundaries={role:cropped_render_metrics(a,BLOCK,RATE) for role,a in rendereds.items()}
    checks['no_block_discontinuity_outliers']=all(m['max_block_boundary_delta']<=max(.25,m['max_sample_delta']*.8) for m in boundaries.values())
    report=dict(test_id='M02-T002',objective_status='PASS' if all(checks.values()) else 'FAIL',human_status='PENDING',
        superiority='NOT_ESTABLISHED_WITHOUT_HUMAN_REVIEW',checks=checks,baseline_regressions=regressions,
        comparison=comparison,monitors=monitors,distance_sweeps=distance_exports,lead_diagnostics=lead_exports,
        parameter_control=control,selected_proximity_events=variant['proximity_events'],distance_gain_tables=variant['distance_gain_calibration'],
        distance_traces=traces,boundary_metrics=boundaries,exported_files=files,
        limitations=['Physical/front localization cannot be established from channel metrics.',
            'Distance readout rounds to 0.1m; nominal 0.35/0.75 targets use validated continuous raw mapping.',
            'Empirical linked gain cancels measured static RMS changes, not all time-varying spectral/perceptual changes.',
            'Main mix uses compact Lead as an audition candidate, with original-Lead control supplied; mono and compact Percussion are not adopted.'])
    dump(OUT/'reports/M02_T002_validation.json',report)
    dump(OUT/'reports/music02_existing_integrity_after.json',after_existing);dump(OUT/'reports/tukana_integrity_after.json',tukana_after)
    assert all(checks.values()),checks
    print(json.dumps(dict(status=report['objective_status'],checks=checks,main_comparison=comparison),indent=2),flush=True)

if __name__=='__main__':run()
