"""Compare actual historical exports, full-section proxies, and native-control orbit probes."""
import copy
import itertools
import numpy as np
from music02_t005_common import *
from music02_t005_render import render
from music02_t005_probes import reference

def candidates():
    old=load(PROJECT/'spatial_scenes/M02_T001_initial_scene.json')
    t2=load(PROJECT/'experiments/M02_T002/spatial_scenes/M02_T002_proximity_centering_scene.json')
    r2=load(PROJECT/'experiments/M02_T002/reports/M02_T002_validation.json')
    t3=load(PROJECT/'experiments/M02_T003/spatial_scenes/M02_T003_scene.json')
    t4=load(PROJECT/'experiments/M02_T004/spatial_scenes/M02_T004_scene.json')
    r4=load(PROJECT/'experiments/M02_T004/reports/M02_T004_validation.json')
    base={s['source_id']:read(PROJECT/f"spatial_stems/M02_T001_preview_200_230/{s['source_id']}_spatial_24bit.wav") for s in old['sources']}
    second={k:v.copy() for k,v in base.items()}
    for role in ('lead_vocal','woodwinds','backing_vocals'):
        second[role]=read(PROJECT/f'experiments/M02_T002/spatial_stems/M02_T002_{role}_candidate_200_230_24bit.wav')*np.float32(10**(r2['main_stem_level_control_db'][role]/20))
    control={k:v for k,v in second.items()};control['lead_vocal']=base['lead_vocal'];t2control=copy.deepcopy(t2)
    for s in t2control['sources']:
        if s['source_id']=='lead_vocal':s.pop('preprocess',None)
    third={s['source_id']:read(PROJECT/f"experiments/M02_T003/spatial_stems/M02_T003_{s['source_id']}_200_230_24bit.wav") for s in t3['sources']}
    fourth={role:read(Path(d['export']['path'])) for role,d in r4['source_reports'].items()}
    return dict(T001=dict(scene=old,arrays=base),T002=dict(scene=t2,arrays=second),T002_ORIGINAL_LEAD=dict(scene=t2control,arrays=control),
        T003=dict(scene=t3,arrays=third),T004=dict(scene=t4,arrays=fourth))

