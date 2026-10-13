"""M02-T001: explainable scene and 30 s preview, using unchanged T017 adapter."""
from pathlib import Path
import json
import math
import sys
import wave
import numpy as np

from dearvr_adapter import (DearVRRenderer, interpolate_pose, wrap_azimuth,
    interpolate_keyframe_value, configure_direct_signal, set_pose, PLUGIN_PATH, CALIBRATED_DISTANCE_RAW)
from tukana_preview_renderer import read_segment, metrics
from tukana_multistem_preview import apply_scene_gain
from stem_importer import _sha256, iter_blocks, import_folder, identify_stems, ROLES
from music02_analysis import PROJECT, ROOT, dump, snapshot, ROLES_M02
sys.path.insert(0,str(ROOT/'backend/mastering'))
from tukana_mastering import ebur128, signal_metrics

def load(path): return json.loads(path.read_text(encoding='utf-8-sig'))

def preview_signal_metrics(path):
    result=signal_metrics(path)
    result.pop('transient_151_92_peak',None)  # Tukana-specific probe is irrelevant here.
    return result

def cropped_render_metrics(audio,block,crop):
    result=metrics(audio,block)
    phase=(-crop)%block
    boundaries=np.arange(phase if phase else block,audio.shape[1],block)
    result['max_block_boundary_delta']=float(np.max(np.abs(audio[:,boundaries]-audio[:,boundaries-1])))
    result['plugin_boundary_phase_frames']=phase
    return result

def key(t,az,el,reason,gain=0):
    return dict(time_seconds=float(t),azimuth_deg_unwrapped=float(az),elevation_deg=float(el),
                gain_db=float(gain),reason=reason)

