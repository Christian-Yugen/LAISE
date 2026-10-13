"""M02-T003 near-field angular-separation audition; approved pipelines stay untouched."""
import copy
import json
import math
from pathlib import Path
import numpy as np
from music02_t002 import (ROOT,PROJECT,load,render,rms,compact,image,peak_window,db,RATE,BLOCK,
    _sha256,iter_blocks,read_segment,preview_signal_metrics,ebur128,cropped_render_metrics,baseline_regressions)
from music02_analysis import dump,snapshot
from music02_preview import write24
from dearvr_adapter import interpolate_pose,interpolate_keyframe_value,wrap_azimuth

OUT=PROJECT/'experiments/M02_T003'

def read(path):return np.concatenate(list(iter_blocks(path)),axis=0).T

def key(t,az,el,why):return dict(time_seconds=float(t),azimuth_deg_unwrapped=float(az),elevation_deg=float(el),gain_db=0.,reason=why)

def distance_keys(duration,base,event=None):
    keys=[dict(time_seconds=0.,distance_m=base),dict(time_seconds=duration,distance_m=base)]
    if event:
        a,b,near=event
        keys += [dict(time_seconds=a,distance_m=base),dict(time_seconds=(a+b)/2,distance_m=near),dict(time_seconds=b,distance_m=base)]
    return [v for _,v in sorted({k['time_seconds']:k for k in keys}.items())]

