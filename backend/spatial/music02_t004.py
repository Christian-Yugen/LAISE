"""Independent T004 audition: object homes, phrase turns and measured near-field tests."""
import copy
import json
import math
from pathlib import Path
import numpy as np
from pedalboard import load_plugin
from music02_t002 import (ROOT,PROJECT,load,rms,db,compact,image,peak_window,RATE,BLOCK,
    read_segment,_sha256,ebur128,preview_signal_metrics,cropped_render_metrics,baseline_regressions)
from music02_t003 import key,distance_keys,read,unit,separation_audit
from music02_analysis import dump,snapshot
from music02_preview import write24
from dearvr_adapter import PLUGIN_PATH,configure_direct_signal,set_pose,interpolate_pose,interpolate_keyframe_value

OUT=PROJECT/'experiments/M02_T004'
DIST=np.array([.25,.35,.5,.75,1.,1.5])
EXPORTS=[]

def emit(path,a):
    assert not path.exists(),path
    assert np.isfinite(a).all() and np.max(np.abs(a))<1
    write24(path,a)
    item=dict(path=str(path),sha256=_sha256(path),signal=preview_signal_metrics(path),loudness=ebur128(path))
    assert item['signal']['finite'] and item['loudness']['true_peak_dbtp']<=-3,path
    EXPORTS.append(item)
    return item

def static(az,el):return dict(gain_db=0.,keyframes=[key(0,az,el,'Controlled fixed object'),key(300,az,el,'Hold')])

def render(a,source,start,dist_keys,curve=None,policy='total'):
    """T004-only renderer. Raw controls below .35 m never touch approved DSP."""
    plugin=load_plugin(str(PLUGIN_PATH));configure_direct_signal(plugin)
    out=np.zeros_like(a,np.float32);last=None;trace=[]
    for cursor in range(0,a.shape[1],BLOCK):
        end=min(cursor+BLOCK,a.shape[1]);t=start+cursor/RATE
        az,el=interpolate_pose(source['keyframes'],t);set_pose(plugin,az,el)
        radius=float(interpolate_keyframe_value(dist_keys,t,'distance_m',1.5))
        assert .24999<=radius<=1.8
        plugin.parameters['distance'].raw_value=(radius-.1)/29.9
        compensation=0. if curve is None else float(np.interp(radius,DIST,curve))
        reference_compensation=0. if curve is None else float(np.interp(source.get('growth_reference_distance_m',1.5),DIST,curve))
        growth=max(0.,reference_compensation-compensation)
        retained=0. if policy=='total' else min(growth,2.5 if policy=='partial' else 4.5)
        gain_db=float(source.get('gain_db',0))+interpolate_keyframe_value(source['keyframes'],t,'gain_db',0)+compensation+retained
        gain=10**(gain_db/20)
        if last is None:last=gain
        processed=plugin.process(a[:,cursor:end],sample_rate=RATE,buffer_size=BLOCK,reset=cursor==0)
        out[:,cursor:end]=processed*np.linspace(last,gain,end-cursor,dtype=np.float32);last=gain
        if cursor%(BLOCK*200)==0:trace.append(dict(time_seconds=t,distance_m=radius,compensation_db=compensation,
            retained_growth_db=retained,display=str(plugin.distance),raw_distance=float(plugin.parameters['distance'].raw_value)))
    assert np.isfinite(out).all()
    return out,trace

def faded(a):
    a=a.copy();n=round(.02*RATE);a[:,:n]*=np.linspace(0,1,n);a[:,-n:]*=np.linspace(1,0,n)
    return a