def scene_for_music(manifest,mapping,gain):
    duration=mapping['duration_seconds'];beat=mapping['bpm']['beat_period_seconds']
    anchors={'lead_vocal':(0,0,0),'bass':(0,-6,0),'drums':(8,0,0),
        'backing_vocals':(-100,12,-2),'guitar':(-42,8,-1),'keyboards':(48,16,-1),
        'percussion':(80,5,-1),'synth':(125,28,-2),'woodwinds':(-62,14,0),
        'brass':(64,9,0),'other':(-18,0,-4)}
    reasons={
        'lead_vocal':'Central stable vocal protects intelligibility through changing instrumental density.',
        'bass':'Stable low-elevation center preserves the low-frequency anchor and avoids rhythmic wandering.',
        'drums':'Stable near-front rhythm anchor preserves attack and impact while separating the lead.',
        'backing_vocals':'Offset rear-left answer layer separates backing activity from the lead without width DSP.',
        'guitar':'Left harmonic lane changes modestly at independently detected texture sections.',
        'keyboards':'Right upper harmonic lane complements the guitar; section changes guide restrained relocation.',
        'synth':'Upper right-rear sustained layer separated from intermittent brass and front anchors.',
        'percussion':'Right-side rhythmic lane; one beat-synchronized phrase orbit culminates at the detected late texture release.',
        'woodwinds':'Expressive lane for measured phrases; long answers traverse behind the listener without shifting vocal anchors.',
        'brass':'Measured intermittent accent phrases occupy a stable side per phrase; side changes occur in intervening silence.',
        'other':'Content identity is pending. Neutral fixed low-gain lane; no instrument-specific motion is claimed.'}
    sources=[]
    for role,r in manifest['stems'].items():
        az,el,g=anchors[role];frames=[key(0,az,el,reasons[role]),key(duration,az,el,'Preserve full timeline through final frame.')]
        behavior='stable_anchor'
        if role in ('guitar','keyboards','synth','backing_vocals'):
            frames=[key(0,az,el,reasons[role])];current=az
            for section in mapping['sections'][1:]:
                t=section['start_seconds']
                occupied=role in section['dominant_roles']
                target=az+(-12 if az<0 else 12) if occupied else az
                frames += [key(max(frames[-1]['time_seconds'],t-beat*2),current,el,'Hold lane until texture transition approach.'),
                           key(t,target,el,f"{section['section_id']}: {'feature' if occupied else 'support'} role in measured section energy.")]
                current=target
            frames.append(key(duration,current,el,'Hold last section position; preserve ending silence.'))
            behavior='restrained_section_lane'
        elif role=='percussion':
            start=mapping['preview_selection']['selected']['start_seconds']
            transitions=[t for t in mapping['transitions'] if start<t['time_seconds']<start+30]
            release=max(transitions,key=lambda x:x['confidence'])
            end=min(mapping['beat_grid_seconds'],key=lambda t:abs(t-release['time_seconds']))
            begin=end-32*beat
            assert begin>=start and end<=start+30
            frames=[key(0,az,el,reasons[role]),key(begin,az,el,'Start one eight-bar rhythmic phrase before the detected late texture release.'),
                key((begin+end)/2,az+180,18,'Half-phrase reaches rear field while front anchors remain stable.'),
                key(end,az+360,el,'Complete one orbit at texture release; end moving after this event.'),
                key(duration,az+360,el,'Fixed wrapped lane after phrase; no continuous orbit.')]
            behavior='single_phrase_360_orbit'
        elif role in ('brass','woodwinds'):
            frames=[key(0,az,el,reasons[role])];last=0;current=az;event_index=0
            for phrase in mapping['stem_events'][role]['phrases']:
                a,b=phrase['start_seconds'],phrase['end_seconds']
                if b-a<0.2: continue
                event_index+=1
                target=(64 if event_index%2 else -64) if role=='brass' else (-62 if event_index%2 else 62)
                approach=max(last,a-beat)
                frames += [key(approach,current,el,'Begin relocation in gap before detected phrase.'),
                           key(a,target,el,f'{role} phrase {event_index}: stable, individually located entry.')]
                if role=='woodwinds' and b-a>beat*8:
                    # Shortest expressive rear traversal, only within a long active phrase.
                    rear=-180 if target<0 else 180
                    frames += [key(a+(b-a)*0.5,rear,24,'Long woodwind answer develops through rear field.'),
                               key(b,-target,el,'Finish expressive answer in complementary lane.')]
                    current=-target
                else:
                    frames.append(key(b,target,el,'Hold position during accent; no continuous motion.'))
                    current=target
                last=b
            frames.append(key(duration,current,el,'Preserve final timeline; hold last position.'))
            behavior='punctual_phrase_locations' if role=='brass' else 'expressive_phrase_traversal'
        # Resolve same-time holds deterministically, and require monotonic full timeline.
        unique={frame['time_seconds']:frame for frame in frames}
        frames=[unique[t] for t in sorted(unique)]
        assert frames[0]['time_seconds']==0 and frames[-1]['time_seconds']==duration
        sources.append(dict(source_id=role,input_file=r['path'],trajectory=behavior,gain_db=g,
            musical_rationale=reasons[role],keyframes=frames))
    return dict(schema='LAISE Spatial Scene v1.0',project='music_02',test_id='M02-T001',
        baseline='LAISE_T017_APPROVED_BASELINE',duration_seconds=duration,sources=sources,
        coordinate_system=dict(type='polar',azimuth='unwrapped degrees; 0=front',elevation='degrees'),
        renderer_policy=dict(scene_is_renderer_independent=True,distance_m=3.0,distance_raw=CALIBRATED_DISTANCE_RAW,
            dynamic_distance=False,reflection=False,reverb=False,experimental_parameters=False),
        gain_staging=gain,other_identification_status='PENDING_HUMAN_IDENTIFICATION',
        human_review='PENDING',preview_selection=mapping['preview_selection'])