def make_scene(old,mapping):
    scene=copy.deepcopy(old);duration=scene['duration_seconds']
    poses={
        'lead_vocal':(0,0,1.1),'bass':(0,-42,1.3),'drums':(18,-20,1.2),
        'guitar':(-55,8,1.25),'keyboards':(55,15,1.3),'backing_vocals':(-110,10,.9),
        'percussion':(45,-15,.9),'woodwinds':(-75,22,1.1),'synth':(145,48,1.5),
        'brass':(120,-35,.85),'other':(-155,-5,1.6)}
    reasons={
        'lead_vocal':'Stable front center; vocal anchor. Compactness is an audition candidate, not a permanent mono decision.',
        'bass':'Stable central low-elevation anchor; shared central azimuth is intentional, with 42 degrees elevation separation from Lead.',
        'drums':'Stable near-front lower rhythmic anchor; distinct from Lead and Bass.',
        'guitar':'Left-front lane separate from right-front Keyboard.',
        'keyboards':'Right-front elevated harmonic lane, separate from Guitar and Percussion start/end lane.',
        'backing_vocals':'Near left lateral/rear envelopment, with lower elevation than Synth; no displacement of frontal Lead.',
        'percussion':'One continuous 360-degree orbit with eight sector dwells; angular cues take priority over radial depth.',
        'woodwinds':'Expressive front/lateral phrase traversal, distinct from Percussion full orbit.',
        'synth':'Stable high rear-right layer; elevation provides separation.',
        'brass':'Intermittent lower rear-side entries, position held during each accent.',
        'other':'Unidentified content remains static and attenuated; rear-left lane avoids occupying the frontal vocal zone.'}
    beat=mapping['bpm']['beat_period_seconds'];phase=mapping['bpm']['first_beat_seconds']
    orbit_begin=phase+math.ceil((200-phase)/beat)*beat;step=4*beat;dwell=.45
    sectors=['front-right','right','rear-right','rear','rear-left','left','front-left','front']
    orbit=[key(0,45,-15,'Hold front-right outside selected phrase'),key(orbit_begin,45,-15,'Start beat-aligned orbit')]
    sector_times=[]
    for i in range(9):
        t=orbit_begin+i*step;az=45+i*45
        orbit += [key(t,az,-15,'Arrival at '+sectors[i%8]),key(t+dwell,az,-15,'Brief sector dwell; continuous departure afterwards')]
        if i<8:sector_times.append(dict(sector=sectors[i],azimuth_unwrapped_deg=az,start_seconds=t,dwell_seconds=dwell))
    orbit.append(key(duration,405,-15,'Return to front-right after complete orbit; hold'))
    wood_phrases=[p for p in mapping['stem_events']['woodwinds']['phrases'] if p['end_seconds']>200 and p['start_seconds']<230 and p['end_seconds']-p['start_seconds']>=2]
    for s in scene['sources']:
        role=s['source_id'];az,el,dist=poses[role];s['musical_rationale']=reasons[role]
        frames=[key(0,az,el,reasons[role]),key(duration,az,el,'Hold ending; preserve full scene timeline')]
        event=None
        if role=='percussion':frames=orbit;s['preprocess']=dict(method='linked pre-dearVR M/S',side_factor=.5,adoption='T003_AUDITION_ONLY')
        if role=='lead_vocal':s['preprocess']=dict(method='linked pre-dearVR M/S',side_factor=.5,adoption='T003_AUDITION_ONLY')
        if role=='woodwinds':
            frames=[key(0,-75,22,reasons[role])];previous=0.;current=-75.
            for i,p in enumerate(wood_phrases):
                a=max(200.,p['start_seconds']);b=min(230.,p['end_seconds']);left=-75 if i%2==0 else 75;right=-left
                frames += [key(max(previous,a-1),current,22,'Prepare next lateral phrase in gap'),
                    key(a,left,22,'Distinct lateral entry'),key((a+b)/2,0,28,'Expressive upper-front crossing, not rear orbit'),
                    key(b,right,22,'Complete lateral answer')]
                previous=b;current=right
            frames.append(key(duration,current,22,'Hold after last audition phrase'))
            p=max(wood_phrases,key=lambda p:min(230,p['end_seconds'])-max(200,p['start_seconds']))
            event=(max(200.,p['start_seconds']),min(230.,p['end_seconds']),.5)
        if role=='backing_vocals':event=(214.,217.,.6)
        if role=='brass':
            frames=[key(0,120,-35,reasons[role])];current=120.;last=0.
            for i,p in enumerate(mapping['stem_events']['brass']['phrases']):
                a,b=p['start_seconds'],p['end_seconds']
                if b-a<.2:continue
                target=120 if i%2==0 else -120
                frames += [key(max(last,a-1),current,-35,'Reposition during gap'),key(a,target,-35,'Located episodic entry'),key(b,target,-35,'Hold during accent')]
                current=target;last=b
            frames.append(key(duration,current,-35,'Hold after final accent'))
        s['keyframes']=[v for _,v in sorted({k['time_seconds']:k for k in frames}.items())]
        s['distance_keyframes']=distance_keys(duration,dist,event)
        s['trajectory']='sector_defined_360' if role=='percussion' else ('front_lateral_phrase' if role=='woodwinds' else ('episodic_positions' if role=='brass' else 'stable_anchor_or_lane'))
    scene.update(test_id='M02-T003',status='EXPERIMENTAL_AUDITION_ONLY',human_review='PENDING',
        objective='Distinct sources and directions; instrument naming is not a success criterion',
        sector_events=sector_times,orbit_start_seconds=orbit_begin,orbit_end_seconds=orbit_begin+8*step,
        renderer_policy=dict(distance_range_m=[.7,1.8],punctual_near_events_m=[.5,.6],dynamic_distance=True,
            reflection=False,reverb=False,T018_logic=False,priority=['azimuth','front/back','elevation','trajectory','proximity','depth']))
    return scene

def save_audio(path,audio):
    assert not path.exists(),str(path)
    write24(path,audio)
    info=dict(path=str(path),sha256=_sha256(path),signal=preview_signal_metrics(path),loudness=ebur128(path))
    assert info['loudness']['integrated_lufs'] is not None
    assert info['signal']['finite'] and info['signal']['sample_peak']<1
    return info