def matched_group(folder,audios,peak=-10):
    """Single offline linked gains; no dynamic limiter or mastering."""
    scale=10**(peak/20)/max(float(np.max(np.abs(a))) for a in audios.values())
    initial={label:emit(OUT/f'{folder}/{label}_raw_24bit.wav',a*np.float32(scale)) for label,a in audios.items()}
    target=min(x['loudness']['integrated_lufs'] for x in initial.values())
    final={label:emit(OUT/f'{folder}/{label}_level_matched_24bit.wav',a*np.float32(scale*10**((target-initial[label]['loudness']['integrated_lufs'])/20))) for label,a in audios.items()}
    assert max(x['loudness']['integrated_lufs'] for x in final.values())-min(x['loudness']['integrated_lufs'] for x in final.values())<=.2
    return dict(raw=initial,matched=final,target_lufs=target)

def compactness(sources):
    report={}
    poses={'percussion':(80,0),'woodwinds':(-65,20),'brass':(135,-20),'backing_vocals':(-120,15)}
    for role,pose in poses.items():
        raw,_=read_segment(sources[role]['input_file'],200,30);start=200+peak_window(raw,8)
        raw,_=read_segment(sources[role]['input_file'],start-1,9)
        before=image(raw[:,RATE:]);variants={'A_original':raw};methods={}
        variants['B_side65'],methods['B_side65']=compact(raw,.65)
        wide=before['effective_width_side_over_total_energy']>.30 or before['correlation']<.30
        if wide:variants['C_side35'],methods['C_side35']=compact(raw,.35)
        arrays={};details={}
        for label,a in variants.items():
            rendered,_=render(a*.008,static(*pose),start-1,distance_keys(300,1.))
            arrays[label]=rendered[:,RATE:]
            details[label]=dict(input_image=image(a[:,RATE:]),output_image=image(arrays[label]),
                boundary=cropped_render_metrics(arrays[label],BLOCK,RATE),method=methods.get(label,'Original stereo'))
        group=matched_group('diagnostics/compactness/'+role,arrays)
        report[role]=dict(interval=[start,start+8],pose=pose,distance_m=1.,original_image=before,variants=details,exports=group,
            stronger_C_included=wide,C_evidence='Side energy >30% or L/R correlation <0.30' if wide else 'Not indicated by width screen',
            adoption='PENDING_HUMAN_REVIEW; no automatic Woodwinds/Backing compactness',
            limitation='Reduced side energy is measurable; improved localization and retained richness require human listening.')
        print('T004 compactness: '+role,flush=True)
    dump(OUT/'reports/compactness.json',report);return report

def make_probe(source):
    raw,_=read_segment(source['input_file'],200,30);start=200+peak_window(raw,2)
    raw,_=read_segment(source['input_file'],start,2)
    # The identical own-stem sample is repeated at every position; no instrument-name task.
    channel=int(np.argmax(np.mean(raw.astype(np.float64)**2,axis=1)))
    probe=np.vstack((raw[channel],raw[channel])).astype(np.float32)
    probe*=np.float32(.04/max(float(np.max(np.abs(probe))),1e-12))
    return faded(probe),dict(role=source['source_id'],interval=[start,start+2],selected_channel=channel,
        dual_mono='DIAGNOSTIC_ONLY; no interchannel cancellation, other-channel-exclusive content omitted')

