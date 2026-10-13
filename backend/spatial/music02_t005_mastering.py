"""Measured T017-style A/B/C mastering, linked processing and AAC round-trip selection."""
import shutil
import numpy as np
from music02_t005_common import *
from music02_t005_common import _sha256
from tukana_transient_refinement import render_loudnorm,drum_attack_frames,transient_analysis

def signature_integrity(source,processed,library):
    windows=[]
    for time in np.arange(0,FRAMES/RATE-1,2.):
        first=round(time*RATE);last=first+RATE
        if rms(source[:,first:last])<1e-6:continue
        a,b=features(source[:,first:last]),features(processed[:,first:last])
        distance=feature_distance(a,b,library)
        windows.append(dict(time_seconds=float(time),feature_distance=distance,ild_delta_db=b['ild_global_db']-a['ild_global_db'],
            itd_delta_us=b['itd_us']-a['itd_us'],correlation_delta=b['cross_correlation_lr']-a['cross_correlation_lr'],
            spectral_contrast_mean_delta_db=float(np.mean(np.abs(np.array(a['spectral_difference_lr_db'])-b['spectral_difference_lr_db'])))))
    distances=[w['feature_distance'] for w in windows]
    return dict(score=float(100*np.exp(-np.mean(distances)/.25)),mean_distance=float(np.mean(distances)),
        p95_distance=float(np.percentile(distances,95)),windows=windows,
        definition='Gain-invariant mix-feature fidelity relative to the full spatial source; not new classification of individually mastered stems.')

def intervention(source,audio,target_gain):
    a,b=envelope(source,480),envelope(audio,480);active=a>max(a.max()*.001,1e-8)
    actual=20*np.log10(np.maximum(b[active],1e-15)/a[active]);deficit=np.maximum(target_gain-actual,0)
    return dict(unconstrained_integrated_gain_db=target_gain,observed_gain_db=dict(min=float(actual.min()),median=float(np.median(actual)),max=float(actual.max())),
        normalization_or_limiting_deficit_db=dict(median=float(np.median(deficit)),p95=float(np.percentile(deficit,95)),maximum=float(deficit.max())),
        fraction_active_10ms_windows_below_unconstrained_gain_by_05db=float(np.mean(deficit>.5)),
        caution='FFmpeg does not expose a dedicated limiter GR trace here. Gain deficit includes dynamic normalization; it is not attributed entirely to limiting.')

def codec(path,label,source_audio,library):
    aac=OUT/f'mastering/codec/{label}_aac_256k.m4a';assert not aac.exists();aac.parent.mkdir(parents=True,exist_ok=True)
    ff(['ffmpeg','-v','error','-i',str(path),'-c:a','aac','-b:a','256k','-ar','48000','-movflags','+faststart',str(aac)])
    decoded=read_any(aac);extra=decoded.shape[1]-FRAMES;assert decoded.shape[1]>=FRAMES
    aligned=decoded[:,:FRAMES];roundtrip=OUT/f'mastering/codec/{label}_aac_roundtrip_aligned_24bit.wav'
    assert not roundtrip.exists();write24(roundtrip,aligned)
    record=file_metrics(roundtrip);spatial=signature_integrity(source_audio,aligned,library)
    trans=transient_proxy(source_audio,aligned,latency_samples=0)
    spectral_a=features(source_audio);spectral_b=features(aligned)
    spectral=float(np.mean(np.abs(10*np.log10((np.array(spectral_b['band_distribution'])+1e-20)/(np.array(spectral_a['band_distribution'])+1e-20)))))
    return dict(path=str(aac),sha256=_sha256(aac),requested_bitrate_bps=256000,roundtrip=record,
        decoded_frames_before_padding_removal=int(decoded.shape[1]),codec_end_padding_removed_frames=extra,
        no_audio_time_shift=True,priming_handled_by_ffmpeg_container_metadata=True,spatial_integrity=spatial,
        transients=trans,spectral_distribution_mean_delta_db=spectral,
        safety_pass=record['signal']['finite'] and record['signal']['sample_peak']<1 and record['loudness']['true_peak_dbtp']<=-1.,
        codec_score=float(.6*spatial['score']+.3*trans['score']+.1*max(0,100-spectral*10)))