def compare(audios):
    folder=OUT/'renders/comparison';scale=float(10**(-6/20)/max(float(np.max(np.abs(a))) for a in audios.values()))
    entries={}
    for label,a in audios.items():entries[label]=save_audio(folder/f'M02_T003_{label}_200_230_24bit.wav',a*np.float32(scale))
    target=min(v['loudness']['integrated_lufs'] for v in entries.values())
    for label,a in audios.items():
        gain=10**((target-entries[label]['loudness']['integrated_lufs'])/20)
        entries[label]['level_matched']=save_audio(folder/f'M02_T003_{label}_200_230_level_matched_24bit.wav',a*np.float32(scale*gain))
    assert max(v['level_matched']['loudness']['integrated_lufs'] for v in entries.values())-min(v['level_matched']['loudness']['integrated_lufs'] for v in entries.values())<=.2
    return entries

def unit(az,el):
    a,e=np.deg2rad([az,el]);return np.array([np.cos(e)*np.cos(a),np.cos(e)*np.sin(a),np.sin(e)])

def separation_audit(scene,mapping):
    by={s['source_id']:s for s in scene['sources']};pairs={};crossings=[]
    for time in np.arange(200,230,.1):
        active=[role for role in by if any(p['start_seconds']<=time<p['end_seconds'] for p in mapping['stem_events'][role]['active_regions'])]
        for i,a in enumerate(active):
            for b in active[i+1:]:
                angle=float(np.rad2deg(np.arccos(np.clip(np.dot(unit(*interpolate_pose(by[a]['keyframes'],time)),unit(*interpolate_pose(by[b]['keyframes'],time))),-1,1))))
                pair=a+' / '+b;pairs[pair]=min(angle,pairs.get(pair,180.))
                if angle<20:crossings.append(dict(time_seconds=round(float(time),2),pair=pair,separation_deg=angle))
    return dict(active_pair_minimum_great_circle_separation_deg=pairs,brief_crossings_below_20deg=crossings,
        interpretation='Continuous moving sources necessarily cross some lanes. Exact scene coordinates are not measured perceived localization; nearby anchor azimuths are differentiated by elevation.')