def evaluate(arrays,scene,dry,library,start=200.,step=1.,details=True,transient_latency=512):
    by={s['source_id']:s for s in scene['sources']};roles=list(arrays);duration=next(iter(arrays.values())).shape[1]/RATE
    peaks={r:max(float(envelope(dry[r]).max(initial=0)),1e-10) for r in roles}
    pair_acc={a+' / '+b:[] for a,b in itertools.combinations(roles,2)};rows=[];clarity=[];lead_mask=[];transient_masks=[]
    fb=[];elev=[];stem_features={r:[] for r in roles}
    for offset in np.arange(0,duration-step*.99,step):
        first=round(offset*RATE);last=round((offset+step)*RATE);time=start+offset+step/2
        active=[];fs={};poses={};envs={}
        for role in roles:
            raw=dry[role][:,first:last];wet=arrays[role][:,first:last]
            if rms(raw)<max(peaks[role]*.03,1e-6):continue
            active.append(role);f=features(wet);fs[role]=f;poses[role]=interpolate_pose(by[role]['keyframes'],time)
            estimate=classify(f,library);target_distance=intended_distance(f,*poses[role],library)
            confidence=estimate['confidence']*(1-.5*features(raw)['objective_width'])
            fbreliable=max(.1,estimate['coverage'])
            fb.append((estimate['front_rear']==direction(poses[role][0]),fbreliable))
            elev.append((estimate['elevation_band']==elevation_band(poses[role][1]),fbreliable))
            envs[role]=envelope(wet)
            if details:stem_features[role].append(dict(time_seconds=float(time),intended_azimuth_deg=poses[role][0],intended_elevation_deg=poses[role][1],
                estimated=estimate,confidence_with_native_stereo_caution=confidence,distance_from_intended_features=target_distance,features=f))
        mask_for={r:[] for r in active}
        for a,b in itertools.combinations(active,2):
            fa,fbv=fs[a],fs[b];pa,pb=poses[a],poses[b]
            angular=math.degrees(math.acos(float(np.clip(np.dot(unit(*pa),unit(*pb)),-1,1))))
            spectral=float(np.dot(fa['band_distribution'],fbv['band_distribution'])/max(np.linalg.norm(fa['band_distribution'])*np.linalg.norm(fbv['band_distribution']),1e-20))
            ea,eb=envs[a],envs[b];temporal=float(np.mean((ea>max(ea.max()*.03,1e-9))&(eb>max(eb.max()*.03,1e-9))))
            similarity=float(np.corrcoef(ea,eb)[0,1]) if min(ea.std(),eb.std())>1e-12 else 0.
            fd=feature_distance(fa,fbv,library);signature=1-math.exp(-fd/1.5)
            score=100*(.65*signature+.25*min(angular/90,1)+.10*min(abs(pa[1]-pb[1])/45,1))
            score*=1-.30*spectral*temporal*max(0,similarity)
            record=dict(time_seconds=float(time),angular_difference_deg=angular,elevation_difference_deg=abs(pa[1]-pb[1]),
                ild_difference_db=abs(fa['ild_global_db']-fbv['ild_global_db']),itd_difference_us=abs(fa['itd_us']-fbv['itd_us']),
                binaural_feature_distance=fd,binaural_spectral_contrast_difference_db=float(np.mean(np.abs(np.array(fa['interaural_spectral_contrast_db'])-fbv['interaural_spectral_contrast_db']))),
                spectral_overlap=spectral,temporal_overlap=temporal,envelope_similarity=similarity,spatial_discriminability_score=float(score))
            pair_acc[a+' / '+b].append(record)
            location_overlap=math.exp(-fd/1.5)
            mask_for[a].append(spectral*temporal*(.35+.65*location_overlap)*10**((fbv['rms_dbfs']-fa['rms_dbfs'])/20))
            mask_for[b].append(spectral*temporal*(.35+.65*location_overlap)*10**((fa['rms_dbfs']-fbv['rms_dbfs'])/20))
        important=[r for r in active if r in ('lead_vocal','drums','bass','woodwinds','percussion','brass')]
        if important:
            scores={r:100/(1+np.log1p(sum(mask_for[r]))*.35) for r in important}
            clarity.append(float(np.average(list(scores.values()),weights=[2 if r=='lead_vocal' else 1 for r in important])))
            if 'lead_vocal' in scores:lead_mask.append(dict(time_seconds=float(time),clarity_proxy=scores['lead_vocal'],masker_index=sum(mask_for['lead_vocal'])))
            for r in ('drums','percussion','brass'):
                if r in scores:transient_masks.append(dict(time_seconds=float(time),role=r,clarity_proxy=scores[r]))
    matrix={pair:dict(coactive_windows=len(values),mean_score=float(np.mean([v['spatial_discriminability_score'] for v in values])) if values else None,
        minimum_score=min((v['spatial_discriminability_score'] for v in values),default=None),windows=values if details else []) for pair,values in pair_acc.items()}
    pair_scores=[v['mean_score'] for v in matrix.values() if v['mean_score'] is not None]
    trans={r:transient_proxy(dry[r],arrays[r],latency_samples=transient_latency) for r in roles}
    transient=float(np.average([trans[r]['score'] for r in ('drums','percussion','brass')],weights=[2,1,1]))
    mixed=np.sum(np.stack(list(arrays.values())).astype(np.float64),axis=0)
    full_feature=features(mixed)
    mono=full_feature['mono_fold_db'];stability=float(np.clip(100-max(0,-mono-3)*10,0,100))
    components=dict(spatial_discriminability=float(np.mean(pair_scores)) if pair_scores else 0.,clarity=float(np.mean(clarity)) if clarity else 0.,
        front_back=100*sum(float(v)*w for v,w in fb)/max(sum(w for _,w in fb),1e-12),
        elevation=100*sum(float(v)*w for v,w in elev)/max(sum(w for _,w in elev),1e-12),
        transient_preservation=transient,peak_safety=100. if np.isfinite(mixed).all() else 0.,mono_stability=stability)
    return dict(components=components,pairwise_matrix=matrix,stem_features=stem_features,transient_by_role=trans,
        lead_masking_windows=lead_mask,transient_masking_windows=transient_masks,
        interpretation='Technical proxies; masking index is not intelligibility measurement, pair score is not a human discrimination probability.')