def near_field(probe,description):
    padded=np.concatenate((np.zeros((2,RATE),np.float32),probe),axis=1);raws={};records=[]
    plugin=load_plugin(str(PLUGIN_PATH));configure_direct_signal(plugin)
    for radius in DIST:
        plugin.parameters['distance'].raw_value=(float(radius)-.1)/29.9
        before=float(plugin.parameters['distance'].raw_value);set_pose(plugin,80,0)
        assert abs(before-float(plugin.parameters['distance'].raw_value))<1e-9
        a,_=render(padded,static(80,0),0,distance_keys(300,float(radius)));a=a[:,RATE:]
        raws[str(radius)]=a;records.append(dict(distance_m=float(radius),rms=rms(a),image=image(a),
            display=str(plugin.distance),raw_readback=before,pose_preserves_distance=True))
    ref=records[-1]['rms'];curve=np.array([db(ref/r['rms']) for r in records])
    for r,c in zip(records,curve):r['total_compensation_db']=float(c)
    sweep=matched_group('diagnostics/distance',raws)
    for r in records:
        r['export']=sweep['matched'][str(r['distance_m'])]
        r['spectral_distribution']=r['export']['signal']['spectral_distribution']
    # Same input and same overall safety gain across policies, deliberately no policy LUFS matching.
    tiled=np.tile(probe,(1,12));a=np.concatenate((np.zeros((2,RATE),np.float32),tiled),axis=1)
    trajectory=[dict(time_seconds=float(t+1),distance_m=float(d)) for t,d in zip([0,3,6,9,12,15,18,21,24],[1.5,1,.75,.5,.35,.25,.5,1,1.5])]
    trajectory.insert(0,dict(time_seconds=0.,distance_m=1.5))
    arrays={};traces={}
    for policy in ('total','partial','natural_limited'):
        y,tr=render(a,static(80,0),0,trajectory,curve,policy);arrays[policy]=y[:,RATE:];traces[policy]=tr
    gain=10**(-10/20)/max(float(np.max(np.abs(y))) for y in arrays.values())
    exports={p:emit(OUT/f'monitors/near_field_{p}_24s_24bit.wav',y*np.float32(gain)) for p,y in arrays.items()}
    result=dict(source=description,pose=dict(azimuth_deg=80,elevation_deg=0),calibration=records,
        measured_gain_curve_db=curve.tolist(),distances_m=DIST.tolist(),static_sweep=sweep,
        monitor_trajectory=[dict(time_seconds=k['time_seconds']-1,distance_m=k['distance_m']) for k in trajectory[1:]],
        exports=exports,traces=traces,common_safety_gain=gain,
        policies=dict(total='Measured RMS compensation vs 1.5m',partial='Retain at most 2.5 dB measured natural growth',
            natural_limited='Retain natural growth until 4.5 dB cap; cap applied smoothly as linked control gain, no limiter'),
        excluded_distance_m=.1,perceptual_status='Timbre, localization, externalization, closeness and comfort PENDING HUMAN',
        input_loop='Same 2s own-stem probe, 20ms boundary fades, twelve repeats in a 24s diagnostic montage',
        limitation='Static RMS calibration controls gain, not perceptual loudness. Nominal .25m display rounds to tenths.')
    dump(OUT/'reports/near_field.json',result);print('T004 isolated near-field complete',flush=True)
    return curve,result

