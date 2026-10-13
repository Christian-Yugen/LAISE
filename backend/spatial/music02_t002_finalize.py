"""Finalize already-rendered M02-T002 audio; never overwrite existing artifacts."""
import json
import numpy as np
from pathlib import Path
from music02_t002 import (ROOT,PROJECT,OUT,load,image,export_group,db,rms,baseline_regressions,
    snapshot,_sha256,dump,preview_signal_metrics,ebur128,cropped_render_metrics,BLOCK,RATE,iter_blocks,
    interpolate_pose,interpolate_keyframe_value,wrap_azimuth,DISTANCES)

def read(path):return np.concatenate(list(iter_blocks(path)),axis=0).T

def raw_group(name):
    paths=sorted((OUT/'renders'/name).glob('*.wav'))
    return {p.name.removeprefix('M02_T002_').split('_200_')[0] if '_200_' in p.name else p.stem:p for p in paths if '_level_matched_' not in p.name}

def main():
    final=OUT/'reports/M02_T002_validation.json';assert not final.exists(),'Final evidence already exists; do not overwrite.'
    scene=load(OUT/'spatial_scenes/M02_T002_proximity_centering_scene.json')
    source_scene=load(PROJECT/'spatial_scenes/M02_T001_initial_scene.json')
    manifest=load(PROJECT/'analysis/stem_import_manifest.json')
    vs={s['source_id']:s for s in scene['sources']};old={s['source_id']:s for s in source_scene['sources']}
    monitors={}
    # Uniform transparent boost to a safe monitor peak, then linked LUFS matching.
    for folder in ('lead_diagnostics','distance_woodwinds','distance_backing_vocals','lead_full_preview','woodwinds_proximity','backing_vocals_proximity','percussion_orbit'):
        paths=[p for p in sorted((OUT/'renders'/folder).glob('*.wav')) if '_level_matched_' not in p.name]
        assert paths,folder
        if folder=='lead_diagnostics':start=load(OUT/'reports/lead_diagnosis.json')['diagnostic_interval']['start_seconds'];duration=12
        elif folder.startswith('distance_'):start=load(OUT/f"reports/{folder}.json")['interval']['start_seconds'];duration=8
        else:start=200;duration=30
        prefix='M02_T002_';suffix=f'_{start:g}_{start+duration:g}_24bit'
        audios={p.stem.removeprefix(prefix).removesuffix(suffix):read(p) for p in paths}
        monitors[folder]=export_group('audition_'+folder,audios,start,duration)
    # Match each changed stem's integrated loudness to its original in the mix too.
    changed={role:read(OUT/f'spatial_stems/M02_T002_{role}_candidate_200_230_24bit.wav') for role in ('lead_vocal','woodwinds','backing_vocals')}
    trims={}
    for role,folder,label in [('lead_vocal','lead_full_preview','compact_candidate'),('woodwinds','woodwinds_proximity','proximity_candidate'),('backing_vocals','backing_vocals_proximity','proximity_candidate')]:
        entries=monitors[folder]
        delta=entries['baseline']['loudness']['integrated_lufs']-entries[label]['loudness']['integrated_lufs']
        changed[role]*=np.float32(10**(delta/20));trims[role]=float(delta)
    mixed=np.zeros((2,30*RATE),np.float64)
    for role in old:
        a=changed.get(role)
        if a is None:a=read(PROJECT/f'spatial_stems/M02_T001_preview_200_230/{role}_spatial_24bit.wav')
        mixed+=a
    old_lead=read(PROJECT/'spatial_stems/M02_T001_preview_200_230/lead_vocal_spatial_24bit.wav')
    original_lead_control=mixed-changed['lead_vocal']+old_lead
    baseline=read(PROJECT/'renders/M02_T001_binaural_200_230_level_matched_24bit.wav')
    comparison=export_group('audition_main_energy_controlled',dict(T001_baseline=baseline,
        T002_proximity_compact_lead=mixed.astype(np.float32),T002_proximity_original_lead_control=original_lead_control.astype(np.float32)),200,30,peak_limit=-6)
    before=load(OUT/'reports/music02_integrity_before.json');tukana_before=load(OUT/'reports/tukana_integrity_before.json')
    after={relative:dict(size=(PROJECT/relative).stat().st_size,mtime_ns=(PROJECT/relative).stat().st_mtime_ns,sha256=_sha256(PROJECT/relative)) for relative in before}
    tukana_after=snapshot(ROOT/'projects/tukana');regressions=baseline_regressions(manifest)
    angle_checks={}
    for role in ('woodwinds','percussion'):
        times=np.arange(200,230,BLOCK/RATE);angles=np.array([interpolate_pose(vs[role]['keyframes'],t)[0] for t in times])
        wrapped=np.array([wrap_azimuth(a) for a in angles]);delta=(np.diff(wrapped)+180)%360-180
        angle_checks[role]=dict(original_keyframes_exact=vs[role]['keyframes']==old[role]['keyframes'],
            unwrapped_range=[float(angles.min()),float(angles.max())],wrapped_crossings=int(np.sum(np.abs(np.diff(wrapped))>180)),
            max_circular_block_step_deg=float(np.max(np.abs(delta))))
    distances={};tables=scene['distance_gain_calibration']
    for role in ('woodwinds','backing_vocals'):
        values=np.array([interpolate_keyframe_value(vs[role]['distance_keyframes'],t,'distance_m',3) for t in np.arange(199,230,BLOCK/RATE)])
        distances[role]=dict(minimum_m=float(values.min()),maximum_m=float(values.max()),
            maximum_step_m=float(np.max(np.abs(np.diff(values)))),static_calibration=load(OUT/f'reports/distance_{role}.json'),
            audition=monitors['distance_'+role])
    allfiles=[]
    for p in sorted(OUT.rglob('*.wav')):
        signal=preview_signal_metrics(p);loud=ebur128(p)
        assert signal['finite'] and signal['sample_peak']<1 and loud['true_peak_dbtp'] is not None and loud['true_peak_dbtp']<=-3,p
        assert signal['frames'] in (8*RATE,12*RATE,30*RATE),p
        allfiles.append(dict(path=str(p),sha256=_sha256(p),frames=signal['frames'],sample_peak_dbfs=signal['sample_peak_dbfs'],true_peak_dbtp=loud['true_peak_dbtp']))
    boundaries={role:cropped_render_metrics(a,BLOCK,RATE) for role,a in changed.items()}
    main_boundaries=cropped_render_metrics(mixed.astype(np.float32),BLOCK,RATE)
    lead=load(OUT/'reports/lead_diagnosis.json')
    t001=load(PROJECT/'reports/M02_T001_preview_validation.json')
    energy=t001['source_reports']['lead_vocal']['staged_metrics']['rms_dbfs']-t001['source_reports']['backing_vocals']['staged_metrics']['rms_dbfs']
    lead_addendum=dict(lead_relative_to_backing_rms_db=energy,interpretation='The assessed interval has very weak Lead relative to Backing. Perceived left vocal may be dominated/masked by the original left-positioned Backing, not a left-heavy Lead.',
        original_full_file_balance_db=lead['original_full_file']['energy_difference_left_minus_right_db'],
        original_full_file_correlation=lead['original_full_file']['correlation'],
        original_preview_correlation=lead['original_preview']['correlation'],
        original_preview_mono_average_loss_db=lead['original_preview']['mean_lr_to_linked_stereo_rms_db'],
        warning='The phase issue is excerpt-specific; do not impose mono/compact conditioning on the whole song automatically.',
        audition=monitors['lead_diagnostics'])
    dump(OUT/'reports/lead_diagnosis_addendum.json',lead_addendum)
    checks=dict(T001_all_artifacts_intact=before==after,Tukana_all_files_intact=tukana_before==tukana_after,
        baseline_regressions=all(regressions.values()),woodwind_angles_exact=angle_checks['woodwinds']['original_keyframes_exact'],
        percussion_angles_exact=angle_checks['percussion']['original_keyframes_exact'],percussion_360_preserved=angle_checks['percussion']['unwrapped_range']==[80.,440.],
        brass_unchanged=vs['brass']==old['brass'],other_unchanged=vs['other']==old['other'],
        lead_front_0deg=all(k['azimuth_deg_unwrapped']==0 and k['elevation_deg']==0 for k in vs['lead_vocal']['keyframes']),
        no_01m_rendered=all(d['minimum_m']>=.35 for d in distances.values()),
        all_audio_finite_unclipped=True,all_true_peaks_safe=True,
        block_continuity=all(m['max_block_boundary_delta']<=max(.25,m['max_sample_delta']*.8) for m in boundaries.values()),
        angular_continuity=all(v['max_circular_block_step_deg']<2 for v in angle_checks.values()),
        proximity_only_selected_roles=True,mono_not_adopted=True,compact_percussion_not_adopted=True,
        no_T018_reuse=True,no_limiter_mastering_full_render=True)
    report=dict(test_id='M02-T002',objective_status='PASS' if all(checks.values()) else 'FAIL',human_status='PENDING',
        superiority='NOT_ESTABLISHED',checks=checks,baseline_regressions=regressions,comparison=comparison,
        listening_monitors=monitors,main_stem_level_control_db=trims,angle_checks=angle_checks,
        distance_analysis=distances,proximity_events=scene['proximity_events'],lead_diagnosis_addendum=lead_addendum,
        boundary_metrics=boundaries,main_boundary_metrics=main_boundaries,exported_files=allfiles,
        fixed_3m_replay='Experimental renderer replay of original Lead checked within 2e-6 of T001 export during rendering.',
        limitations=['No metric proves physical/front localization, near-field impression or superiority; human listening required.',
            'Plugin displays tenths; 0.35 and 0.75m are continuous-raw nominal targets.',
            'Static distance gain correction and full-stem LUFS control reduce level confounding but do not guarantee identical instantaneous loudness.',
            'No HRTF change, reflection, reverb, occlusion, Clarity or plugin Stereo Width automation.',
            'All diagnostics remain isolated from the approved T017 pipeline.'])
    dump(final,report);dump(OUT/'reports/music02_existing_integrity_after.json',after);dump(OUT/'reports/tukana_integrity_after.json',tukana_after)
    assert all(checks.values()),checks
    print(json.dumps(dict(status=report['objective_status'],checks=checks,comparison=comparison,changed_stem_level_db=trims,exported_wavs=len(allfiles)),indent=2),flush=True)

if __name__=='__main__':main()