def full_sections(scene,library):
    mapping=load(PROJECT/'analysis/musical_map.json');by={s['source_id']:s for s in scene['sources']};sections=[]
    for section in mapping['sections']:
        a,b=section['start_seconds'],section['end_seconds'];time=(a+b)/2;features_by={};levels={};envs={};poses={}
        for role,s in by.items():
            raw,_=read_segment(s['input_file'],a,b-a)
            f=features(raw);poses[role]=interpolate_pose(s['keyframes'],time)
            model=min(library['position_models'],key=lambda m:math.degrees(math.acos(float(np.clip(np.dot(unit(*poses[role]),unit(m['azimuth_deg'],m['elevation_deg'])),-1,1)))))
            features_by[role]=copy.deepcopy(model['features']);features_by[role]['active_bands']=f['active_bands']
            features_by[role]['band_distribution']=f['band_distribution']
            gain=float(s.get('gain_db',0))+interpolate_keyframe_value(s['keyframes'],time,'gain_db',0)
            levels[role]=f['rms_dbfs']+gain;envs[role]=envelope(raw)
        pairs=[];masks={r:0. for r in by}
        for left,right in itertools.combinations(by,2):
            x,y=envs[left],envs[right]
            coactive=float(np.mean((x>=max(float(x.max())*.03,1e-6))&(y>=max(float(y.max())*.03,1e-6))))
            if coactive==0:continue
            fl,fr=features_by[left],features_by[right];fd=feature_distance(fl,fr,library)
            overlap=float(np.dot(fl['band_distribution'],fr['band_distribution'])/max(np.linalg.norm(fl['band_distribution'])*np.linalg.norm(fr['band_distribution']),1e-20))
            angle=math.degrees(math.acos(float(np.clip(np.dot(unit(*poses[left]),unit(*poses[right])),-1,1))))
            envelope_similarity=float(np.corrcoef(x,y)[0,1]) if min(x.std(),y.std())>1e-12 else 0.
            dl=np.maximum(np.diff(x,prepend=x[0]),0);dr=np.maximum(np.diff(y,prepend=y[0]),0)
            onset_collision=float(np.mean((dl>dl.max()*.2)&(dr>dr.max()*.2))) if dl.max()>0 and dr.max()>0 else 0.
            score=100*(.65*(1-math.exp(-fd/1.5))+.25*min(angle/90,1)+.1*min(abs(poses[left][1]-poses[right][1])/45,1))*(1-.3*overlap*coactive*max(envelope_similarity,0))
            pairs.append(dict(roles=[left,right],angular_separation_deg=angle,signature_distance=fd,spectral_overlap=overlap,
                temporal_overlap=coactive,envelope_similarity=envelope_similarity,onset_collision_fraction=onset_collision,
                relative_rms_db=levels[left]-levels[right],discriminability_proxy=score))
            loc=math.exp(-fd/1.5);masks[left]+=overlap*coactive*(.35+.65*loc)*10**(np.clip(levels[right]-levels[left],-60,60)/20)
            masks[right]+=overlap*coactive*(.35+.65*loc)*10**(np.clip(levels[left]-levels[right],-60,60)/20)
        important=('lead_vocal','drums','bass','woodwinds','percussion','brass')
        clarity={r:100/(1+np.log1p(masks[r])*.35) for r in important}
        sections.append(dict(section_id=section['section_id'],start_seconds=a,end_seconds=b,pairs=pairs,
            discriminability_proxy=float(np.mean([p['discriminability_proxy'] for p in pairs])) if pairs else 0.,
            clarity_proxy=float(np.mean(list(clarity.values()))),lead_intelligibility_proxy=clarity['lead_vocal'],
            transient_masking_proxy={r:clarity[r] for r in ('drums','percussion','brass')},
            scope='Original-stem spectra/time activity plus intended pose prototypes; a predictive architecture audit, not full binaural output measurement.'))
    return sections