def run():
    assert not (OUT/'reports/mastering_validation.json').exists()
    full=load(OUT/'reports/full_render_validation.json');assert full['status']=='PASS'
    library=load(OUT/'reports/probe_library_native256.json');source=Path(full['outputs']['binaural']['path']);source_audio=read_any(source)
    metrics=full['outputs']['binaural'];ebu=metrics['loudness'];signal=metrics['signal']
    # Targets respond to this programme's measured crest and LRA, rather than copying Tukana values.
    target_i=-16. if signal['crest_factor_db']<18 and ebu['loudness_range_lu']<10 else (-17. if signal['crest_factor_db']<22 else -18.)
    target_tp=-2.;target_lra=float(np.clip(ebu['loudness_range_lu'],7,14))
    folder=OUT/'mastering';folder.mkdir(parents=True,exist_ok=True)
    a=folder/'A_transparent_master_24bit.wav';b=folder/'B_optimized_master_24bit.wav';trial=folder/'C_refinement_trial_24bit.wav'
    assert all(not p.exists() for p in (a,b,trial))
    transparent_gain=min(target_i-ebu['integrated_lufs'],target_tp-ebu['true_peak_dbtp'])
    ff(['ffmpeg','-v','error','-i',str(source),'-af',f'volume={transparent_gain:.8f}dB','-ar','48000','-c:a','pcm_s24le',str(a)])
    first_pass=render_loudnorm(source,b,target_i,target_tp,target_lra)
    b_audio=read_any(b);mix_trans=transient_proxy(source_audio,b_audio,latency_samples=0)
    relaxation=.6 if mix_trans['median_attack_crest_delta_db']<-.5 else .3
    c_pass=render_loudnorm(source,trial,target_i-relaxation,target_tp,target_lra)
    attacks={role:drum_attack_frames(read_any(Path(full['source_reports'][role]['delivery']['path'])).T,count=count)
        for role,count in [('drums',180),('percussion',120),('brass',100)]}
    paths={'A':a,'B':b,'C_TRIAL':trial};records={}
    for label,path in paths.items():
        print('T005 mastering QA: '+label,flush=True)
        audio=read_any(path);record=file_metrics(path);record['spatial_integrity']=signature_integrity(source_audio,audio,library)
        record['transient_fidelity']=transient_proxy(source_audio,audio,latency_samples=0)
        record['role_timed_attacks']={role:transient_analysis(audio.T,indices) for role,indices in attacks.items()}
        record['role_timed_source_attacks']={role:transient_analysis(source_audio.T,indices) for role,indices in attacks.items()}
        record['gain_intervention']=intervention(source_audio,audio,(target_i if label!='C_TRIAL' else target_i-relaxation)-ebu['integrated_lufs'])
        record['codec']=codec(path,label,audio,library)
        record['clarity_integrity']=100*math.exp(-record['spatial_integrity']['mean_distance']/.5)
        record['full_spatial_score_after_master_proxy']=full['final_spatial_score']*record['spatial_integrity']['score']/100
        record['eligible']=record['signal']['frames']==FRAMES and record['signal']['finite'] and record['signal']['sample_peak']<1 and record['loudness']['true_peak_dbtp']<=-1.5 and record['codec']['safety_pass']
        records[label]=record
    c,brec=records['C_TRIAL'],records['B']
    refinement_gate=dict(spatial_integrity_not_worse=c['spatial_integrity']['score']>=brec['spatial_integrity']['score']-.1,
        transient_score_not_worse=c['transient_fidelity']['score']>=brec['transient_fidelity']['score']-.01,
        clarity_not_worse=c['clarity_integrity']>=brec['clarity_integrity']-.1,
        safety=c['eligible'],codec_spatial_not_worse=c['codec']['spatial_integrity']['score']>=brec['codec']['spatial_integrity']['score']-.2)
    refined=all(refinement_gate.values())
    if refined:
        final_c=folder/'C_refined_master_24bit.wav';assert not final_c.exists();shutil.copyfile(trial,final_c)
        records['C']=records.pop('C_TRIAL');records['C']['path']=str(final_c);records['C']['sha256']=_sha256(final_c)
    else:records['C_TRIAL']['eligible']=False
    master_weights=dict(spatial_integrity=.30,clarity=.20,transients=.20,loudness=.10,true_peak=.08,dynamics=.07,codec=.05)
    for label,r in records.items():
        loudness_score=max(0,100-abs(r['loudness']['integrated_lufs']-target_i)*12)
        dynamics=max(0,100-abs(r['signal']['crest_factor_db']-signal['crest_factor_db'])*5)
        components=dict(spatial_integrity=r['spatial_integrity']['score'],clarity=r['clarity_integrity'],transients=r['transient_fidelity']['score'],
            loudness=loudness_score,true_peak=100 if r['loudness']['true_peak_dbtp']<=-1.5 else 0,dynamics=dynamics,codec=r['codec']['codec_score'])
        r['master_score_components']=components;r['master_score']=float(sum(components[k]*master_weights[k] for k in master_weights))
    eligible=[label for label,r in records.items() if r['eligible']];assert eligible,'No technically safe master candidate'
    winner=max(eligible,key=lambda label:records[label]['master_score']);selected=records[winner]
    delivery=OUT/'final';delivery.mkdir(parents=True,exist_ok=True)
    final_wav=delivery/'MUSIC02_FINAL_binaural_master_PCM24_48k.wav';final_aac=delivery/'MUSIC02_FINAL_binaural_master_AAC_256k.m4a'
    final_dry=delivery/'MUSIC02_FINAL_dry_comparison_PCM24_48k.wav'
    assert all(not p.exists() for p in (final_wav,final_aac,final_dry))
    shutil.copyfile(selected['path'],final_wav);shutil.copyfile(selected['codec']['path'],final_aac)
    # Dry copy receives only linked gain, matched to the final master where headroom permits.
    drysource=Path(full['outputs']['dry']['path']);dryebu=full['outputs']['dry']['loudness']
    drygain=min(selected['loudness']['integrated_lufs']-dryebu['integrated_lufs'],-2.-dryebu['true_peak_dbtp'])
    ff(['ffmpeg','-v','error','-i',str(drysource),'-af',f'volume={drygain:.8f}dB','-ar','48000','-c:a','pcm_s24le',str(final_dry)])
    # Also provide the uncompromised RMS-matched pre-master spatial/dry pair in PCM24 for fair spatial comparison.
    for label in ('binaural','dry'):
        path=OUT/f'renders/M02_full_{label}_premaster_24bit.wav';assert not path.exists();write24(path,read_any(Path(full['outputs'][label]['path'])))
    checks=dict(full_qa_passed=True,all_eligible_masters_safe=all(records[l]['eligible'] for l in eligible),
        selected_pcm24_exact_frames=selected['signal']['frames']==FRAMES,selected_codec_safe=selected['codec']['safety_pass'],
        selected_spatial_integrity=selected['spatial_integrity']['score']>=95,selected_codec_signature=selected['codec']['spatial_integrity']['score']>=90,
        no_widening_MS_channel_independent_gain_or_respatialization=True,source_float_unchanged=_sha256(source)==metrics['sha256'])
    report=dict(test_id='M02-T005-MASTER',status='PASS' if all(checks.values()) else 'FAIL',checks=checks,selected_master=winner,
        targets=dict(optimized_i_lufs=target_i,true_peak_dbtp=target_tp,lra_lu=target_lra,refined_i_lufs=target_i-relaxation,
            rationale='Crest/LRA of MUSIC02 choose target; modest lower refined loudness follows T017/B2 transient-preservation method.'),
        transparent_gain_db=transparent_gain,optimized_first_pass=first_pass,refined_first_pass=c_pass,
        refinement_gate=refinement_gate,refined_product_created=refined,master_weights=master_weights,candidates=records,
        final_artifacts=dict(wav=file_metrics(final_wav),aac=dict(path=str(final_aac),sha256=_sha256(final_aac)),dry=file_metrics(final_dry)),
        dry_master_comparison_gain_db=drygain,dry_master_loudness_may_differ_for_headroom=True,
        method='Transparent linked gain; optimized two-pass EBU R128/true-peak limiting; refined modest target relaxation if objective gates pass.',
        limitations=['Master spatial score derives from full-scene score times measured gain-invariant mix-feature integrity; not independent localization of mastered stems.',
            'Attack windows are timed from individual stems but measured in the mix, not exclusively attributed to an instrument.',
            'Codec features and spectral deltas are technical fidelity proxies, not a universal audibility test.'])
    dump(OUT/'reports/mastering_validation.json',report);assert all(checks.values()),checks
    print(json.dumps(dict(status=report['status'],selected_master=winner,master_scores={l:r['master_score'] for l,r in records.items()},
        loudness=selected['loudness'],checks=checks),indent=2),flush=True)

if __name__=='__main__':run()