def write24(path,audio):
    assert np.isfinite(audio).all() and np.max(np.abs(audio))<1, str(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    integers=np.rint(audio.T.reshape(-1).astype(np.float64)*8388608).astype(np.int32)
    packed=np.empty((len(integers),3),dtype=np.uint8)
    packed[:,0]=integers&255;packed[:,1]=(integers>>8)&255;packed[:,2]=(integers>>16)&255
    with wave.open(str(path),'wb') as stream:
        stream.setnchannels(2);stream.setsampwidth(3);stream.setframerate(48000);stream.writeframes(packed.tobytes())

def transient_check(dry,rendered):
    # Magnitude-envelope timing, independent of binaural channel redistribution.
    hop=240
    def env(a):
        mono=np.max(np.abs(a),axis=0)
        length=(len(mono)//hop)*hop
        return mono[:length].reshape(-1,hop).max(axis=1)
    a,b=env(dry),env(rendered);a=a-a.mean();b=b-b.mean()
    values=[]
    for lag in range(-20,21):
        x=a[max(0,lag):len(a)+min(0,lag)];y=b[max(0,-lag):len(b)+min(0,-lag)]
        values.append(float(np.dot(x,y)/max(np.sqrt(np.dot(x,x)*np.dot(y,y)),1e-20)))
    best=int(np.argmax(values)); peaks=[i for i in range(1,len(a)-1) if a[i]>=a[i-1] and a[i]>a[i+1]]
    chosen=sorted(peaks,key=lambda i:a[i],reverse=True)[:50]
    retained=[bool(np.max(b[max(0,i-2):i+3])>np.quantile(b,0.75)) for i in chosen]
    return dict(method='5-ms magnitude envelopes; cross-correlation and strong-event local retention',
        best_lag_ms=(best-20)*5,search_bounds_ms=[-100,100],search_edge=best in (0,40),correlation=values[best],strong_events=len(chosen),
        retained_fraction=float(np.mean(retained)) if retained else None,
        interpretation='Timing diagnostic; binaural filtering changes spectra/crest, so perceptual transient quality awaits human review.')

def baseline_regressions(manifest):
    import subprocess,tempfile,ast
    checks={}
    checks['head_is_approved_baseline']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==subprocess.check_output(['git','rev-parse','LAISE_T017_APPROVED_BASELINE^{}'],text=True).strip()
    files=['backend/spatial/dearvr_adapter.py','backend/spatial/musical_analyzer.py','backend/spatial/tukana_spatial_composer.py',
        'backend/spatial/tukana_full_renderer.py','backend/spatial/tukana_preview_renderer.py','backend/spatial/tukana_multistem_preview.py',
        'backend/mastering/tukana_mastering.py','backend/mastering/tukana_transient_refinement.py','config/profiles/tukana_spatial.json']
    checks['approved_DSP_composer_analyzer_unchanged']=all((ROOT/path).read_bytes().replace(b'\r\n',b'\n')==
        subprocess.check_output(['git','show',f'LAISE_T017_APPROVED_BASELINE:{path}']).replace(b'\r\n',b'\n') for path in files)
    with tempfile.TemporaryDirectory(dir=PROJECT/'reports',prefix='_import_regression_') as temp:
        imported=import_folder(ROOT/'projects/tukana/stems_original',Path(temp)/'manifest.json')
    checks['Tukana_10_role_import_exact']=imported==load(ROOT/'projects/tukana/analysis/stem_import_manifest.json')
    checks['M02_11_roles']=set(identify_stems(PROJECT/'stems_original',required_roles=ROLES_M02))==set(ROLES_M02)
    # Also exercise genuinely variable role counts without requiring legacy ten.
    with tempfile.TemporaryDirectory(dir=PROJECT/'reports',prefix='_roles_regression_') as temp:
        folder=Path(temp)
        for name in ('0 Lead Vocals.wav','5 Keyboard.wav','9 Brass.wav'):
            with wave.open(str(folder/name),'wb') as w:
                w.setnchannels(2);w.setsampwidth(2);w.setframerate(48000);w.writeframes(bytes(400))
        checks['variable_3_role_import']=set(identify_stems(folder,required_roles=['lead_vocal','keyboards','brass']))=={'lead_vocal','keyboards','brass'}
    from pedalboard import load_plugin
    plugin=load_plugin(str(PLUGIN_PATH));configure_direct_signal(plugin)
    for az in range(-720,721,45):
        set_pose(plugin,az,10)
        assert abs(float(plugin.parameters['distance'].raw_value)-CALIBRATED_DISTANCE_RAW)<1e-6
    checks['fixed_distance_and_wrapping']=True
    keys=[dict(time_seconds=0,azimuth_deg_unwrapped=0,elevation_deg=0,gain_db=0),dict(time_seconds=2,azimuth_deg_unwrapped=360,elevation_deg=20,gain_db=-6)]
    checks['keyframe_gain_orbit_interpolation']=interpolate_pose(keys,1)==(180,10) and interpolate_keyframe_value(keys,1,'gain_db',0)==-3
    no_experiment=True
    for path in (ROOT/'backend').rglob('*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            names=[a.name for a in node.names] if isinstance(node,ast.Import) else ([node.module or ''] if isinstance(node,ast.ImportFrom) else [])
            if any('t018' in name.lower() for name in names):no_experiment=False
    checks['no_T018_imports']=no_experiment
    checks['B2_original_hash']=_sha256(ROOT/'projects/tukana/renders/mastering/t017/TUKANA_B2_transient_refinement_24bit.wav')=='9daf544d7e073d8791f6260eed2630863a9280a2cca7d22053132a881e2c0df9'
    assert all(checks.values()),checks
    return checks

def run():
    manifest=load(PROJECT/'analysis/stem_import_manifest.json');mapping=load(PROJECT/'analysis/musical_map.json');gain=load(PROJECT/'analysis/gain_staging.json')
    regressions=baseline_regressions(manifest)
    scene=scene_for_music(manifest,mapping,gain);scene_path=PROJECT/'spatial_scenes/M02_T001_initial_scene.json';dump(scene_path,scene)
    selected=mapping['preview_selection']['selected'];start=selected['start_seconds'];duration=selected['duration_seconds']
    rate=48000;block=256;count=round(duration*rate);preroll=min(1.0,start);crop=round(preroll*rate)
    spatial=np.zeros((2,count),np.float64);dry_mix=np.zeros_like(spatial);rendered_stems={};source_reports={}
    for index,source in enumerate(scene['sources'],1):
        role=source['source_id'];raw,sr=read_segment(source['input_file'],start-preroll,duration+preroll)
        assert sr==rate and raw.shape[1]==count+crop
        staged=raw*np.float32(gain['common_input_gain'])
        rendered=DearVRRenderer(rate,block).render(staged,source,timeline_offset_seconds=start-preroll)[:,crop:]
        dry=apply_scene_gain(staged,source,start-preroll,rate,block)[:,crop:]
        assert np.isfinite(rendered).all() and np.max(np.abs(rendered))<0.95
        spatial+=rendered;dry_mix+=dry;rendered_stems[role]=rendered
        angular_times=np.arange(start,start+duration,block/rate)
        angles=np.array([interpolate_pose(source['keyframes'],t)[0] for t in angular_times]);wrapped=np.array([wrap_azimuth(a) for a in angles]);steps=(np.diff(wrapped)+180)%360-180
        source_reports[role]=dict(input_sha256=manifest['stems'][role]['sha256'],timeline_start_frame=round(start*rate),frames=count,
            staged_metrics=cropped_render_metrics(rendered,block,crop),angular_continuity=dict(wrapped_crossings=int(np.sum(np.abs(np.diff(wrapped))>180)),
                max_circular_step_deg=float(np.max(np.abs(steps))),unwrapped_range_deg=[float(angles.min()),float(angles.max())]),
            transient_diagnostic=transient_check(dry,rendered) if role in ('drums','percussion','brass','woodwinds') else None)
        if role=='other':
            # Raw excerpt for human content identification; exact segment, no spatial processing.
            audition=PROJECT/f'renders/M02_T001_Other_identification_{start}_{start+duration}_raw.wav'
            write24(audition,raw[:,crop:])
        print(f'M02-T001 [{index:02}/11] {role} rendered',flush=True)
    assert np.max(np.abs(spatial))<0.95 and np.max(np.abs(dry_mix))<0.95
    # Transparent uniform final gain; same initial factor for dry and binaural.
    common=10**(-6/20)/max(float(np.max(np.abs(spatial))),float(np.max(np.abs(dry_mix))),1e-12)
    binaural=(spatial*common).astype(np.float32);dry=(dry_mix*common).astype(np.float32)
    outputs={}
    for name,audio in [('binaural',binaural),('dry_comparison',dry)]:
        path=PROJECT/f'renders/M02_T001_{name}_{start}_{start+duration}_24bit.wav';write24(path,audio)
        loud=ebur128(path)
        assert loud['integrated_lufs'] is not None and loud['true_peak_dbtp'] is not None
        outputs[name]=dict(path=str(path),sha256=_sha256(path),signal=preview_signal_metrics(path),loudness=loud)
    target=min(outputs['binaural']['loudness']['integrated_lufs'],outputs['dry_comparison']['loudness']['integrated_lufs'])
    for name,audio in [('binaural',binaural),('dry_comparison',dry)]:
        match_db=target-outputs[name]['loudness']['integrated_lufs']
        path=PROJECT/f'renders/M02_T001_{name}_{start}_{start+duration}_level_matched_24bit.wav';write24(path,audio*10**(match_db/20))
        outputs[name+'_level_matched']=dict(path=str(path),sha256=_sha256(path),signal=preview_signal_metrics(path),
            loudness=ebur128(path),match_gain_db=match_db)
    for role,audio in rendered_stems.items():
        path=PROJECT/f'spatial_stems/M02_T001_preview_{start}_{start+duration}/{role}_spatial_24bit.wav'
        write24(path,audio*common);source_reports[role]['output']=str(path);source_reports[role]['output_sha256']=_sha256(path)
    originals=all(_sha256(Path(r['path']))==r['sha256'] for r in manifest['stems'].values())
    tukana_after=snapshot(ROOT/'projects/tukana');tukana_before=load(PROJECT/'reports/tukana_integrity_before.json')
    dump(PROJECT/'reports/tukana_integrity_after.json',tukana_after)
    matched_difference=abs(outputs['binaural_level_matched']['loudness']['integrated_lufs']-outputs['dry_comparison_level_matched']['loudness']['integrated_lufs'])
    checks=dict(eleven_stems=len(source_reports)==11,exact_preview_frames=all(r['frames']==count for r in source_reports.values()),
        absolute_synchronization=len({r['timeline_start_frame'] for r in source_reports.values()})==1,
        no_activity_trimming=True,original_hashes_preserved=originals,tukana_project_unchanged=tukana_before==tukana_after,
        finite_no_clipping=all(o['signal']['finite'] and o['signal']['sample_peak']<1 for o in outputs.values()),
        true_peak_headroom=all(o['loudness']['true_peak_dbtp']<=-3 for o in outputs.values()),
        level_matching=matched_difference<=0.2,
        no_boundary_discontinuity_outliers=all(r['staged_metrics']['max_block_boundary_delta']<=max(0.25,r['staged_metrics']['max_sample_delta']*0.8) for r in source_reports.values()),
        angular_continuity=all(r['angular_continuity']['max_circular_step_deg']<2 for r in source_reports.values()),
        full_orbit_present=source_reports['percussion']['angular_continuity']['unwrapped_range_deg'][1]-source_reports['percussion']['angular_continuity']['unwrapped_range_deg'][0]>=359,
        rhythm_envelope_timing=all(abs(source_reports[role]['transient_diagnostic']['best_lag_ms'])<=10 for role in ('drums','percussion')),
        baseline_regressions=all(regressions.values()),no_limiter_or_mastering=True)
    report=dict(test_id='M02-T001',status='PASS' if all(checks.values()) else 'FAIL',human_review='PENDING',
        interval=dict(start_seconds=start,end_seconds=start+duration,frames=count,duration_seconds=duration,preroll_seconds=preroll),
        processing=dict(baseline='LAISE_T017_APPROVED_BASELINE',sample_rate=rate,bits=24,channels=2,block_size=block,
            independent_instances=11,distance_m=3.0,distance_dynamic=False,pre_render_gain_db=gain['common_input_gain_db'],
            common_output_gain=common,no_limiter=True,no_mastering=True,preroll_alignment='All stems start one second earlier; same crop and original absolute keyframe timeline.',
            no_activity_based_trimming=True),checks=checks,baseline_regressions=regressions,scene=str(scene_path),
        scene_sha256=_sha256(scene_path),source_reports=source_reports,outputs=outputs,level_matched_difference_lu=matched_difference,
        caveats=['Section labels, 4/4 and bar phase are hypotheses, not ground truth.',
            'Other instrument identity is pending human identification; its audition file is supplied.',
            'Absolute alignment preserves file-frame origin; recording alignment without timecode cannot be independently inferred.',
            'Binaural transient perception, localization and mono/stereo musical suitability await human review.'])
    dump(PROJECT/'reports/M02_T001_preview_validation.json',report)
    print(json.dumps(dict(status=report['status'],checks=checks,outputs=outputs,regressions=regressions),indent=2),flush=True)
    assert all(checks.values()),checks

if __name__=='__main__': run()