def orbit_test(scene,library,name):
    source=next(s for s in scene['sources'] if s['source_id']=='percussion');keys=source['keyframes']
    # Locate moving interval, not the 0..duration holds surrounding it.
    moving=[(a,b) for a,b in zip(keys,keys[1:]) if abs((b.get('azimuth_deg_unwrapped',b.get('azimuth_deg',0)))-(a.get('azimuth_deg_unwrapped',a.get('azimuth_deg',0))))>1e-8]
    if not moving:return dict(score=0.,status='NO_ORBIT')
    begin=moving[0][0]['time_seconds'];end=moving[-1][1]['time_seconds'];count=round((end-begin+1)*RATE)
    probe=np.tile(reference(),(1,math.ceil(count/reference().shape[1])))[:,:count]
    source=copy.deepcopy(source);source['gain_db']=0.
    for k in source['keyframes']:k['gain_db']=0.
    source['distance_keyframes']=[dict(time_seconds=0.,distance_m=1.),dict(time_seconds=300.,distance_m=1.)]
    y,_,_=render(probe,source,begin-1);y=y[:,RATE:]
    path=OUT/f'diagnostics/orbits/{name}_reference_native256.wav';write24(path,y)
    values=[];expected=[];observed=[]
    for offset in np.arange(0,(end-begin)-.25,.25):
        time=begin+offset+.125;a=y[:,round(offset*RATE):round((offset+.25)*RATE)]
        f=features(a);az,el=interpolate_pose(keys,time);estimate=classify(f,library)
        intended=min(library['position_models'],key=lambda m:math.degrees(math.acos(float(np.clip(np.dot(unit(az,el),unit(m['azimuth_deg'],m['elevation_deg'])),-1,1)))))
        expected.append(intended['features']['ild_global_db']);observed.append(f['ild_global_db'])
        error=math.degrees(math.acos(float(np.clip(np.dot(unit(az,el),unit(estimate['azimuth_deg'],estimate['elevation_deg'])),-1,1))))
        values.append(dict(time_seconds=time,intended_azimuth_unwrapped=az,intended_elevation=el,estimated=estimate,
            angular_error_deg=error,itd_us=f['itd_us'],ild_db=f['ild_global_db']))
    times=np.arange(begin,end,BLOCK/RATE);angles=np.array([interpolate_pose(keys,t)[0] for t in times]);elevs=np.array([interpolate_pose(keys,t)[1] for t in times])
    differences=np.diff(angles);wr=np.array([wrap_azimuth(a) for a in angles]);steps=(np.diff(wr)+180)%360-180
    correlation=float(np.corrcoef(expected,observed)[0,1]);median_error=float(np.median([v['angular_error_deg'] for v in values]))
    boundaries=cropped_render_metrics(y,BLOCK,RATE)
    geometry=bool(np.all(differences>=-1e-8) and abs(interpolate_pose(keys,end)[0]-interpolate_pose(keys,begin)[0]-360)<1e-5)
    tracking=float(np.clip(100*(.7*max(correlation,0)+.3*math.exp(-median_error/45)),0,100))
    sectors=['front-right','right','rear-right','rear','rear-left','left','front-left','front']
    base=interpolate_pose(keys,begin)[0];arrival=[]
    for i,label in enumerate(sectors):
        target=45+i*45
        while target<base:target+=360
        hit=int(np.argmin(np.abs(angles-target)))
        row=min(values,key=lambda v:abs(v['time_seconds']-times[hit]))
        arrival.append(dict(sector=label,angle_unwrapped=target,time_seconds=float(times[hit]),estimated=row['estimated']))
    result=dict(score=tracking if geometry else 0.,status='PASS' if geometry and correlation>.8 and median_error<45 else 'REVIEW_TECHNICAL',
        orbit_degrees=interpolate_pose(keys,end)[0]-base,start_seconds=begin,end_seconds=end,monotonic=geometry,
        maximum_velocity_deg_per_s=float(np.max(np.abs(differences))/(BLOCK/RATE)),maximum_wrapped_step_deg=float(np.max(np.abs(steps))),
        wrap_crossings=int(np.sum(np.abs(np.diff(wr))>180)),ild_progression_correlation=correlation,median_classifier_angular_error_deg=median_error,
        reference_probe_path=str(path),boundary_metrics=boundaries,sector_sequence=arrival,windows=values,
        limitation='Independent same-timbre reference follows actual trajectory; musical-source windows also measured separately, with domain-shift uncertainty.')
    return result

def compactness_audit(library):
    report=load(PROJECT/'experiments/M02_T004/reports/compactness.json');result={}
    for role,r in report.items():
        az,el=r['pose'];tests={}
        for label,e in r['exports']['matched'].items():
            a=read(Path(e['path']));f=features(a);tests[label]=dict(estimated=classify(f,library),distance_from_intended=intended_distance(f,az,el,library),
                width=f['objective_width'],mono_fold_db=f['mono_fold_db'])
        a,b=tests['A_original'],tests['B_side65'];improvement=(a['distance_from_intended']-b['distance_from_intended'])/max(a['distance_from_intended'],1e-9)
        result[role]=dict(variants=tests,relative_position_fit_improvement=improvement,
            candidate_benefit=bool(improvement>.10 and b['mono_fold_db']>=a['mono_fold_db']-.1),
            adoption='Diagnostic evidence only; no full-song width change without hybrid score improvement and transient gate.')
    dump(OUT/'reports/compactness_objective.json',result);return result