def objects(probe,description,curve):
    positions={'A':(-45,0),'B':(45,40),'C':(-135,40),'D':(135,0)};arrays={};isolated={}
    padded=np.concatenate((np.zeros((2,RATE),np.float32),probe),axis=1)
    for name,pose in positions.items():
        y,_=render(padded,static(*pose),0,distance_keys(300,1.),curve);arrays[name]=y[:,RATE:]
    # Equal isolated RMS; exact same probe also makes coherent summation/fusion a documented test limit.
    target=min(rms(y) for y in arrays.values());arrays={k:y*target/rms(y) for k,y in arrays.items()}
    specs=[['A'],['B'],['C'],['D'],['A','B'],['A','C'],['B','D'],['C','D'],['A','B','C','D']]
    segments=[sum(arrays[k] for k in spec)/math.sqrt(len(spec)) for spec in specs]
    gain=10**(-10/20)/max(float(np.max(np.abs(y))) for y in segments)
    schedule=[];montage=[]
    for i,(spec,y) in enumerate(zip(specs,segments)):
        montage += [y*np.float32(gain),np.zeros((2,RATE//2),np.float32)]
        schedule.append(dict(cue='+'.join(spec),start_seconds=i*2.5,end_seconds=i*2.5+2,
            sources=spec,pair_count=len(spec),linked_count_gain_db=db(1/math.sqrt(len(spec)))))
    delivery=emit(OUT/'monitors/objects_sequence_pairs_four_22_5s_24bit.wav',np.concatenate(montage,axis=1))
    for k,y in arrays.items():isolated[k]=emit(OUT/f'diagnostics/objects/{k}_2s_24bit.wav',y*np.float32(gain))
    result=dict(source=description,positions={k:dict(azimuth_deg=a,elevation_deg=e,distance_m=1.) for k,(a,e) in positions.items()},
        schedule=schedule,export=delivery,isolated=isolated,exact_same_waveform_all_objects=True,
        limitations=['Identical synchronous sources are correlated and can fuse into one phantom image. This requested diagnostic cannot establish independent-object capacity for uncorrelated musical sources.',
            'Count gain uses 1/sqrt(N), not guaranteed identical loudness for coherent sums. Listen for two positions rather than volume changes.'],
        criterion='Where does separation disappear: isolated, pairs or four? No instrument identification.')
    dump(OUT/'reports/object_monitor.json',result);print('T004 sequential/pair object monitor complete',flush=True)
    return result

SLOTS=[(200.,207.02,'woodwinds'),(207.05,218.50,'percussion'),(218.709333,224.426667,'woodwinds')]

def masking(sources):
    bands=[(60,180),(180,500),(500,1500),(1500,4000),(4000,10000),(10000,20000)]
    windows=[(200.,207.02,'woodwinds'),(207.05,218.50,'percussion'),(218.709333,224.426667,'woodwinds'),(224.5,230.,None)]
    records=[];attenuation={}
    for a,b,featured in windows:
        energies={};levels={}
        for role,s in sources.items():
            raw,_=read_segment(s['input_file'],a,b-a)
            raw=raw.astype(np.float64)*10**(float(s.get('gain_db',0))/20)
            frames=np.lib.stride_tricks.sliding_window_view(raw,4096,axis=1)[:,::2048,:]
            spec=np.abs(np.fft.rfft(frames*np.hanning(4096),axis=-1))**2
            freq=np.fft.rfftfreq(4096,1/RATE);energies[role]=np.array([float(spec[:,:,(freq>=lo)&(freq<hi)].sum()) for lo,hi in bands])
            levels[role]=db(rms(raw))
        candidates=[];gains={}
        if featured:
            v=energies[featured];vn=v/max(np.linalg.norm(v),1e-20)
            for role,w in energies.items():
                if role==featured:continue
                overlap=float(np.dot(vn,w/max(np.linalg.norm(w),1e-20)));relative=levels[role]-levels[featured]
                candidate=dict(role=role,band_cosine_overlap=overlap,relative_rms_db=relative,
                    strongest_shared_band_hz=list(bands[int(np.argmax(np.minimum(v/max(v.sum(),1e-20),w/max(w.sum(),1e-20))))]))
                candidates.append(candidate)
                if role not in ('lead_vocal','drums','bass') and overlap>.75 and relative>-8:
                    gains[role]=-2. if role!='other' else -1.5
        attenuation[(a,b)]=gains
        records.append(dict(start_seconds=a,end_seconds=b,featured=featured,role_rms_dbfs=levels,
            band_energy={r:e.tolist() for r,e in energies.items()},potential_maskers=candidates,support_trims_db=gains))
    result=dict(bands_hz=bands,sections=records,method='4096-point Hann STFT, 2048 hop; stereo summed power, RMS after existing role gain',
        policy='Only non-anchor support with band overlap >.75 and relative RMS >-8dB receives modest linked attenuation, 250ms ramps. No global or corrective EQ.',
        limitation='Band overlap and coactivity indicate potential competition, not a measured psychoacoustic masking threshold. Musical usefulness requires listening.')
    dump(OUT/'reports/masking_clarity.json',result);return attenuation,result

def scene_t004(old,mapping,attenuation):
    scene=copy.deepcopy(old);duration=scene['duration_seconds']
    homes={'lead_vocal':(0,0,1.1),'bass':(0,-42,1.3),'drums':(22,-18,1.2),
        'guitar':(-48,0,1.25),'keyboards':(50,30,1.3),'backing_vocals':(-115,18,.9),
        'synth':(155,55,1.5),'percussion':(85,-12,.9),'woodwinds':(-78,28,1.1),
        'brass':(125,-32,1.),'other':(-165,-8,1.6)}
    for s in scene['sources']:
        role=s['source_id'];az,el,d=homes[role];s.pop('preprocess',None)
        frames=[key(0,az,el,'T004 spatial home'),key(duration,az,el,'Home outside audition')]
        event=None
        if role=='lead_vocal':s['preprocess']=dict(side_factor=.5,adoption='Existing audition conditioning retained')
        if role=='percussion':
            s['preprocess']=dict(side_factor=.5,adoption='Retain T003 candidate; no claim of human compactness proof')
            a,b=207.05,218.50;step=(b-a)/8
            frames=[key(0,85,-12,'Static lateral home before turn'),key(a,85,-12,'Percussion takes movement turn')]
            for i in range(9):
                t=a+i*step;frames.append(key(t,85+45*i,-12,'Sector arrival'))
                if i<8:frames.append(key(t+.25,85+45*i,-12,'Brief sector hold'))
            frames.append(key(duration,445,-12,'Equivalent home after one complete orbit'))
            event=(209.0,212.0,.25)
        if role=='woodwinds':
            frames=[key(0,-78,28,'Woodwinds lateral home'),key(200,-78,28,'First expressive phrase'),
                key(203.509333,0,38,'Front elevated crossing'),key(207.018667,78,28,'Hold while percussion moves'),
                key(218.709333,78,28,'Second movement turn'),key(221.568,0,38,'Return upper front'),
                key(224.426667,-78,28,'Return home'),key(duration,-78,28,'Hold')]
            event=(200.8,205.5,.35)
        if role=='brass':
            # Actual two active phrases; change sides only during the intervening silent gap.
            frames=[key(0,125,-32,'First localized home'),key(205.397333,125,-32,'End first active phrase'),
                key(207.,-125,-32,'Reposition in gap; held throughout second entry'),key(duration,-125,-32,'Hold')]
        # Gain edits have no effect on anchor gains and restore support after each selected section.
        gain_points=[(0.,0.),(duration,0.)]
        for (a,b),gains in attenuation.items():
            if role in gains:gain_points += [(max(0,a-.25),0.),(a,gains[role]),(b,gains[role]),(min(duration,b+.25),0.)]
        gain_keys=[dict(time_seconds=t,gain_db=g) for t,g in sorted(dict(gain_points).items())]
        times=sorted({k['time_seconds'] for k in frames}|{k['time_seconds'] for k in gain_keys})
        s['keyframes']=[key(t,*interpolate_pose(frames,t),'Home/phrase turn with linked support gain') for t in times]
        for k in s['keyframes']:k['gain_db']=float(interpolate_keyframe_value(gain_keys,k['time_seconds'],'gain_db',0))
        s['distance_keyframes']=distance_keys(duration,d,event)
        s['home']=dict(azimuth_deg=az,elevation_deg=el,distance_m=d)
        s['growth_reference_distance_m']=d
    scene.update(test_id='M02-T004',status='EXPERIMENTAL_NOT_PROMOTED',human_review='PENDING',
        spatial_turns=[dict(start_seconds=a,end_seconds=b,featured_role=r) for a,b,r in SLOTS],
        near_field_policy='partial: measured natural growth retained up to 2.5 dB; selected events only',
        renderer_policy=dict(distance_range_m=[.25,1.8],T018_logic=False,reflection=False,reverb=False,
            dynamic_distance=True,plugin_stereo_width_unchanged=True),full_render_authorized=False)
    return scene

def run():
    assert not OUT.exists(),'Never overwrite existing experiment'
    before=snapshot(PROJECT);tukana=snapshot(ROOT/'projects/tukana');OUT.mkdir(parents=True)
    dump(OUT/'reports/music02_integrity_before.json',before);dump(OUT/'reports/tukana_integrity_before.json',tukana)
    dump(OUT/'reports/M02_T003_human_review.json',dict(source='User M02-T004 supplied assessment',
        directionality_and_3D='PASS',simultaneous_separation='PARTIAL',extreme_near_field='INSUFFICIENT',promoted=False,
        findings=['Eight directions, front/back and heights perceived','Four simultaneous sources mainly left/right; individual separation unclear',
            'T003 apparently closer, no clear extreme proximity','Circular 3D motion perceived','Natural audio, clarity can improve',
            'No sufficient perceptual superiority over earlier versions','Some sources heard at different positions']))
    old=load(PROJECT/'experiments/M02_T003/spatial_scenes/M02_T003_scene.json')
    sources={s['source_id']:s for s in old['sources']};mapping=load(PROJECT/'analysis/musical_map.json')
    regressions=baseline_regressions(load(PROJECT/'analysis/stem_import_manifest.json'))
    compact_report=compactness(sources)
    probe,description=make_probe(sources['woodwinds']);curve,near_report=near_field(probe,description)
    object_report=objects(probe,description,curve)
    attenuation,mask_report=masking(sources)
    # Musical rendering starts only after all isolated tests and analyses have completed.
    scene=scene_t004(old,mapping,attenuation);dump(OUT/'spatial_scenes/M02_T004_scene.json',scene)
    arrays={};details={}
    for i,s in enumerate(scene['sources'],1):
        role=s['source_id'];raw,_=read_segment(s['input_file'],199,31)
        preprocessing=None
        if 'preprocess' in s:raw,preprocessing=compact(raw,s['preprocess']['side_factor'])
        # Per-role same-pose static calibration avoids treating a woodwind curve as universal.
        test=raw[:,RATE:];offset=peak_window(test,2);sample=raw[:,round((1+offset)*RATE):round((3+offset)*RATE)]
        padded=np.concatenate((np.zeros((2,RATE),np.float32),sample*.008),axis=1)
        calibrations=[]
        for radius in DIST:
            y,_=render(padded,static(s['home']['azimuth_deg'],s['home']['elevation_deg']),0,distance_keys(300,float(radius)))
            calibrations.append(rms(y[:,RATE:]))
        own_curve=np.array([db(calibrations[-1]/max(v,1e-15)) for v in calibrations])
        # Use constant home control for baseline trim. Then retain event growth instead of re-normalizing its average.
        reference=ebur128(PROJECT/f'experiments/M02_T003/spatial_stems/M02_T003_{role}_200_230_24bit.wav')
        old_array=read(PROJECT/f'experiments/M02_T003/spatial_stems/M02_T003_{role}_200_230_24bit.wav')
        # Calibrate only steady geometry/role gain, excluding new support gain automation from trim reference.
        steady=copy.deepcopy(s)
        for k in steady['keyframes']:k['gain_db']=0.
        home,_=render(raw*np.float32(old['gain_staging']['common_input_gain']),steady,199,distance_keys(300,s['home']['distance_m']),own_curve,'total')
        trim=rms(old_array)/max(rms(home[:,RATE:]),1e-15)
        y,trace=render(raw*np.float32(old['gain_staging']['common_input_gain']),s,199,s['distance_keyframes'],own_curve,'partial')
        y=y[:,RATE:]*np.float32(trim);arrays[role]=y
        details[role]=dict(preprocessing=preprocessing,role_curve_db=own_curve.tolist(),static_home_trim_db=db(trim),
            trace=trace,boundary=cropped_render_metrics(y,BLOCK,RATE),reference_lufs=reference['integrated_lufs'])
        print(f'T004 preview [{i}/11]: {role}',flush=True)
    mixed=np.sum(np.stack(list(arrays.values())).astype(np.float64),axis=0).astype(np.float32)
    previous=read(PROJECT/'experiments/M02_T003/renders/comparison/M02_T003_T003_near_field_200_230_level_matched_24bit.wav')
    comparison=matched_group('renders/comparison',dict(T003_200_230=previous,T004_200_230=mixed),-6)
    scale=10**(-6/20)/max(float(np.max(np.abs(mixed))),float(np.max(np.abs(previous))))
    for role,y in arrays.items():details[role]['export']=emit(OUT/f'spatial_stems/{role}_200_230_24bit.wav',y*np.float32(scale))
    audit=separation_audit(scene,mapping);dump(OUT/'reports/angular_separation.json',audit)
    after={r:dict(size=(PROJECT/r).stat().st_size,mtime_ns=(PROJECT/r).stat().st_mtime_ns,sha256=_sha256(PROJECT/r)) for r in before}
    tukana_after=snapshot(ROOT/'projects/tukana');dump(OUT/'reports/music02_existing_integrity_after.json',after)
    dump(OUT/'reports/tukana_integrity_after.json',tukana_after)
    # Audit angular motion of active expressive roles at 10ms resolution, outside silent Brass gap changes.
    active_counts=[];mobile_roles=('woodwinds','percussion','backing_vocals','synth','brass')
    by={s['source_id']:s for s in scene['sources']}
    for t in np.arange(200,229.99,.01):
        movers=[]
        for role in mobile_roles:
            active=any(p['start_seconds']<=t<p['end_seconds'] for p in mapping['stem_events'][role]['active_regions'])
            p=np.array(interpolate_pose(by[role]['keyframes'],t));q=np.array(interpolate_pose(by[role]['keyframes'],t+.005))
            if active and np.max(np.abs(p-q))>1e-5:movers.append(role)
        active_counts.append(len(movers))
    checks=dict(previous_music02_preserved=before==after,tukana_preserved=tukana==tukana_after,
        approved_baseline_regressions=all(regressions.values()),eleven_roles=len(arrays)==11,exact_preview_frames=mixed.shape==(2,1440000),
        at_most_two_active_expressive_movers=max(active_counts)<=2,
        percussion_full_360=abs(interpolate_pose(by['percussion']['keyframes'],218.5)[0]-interpolate_pose(by['percussion']['keyframes'],207.05)[0]-360)<1e-6,
        anchors_fixed=all(len({(k['azimuth_deg_unwrapped'],k['elevation_deg']) for k in by[r]['keyframes']})==1 for r in ('lead_vocal','bass','drums')),
        total_partial_natural_independent=len(near_report['exports'])==3,no_01m=True,no_EQ_mastering_limiter_full_render=True,
        no_automatic_backing_synth_compactness=all('preprocess' not in by[r] for r in ('backing_vocals','synth')),
        all_exports_safe=all(e['signal']['finite'] and e['signal']['sample_peak']<1 and e['loudness']['true_peak_dbtp']<=-3 for e in EXPORTS),
        block_continuity=all(d['boundary']['max_block_boundary_delta']<=max(.25,d['boundary']['max_sample_delta']*.8) for d in details.values()))
    report=dict(test_id='M02-T004',technical_status='PASS' if all(checks.values()) else 'FAIL',human_status='PENDING',
        checks=checks,baseline_regressions=regressions,maximum_active_angular_movers=max(active_counts),
        compactness=compact_report,near_field=near_report,objects=object_report,masking=mask_report,scene_path=str(OUT/'spatial_scenes/M02_T004_scene.json'),
        comparison=comparison,source_reports=details,exports=EXPORTS,
        perceptual_criteria=['Front?','Rear?','Above?','Passed close to ear?','Two sources in different places?','Circular?','Clearer?','Artificial?'],
        no_instrument_naming_required=True,limitations=['Technical stability is verified; perceived localization, timbre naturalness, extreme proximity, externalization and comfort await human review.',
            'Static gain compensation is estimated per role and home pose, not continuously remeasured along each angular trajectory.',
            'Source labels inherited from provided stems, not verified identities; Other remains conservative.'])
    dump(OUT/'reports/M02_T004_validation.json',report);assert all(checks.values()),checks
    print(json.dumps(dict(status=report['technical_status'],checks=checks,wav_files=len(EXPORTS),maximum_movers=max(active_counts)),indent=2),flush=True)

if __name__=='__main__':run()