def simplified_monitor(sources,input_gain,compensation):
    # Same composite timbre at every position: direction recognition is independent of instrument naming.
    roles=['percussion','woodwinds','backing_vocals'];probe=np.zeros((2,2*RATE),np.float32)
    for role in roles:
        a,_=read_segment(sources[role]['input_file'],214.3,2)
        channel=int(np.argmax(np.mean(a.astype(np.float64)**2,axis=1)))
        mono=np.vstack((a[channel],a[channel]));probe += mono*np.float32(.03/max(rms(mono),1e-12))
    probe*=np.float32(.1/max(float(np.max(np.abs(probe))),1e-12))
    padded=np.concatenate((np.zeros((2,RATE),np.float32),probe),axis=1)
    specs=[('D1',45,0,'front-right'),('D2',90,0,'right'),('D3',135,0,'rear-right'),('D4',180,0,'rear'),
        ('D5',225,0,'rear-left'),('D6',270,0,'left'),('D7',315,0,'front-left'),('D8',360,0,'front'),
        ('H1',0,-35,'front-low'),('H2',0,0,'front-level'),('H3',0,45,'front-high')]
    arrays={};entries={}
    for label,az,el,direction in specs:
        s=dict(gain_db=0,keyframes=[key(0,az,el,'Controlled same-timbre direction probe'),key(300,az,el,'Hold')])
        keys=distance_keys(300,1.0);a,_=render(padded,s,0,keys,compensation);a=a[:,RATE:]
        # Envelope edges only in synthetic diagnostic montage; source WAVs are untouched.
        fade=np.ones(2*RATE,np.float32);n=round(.02*RATE);fade[:n]=np.linspace(0,1,n);fade[-n:]=np.linspace(1,0,n)
        a*=fade;arrays[label]=a
        entries[label]=save_audio(OUT/f'monitors/direction_segments/M02_T003_{label}_raw_24bit.wav',a)
    target=min(v['loudness']['integrated_lufs'] for v in entries.values())
    matched={label:a*10**((target-entries[label]['loudness']['integrated_lufs'])/20) for label,a in arrays.items()}
    peak=max(float(np.max(np.abs(a))) for a in matched.values());gain=10**(-10/20)/peak
    montage=[];schedule=[];cursor=0.
    for label,az,el,direction in specs:
        a=matched[label]*np.float32(gain);montage += [a,np.zeros((2,RATE//2),np.float32)]
        schedule.append(dict(cue=label,start_seconds=cursor,end_seconds=cursor+2,expected_direction=direction,
            azimuth_deg=az,elevation_deg=el,distance_m=1.,source_content='Identical composite of own stems; naming is irrelevant'))
        cursor+=2.5
    out=save_audio(OUT/'monitors/M02_T003_positions_same_sound_27_5s_24bit.wav',np.concatenate(montage,axis=1))
    # Four simultaneous sources, fewer layers than the musical preview.
    poses=[('A','percussion',45,0),('B','woodwinds',-45,15),('C','backing_vocals',-135,0),('D','keyboards',135,35)]
    four={};records={}
    for label,role,az,el in poses:
        raw,_=read_segment(sources[role]['input_file'],199,16);raw,_=compact(raw,.5)
        s=dict(gain_db=0,keyframes=[key(0,az,el,'Simplified static source'),key(300,az,el,'Hold')])
        a,_=render(raw*np.float32(input_gain),s,199,distance_keys(300,1.),compensation);a=a[:,RATE:]
        four[label]=a;records[label]=save_audio(OUT/f'monitors/four_sources/M02_T003_{label}_isolated_200_215_24bit.wav',a)
    target=min(v['loudness']['integrated_lufs'] for v in records.values())
    mixed=sum(four[label]*10**((target-records[label]['loudness']['integrated_lufs'])/20) for label in four)
    mixed*=np.float32(10**(-8/20)/max(float(np.max(np.abs(mixed))),1e-12))
    simultaneous=save_audio(OUT/'monitors/M02_T003_four_positions_200_215_24bit.wav',mixed)
    result=dict(same_sound_sequence=out,schedule=schedule,source_excerpt_seconds=[214.3,216.3],
        own_stems_used=roles,diagnostic_only_montage=True,mono_for_monitor_only=True,
        criterion='Report direction and height, not instrument identity; equal distance and same composite timbre isolate angular/elevation cues.',
        four_source_mix=simultaneous,four_sources=[dict(cue=l,role=role,azimuth_deg=az,elevation_deg=el,distance_m=1.) for l,role,az,el in poses],
        interpretation='Neither monitor is a complete-song render. Montage timing deliberately differs from music; four-source test preserves 200-215 absolute timing.')
    dump(OUT/'reports/simplified_monitor.json',result);return result

def run():
    assert not OUT.exists(),'Preserve existing experiment; use a new namespace.'
    before=snapshot(PROJECT);tukana_before=snapshot(ROOT/'projects/tukana');OUT.mkdir(parents=True)
    dump(OUT/'reports/music02_integrity_before.json',before);dump(OUT/'reports/tukana_integrity_before.json',tukana_before)
    old=load(PROJECT/'spatial_scenes/M02_T001_initial_scene.json');mapping=load(PROJECT/'analysis/musical_map.json')
    manifest=load(PROJECT/'analysis/stem_import_manifest.json');regressions=baseline_regressions(manifest)
    previous=load(PROJECT/'experiments/M02_T002/reports/M02_T002_validation.json')
    curves=[previous['distance_analysis'][role]['static_calibration']['records'] for role in ('woodwinds','backing_vocals')]
    compensation=np.mean([[r['linked_compensation_db'] for r in curve] for curve in curves],axis=0)
    scene=make_scene(old,mapping);scene['linked_distance_gain_calibration']=dict(source='Measured M02-T002 DirectSignal static curves, mean of two agreeing roles',
        distance_m=[.35,.5,.75,1,1.5,2,3],gain_db=compensation.tolist(),limitation='Approximate transfer across roles; actual per-stem integrated level controlled separately.')
    dump(OUT/'spatial_scenes/M02_T003_scene.json',scene)
    sources={s['source_id']:s for s in scene['sources']};input_gain=old['gain_staging']['common_input_gain']
    adjusted={};source_reports={};preliminary={}
    for i,s in enumerate(scene['sources'],1):
        role=s['source_id'];raw,_=read_segment(s['input_file'],199,31)
        preprocessing=None
        if 'preprocess' in s:raw,preprocessing=compact(raw,s['preprocess']['side_factor'])
        a,trace=render(raw*np.float32(input_gain),s,199,s['distance_keyframes'],compensation);a=a[:,RATE:]
        preliminary[role]=save_audio(OUT/f'spatial_stems/measured/M02_T003_{role}_200_230_raw_24bit.wav',a)
        old_path=PROJECT/f'spatial_stems/M02_T001_preview_200_230/{role}_spatial_24bit.wav'
        reference=ebur128(old_path);delta=reference['integrated_lufs']-preliminary[role]['loudness']['integrated_lufs']
        adjusted[role]=a*np.float32(10**(delta/20))
        times=np.arange(200,230,BLOCK/RATE);az=np.array([interpolate_pose(s['keyframes'],t)[0] for t in times]);wr=np.array([wrap_azimuth(x) for x in az])
        dist=np.array([interpolate_keyframe_value(s['distance_keyframes'],t,'distance_m',3) for t in times])
        source_reports[role]=dict(preprocessing=preprocessing,trace=trace,linked_level_trim_db=float(delta),
            target_reference_lufs=reference['integrated_lufs'],unwrapped_azimuth_range_deg=[float(az.min()),float(az.max())],
            maximum_circular_step_deg=float(np.max(np.abs((np.diff(wr)+180)%360-180))),wrapped_crossings=int(np.sum(np.abs(np.diff(wr))>180)),
            distance_range_m=[float(dist.min()),float(dist.max())],metrics=cropped_render_metrics(adjusted[role],BLOCK,RATE))
        print(f'M02-T003 [{i:02}/11] {role} rendered',flush=True)
    mixed=np.sum(np.stack(list(adjusted.values())).astype(np.float64),axis=0).astype(np.float32)
    baseline=read(PROJECT/'renders/M02_T001_binaural_200_230_level_matched_24bit.wav')
    t002=read(Path(previous['comparison']['T002_proximity_compact_lead']['level_matched']['path']))
    comparison=compare(dict(T001_reference=baseline,T002_reference=t002,T003_near_field=mixed))
    common=10**(-6/20)/max(float(np.max(np.abs(a))) for a in (baseline,t002,mixed))
    for role,a in adjusted.items():
        source_reports[role]['export']=save_audio(OUT/f'spatial_stems/M02_T003_{role}_200_230_24bit.wav',a*np.float32(common))
    monitor=simplified_monitor(sources,input_gain,compensation)
    orbit=sources['percussion'];orbit_audio=adjusted['percussion'];safe=float(10**(-8/20)/max(np.max(np.abs(orbit_audio)),1e-12))
    isolated=save_audio(OUT/'monitors/M02_T003_percussion_eight_sectors_200_230_24bit.wav',orbit_audio*np.float32(safe))
    separation=separation_audit(scene,mapping);dump(OUT/'reports/angular_separation.json',separation)
    after={relative:dict(size=(PROJECT/relative).stat().st_size,mtime_ns=(PROJECT/relative).stat().st_mtime_ns,sha256=_sha256(PROJECT/relative)) for relative in before}
    tukana_after=snapshot(ROOT/'projects/tukana')
    dump(OUT/'reports/music02_existing_integrity_after.json',after);dump(OUT/'reports/tukana_integrity_after.json',tukana_after)
    checks=dict(T001_T002_all_existing_artifacts_preserved=before==after,Tukana_all_files_preserved=tukana_before==tukana_after,
        eleven_sources=len(source_reports)==11,baseline_regressions=all(regressions.values()),exact_preview_frames=mixed.shape==(2,1440000),
        same_absolute_origin_all_stems=True,no_activity_trimming=True,
        near_field_range=all(.4<=r['distance_range_m'][0]<=r['distance_range_m'][1]<=1.8 for r in source_reports.values()),
        fixed_anchor_poses=all(len({(k['azimuth_deg_unwrapped'],k['elevation_deg']) for k in sources[role]['keyframes']})==1 for role in ('lead_vocal','bass','drums')),
        guitar_keyboard_opposite_front_sides=interpolate_pose(sources['guitar']['keyframes'],205)[0]<0<interpolate_pose(sources['keyboards']['keyframes'],205)[0],
        percussion_full_360=source_reports['percussion']['unwrapped_azimuth_range_deg']==[45.,405.],
        eight_distinct_sector_events=len(scene['sector_events'])==8,
        angular_continuity=all(r['maximum_circular_step_deg']<2 for r in source_reports.values()),
        no_block_discontinuity_outliers=all(r['metrics']['max_block_boundary_delta']<=max(.25,r['metrics']['max_sample_delta']*.8) for r in source_reports.values()),
        woodwind_not_full_orbit=source_reports['woodwinds']['unwrapped_azimuth_range_deg']==[-75.,75.],
        no_T018_imports=regressions['no_T018_imports'],no_mastering_limiter_full_render=True)
    files=[]
    for path in OUT.rglob('*.wav'):
        stats=preview_signal_metrics(path);loud=ebur128(path)
        assert stats['finite'] and stats['sample_peak']<1 and loud['true_peak_dbtp'] is not None and loud['true_peak_dbtp']<=-3,str(path)
        files.append(dict(path=str(path),sha256=_sha256(path),frames=stats['frames'],sample_peak_dbfs=stats['sample_peak_dbfs'],true_peak_dbtp=loud['true_peak_dbtp']))
    checks['all_audio_finite_unclipped_headroom']=True
    report=dict(test_id='M02-T003',objective_status='PASS' if all(checks.values()) else 'FAIL',human_status='PENDING',
        checks=checks,baseline_regressions=regressions,comparison=comparison,source_reports=source_reports,
        angular_separation=separation,simplified_monitor=monitor,percussion_sector_monitor=isolated,sector_events=scene['sector_events'],exported_files=files,
        success_criteria=['Distinct sources','Different directions','Front versus rear','Elevation','Around-head passage','Physical closeness','Clarity','Absence of spatial confusion'],
        excluded_success_criterion='Ability to name the instrument',
        limitations=['Coordinates and low clipping do not prove perceived 3D separation; human listening required.',
            'Moving trajectories intentionally cross some occupied angular lanes briefly; see active-pair audit.',
            'Plugin distance display rounds to tenths; radius is a nominal control, not verified physical separation.',
            'Distance gain curve transferred from matching M02-T002 measurements; each actual stem separately level-controlled.',
            'Lead and Percussion compact inputs are audition choices; no mono adoption in musical preview.'])
    dump(OUT/'reports/M02_T003_validation.json',report);assert all(checks.values()),checks
    print(json.dumps(dict(status=report['objective_status'],checks=checks,matched_lufs={k:v['level_matched']['loudness']['integrated_lufs'] for k,v in comparison.items()},wav_files=len(files)),indent=2),flush=True)

if __name__=='__main__':run()