def proximity_audit(library):
    previous=load(PROJECT/'experiments/M02_T004/reports/near_field.json');records={}
    for policy,e in previous['exports'].items():
        a=read(Path(e['path']));windows=[]
        for i in range(24):
            f=features(a[:,i*RATE:(i+1)*RATE]);windows.append(dict(time_seconds=i,features=f,estimated=classify(f,library)))
        records[policy]=dict(loudness=e['loudness'],signal=e['signal'],windows=windows,
            transient_vs_total=transient_proxy(read(Path(previous['exports']['total']['path'])),a))
    # Gain-invariant signatures, transient preservation and headroom govern this comparison, not radius label.
    for policy,r in records.items():
        drift=float(np.mean([feature_distance(a['features'],b['features'],library) for a,b in zip(records['total']['windows'],r['windows'])]))
        r['signature_delta_vs_total']=drift
        r['policy_score']=float(100-.5*max(0,r['loudness']['integrated_lufs']-records['total']['loudness']['integrated_lufs'])-10*drift-
            .1*max(0,100-r['transient_vs_total']['score']))
    winner=max(records,key=lambda p:records[p]['policy_score'])
    result=dict(policies=records,selected_policy=winner,near_field_proven=False,
        reason='Prefer gain-invariant signature stability, transients and conservative loudness; no bonus for extreme radius or higher level.',
        closest_normalized_residual_db=previous['calibration'][0]['normalized_waveform_residual_vs_1_5m_db'])
    dump(OUT/'reports/proximity_policy_comparison.json',result);return result

def run():
    library=load(OUT/'reports/probe_library_native256.json');items=candidates();first=next(iter(items.values()))['scene']
    dry={s['source_id']:read_segment(s['input_file'],200,30)[0] for s in first['sources']}
    compactness_audit(library);proximity_audit(library);scores={};orbit_cache={}
    for name,item in items.items():
        print('T005 measuring candidate '+name,flush=True)
        result=evaluate(item['arrays'],item['scene'],dry,library)
        sections=full_sections(item['scene'],library)
        source=next(s for s in item['scene']['sources'] if s['source_id']=='percussion')
        signature=json.dumps(source['keyframes'],sort_keys=True)
        if signature not in orbit_cache:orbit_cache[signature]=orbit_test(item['scene'],library,name)
        orbit=orbit_cache[signature];component=result['components']
        lengths=[s['end_seconds']-s['start_seconds'] for s in sections]
        component['spatial_discriminability']=.65*component['spatial_discriminability']+.35*float(np.average([s['discriminability_proxy'] for s in sections],weights=lengths))
        component['clarity']=.65*component['clarity']+.35*float(np.average([s['clarity_proxy'] for s in sections],weights=lengths))
        component['orbit_integrity']=orbit['score']
        total=float(sum(component[k]*WEIGHTS[k] for k in WEIGHTS))
        scores[name]=dict(score=total,components=component,actual_preview=result,full_section_predictive_audit=sections,orbit=orbit)
        dump(OUT/f'reports/candidates/{name}.json',scores[name])
        print(f'T005 score {name}: {total:.4f}',flush=True)
    winner=max(scores,key=lambda n:(scores[n]['score'],scores[n]['components']['transient_preservation']))
    selected=copy.deepcopy(items[winner]['scene']);selected.update(test_id='M02-T005',selected_source_variant=winner,
        status='AUTOMATICALLY_SELECTED_ARCHITECTURE',human_review='NOT_REQUIRED_BY_USER_T005',
        selection_basis='Locked weighted system-specific technical metrics and reference probes; not universal human validation')
    dump(OUT/'spatial_scenes/selected_architecture.json',selected)
    result=dict(selected_variant=winner,scores={n:dict(score=s['score'],components=s['components']) for n,s in scores.items()},weights=WEIGHTS,
        no_recency_bonus=True,hybrid_created=False,reason='Highest measured weighted score across all candidates; no subjective promotion.',
        interpretation='Spatial/clarity combine 65% actual 200–230s exports and 35% duration-weighted full-section architecture/input proxies. Other components measured from actual preview/reference trajectory. Final full output must independently pass QA.')
    dump(OUT/'reports/objective_selection.json',result);print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':run()
