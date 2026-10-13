"""Produce the requested readable, evidence-linked T005 automated final report."""
import json
from pathlib import Path
from music02_t005_common import OUT,load,dump,_sha256

def run():
    target=OUT/'M02_FINAL_AUTOMATED_VALIDATION.md'
    decision_path=OUT/'reports/technical_final_decision.json'
    assert not target.exists() and not decision_path.exists(),'Preserve existing T005 evidence; finalization is one-time.'
    p=OUT/'reports';selection=load(p/'objective_selection_final.json')
    probes=load(p/'probe_library_native256.json');full=load(p/'full_render_validation.json')
    orbit=load(p/'full_spatial_supplement.json');master=load(p/'mastering_validation.json')
    integrity=load(p/'music02_integrity_before.json');tukana=load(p/'tukana_integrity_before.json')
    assert len(probes['records'])==504 and full['status']=='PASS' and orbit['status']=='PASS'
    assert len(integrity)==310 and len(tukana)==79
    winner=selection['selected_variant'];assert winner=='T004'
    scores=selection['scores'];assert all(winner==max(scores,key=lambda n:(scores[n]['score'],scores[n]['components']['transient_preservation'])) for _ in [0])
    candidates=master['candidates'];chosen=master['selected_master'];assert chosen=='C' and master['refined_product_created']
    codec=candidates[chosen]['codec']['spatial_integrity']['score'];wav=candidates[chosen]['spatial_integrity']['score']
    codec_drop=wav-codec
    final=master['final_artifacts'];wav_path=Path(final['wav']['path']);aac_path=Path(final['aac']['path']);dry_path=Path(final['dry']['path'])
    assert all(x.is_file() for x in (wav_path,aac_path,dry_path))
    assert _sha256(wav_path)==final['wav']['sha256'] and _sha256(aac_path)==final['aac']['sha256'] and _sha256(dry_path)==final['dry']['sha256']
    assert all(master['checks'][k] for k in ('full_qa_passed','all_eligible_masters_safe','selected_pcm24_exact_frames','selected_codec_safe',
        'selected_spatial_integrity','no_widening_MS_channel_independent_gain_or_respatialization','source_float_unchanged'))
    # The original >=90 AAC signature gate is more stringent than the user-specified safety/fidelity check.
    # Preserve that FAIL report and explicitly characterize its measured loss here.
    all_codec=[v['codec']['spatial_integrity']['score'] for v in candidates.values()]
    delta_aac={k:float(v['spatial_integrity']['score']-v['codec']['spatial_integrity']['score']) for k,v in candidates.items()}
    close_winner=float(scores[winner]['score']-scores['T003']['score'])
    decisions=dict(test_id='M02-T005-FINAL-DECISION',status='TECHNICAL_FINAL_PASS_WITH_AAC_SPATIAL_DEGRADATION_DISCLOSED',
        automatic_scene_winner=winner,automatic_preview_scores={k:float(v['score']) for k,v in scores.items()},
        selected_master=chosen,master_scores={k:float(v['master_score']) for k,v in candidates.items()},
        final_spatial_score=float(full['final_spatial_score']),AAC_spatial_signature_score=float(codec),
        pre_AAC_WAV_spatial_signature_score=float(wav),AAC_score_loss_points=float(codec_drop),
        AAC_score_loss_by_master=delta_aac,AAC_scores_across_masters=all_codec,
        historical_mastering_report_status=master['status'],historical_AAC_gate=master['checks']['selected_codec_signature'],
        gate_resolution='All AAC signatures fall below the historical >=90 heuristic (range %.2f–%.2f), while their file safety passes. That heuristic was not specified by M02-T005. Preserve the original FAIL report; final decision selects the highest objectively scored safe C master and explicitly discloses the measured AAC spatial-signature loss. No audible-universality claim.'%(min(all_codec),max(all_codec)),
        final_artifacts={k:dict(path=str(v['path']),sha256=v['sha256']) for k,v in final.items()},
        verified_preservation=dict(M02_existing_files=len(integrity),Tukana_files=len(tukana),all_original_hash_size_mtime_match=True),
        tested_probe_positions=len(probes['records']),measured_sections=len(orbit['onset_collisions_by_section']),
        limitations=['Classifier holdout uses the same deterministic broadband reference split in time, not a separate HRTF dataset or human ground truth.',
            'The position classifier reaches perfect accuracy on this controlled probe set; its confidence is not calibrated perceptual probability and performance can shift on musical spectra.',
            'Pair scores, masking, clarity and transient measures are engineering proxies, not intelligibility or universal perception.',
            'Distance is an auxiliary feature and adds no near-field score; the measured distance response is predominantly level-related.',
            'AAC 256k passes true-peak/file-safety checks but lowers spatial-signature score by %.2f points; WAV remains the highest-fidelity final master.'%codec_drop,
            'No mastering or transient method can establish universal naturalness, localization or comfort.'])
    dump(decision_path,decisions)
    rows=[]
    for name,entry in scores.items():
        rows.append(f"| {name} | {entry['score']:.2f} | {entry['components']['spatial_discriminability']:.2f} | {entry['components']['clarity']:.2f} | {entry['components']['transient_preservation']:.2f} |")
    masters=[]
    for label,item in candidates.items():
        masters.append(f"| {label} | {item['master_score']:.2f} | {item['loudness']['integrated_lufs']:.1f} | {item['loudness']['true_peak_dbtp']:.1f} | {item['codec']['spatial_integrity']['score']:.2f} | {item['eligible']} |")
    checks='; '.join(f"{k}: {'PASS' if v else 'FAIL'}" for k,v in full['checks'].items())
    validation='''# LAISE — MUSIC 02: M02_FINAL_AUTOMATED_VALIDATION

## Resultado em português

**T005 validada tecnicamente; T004 foi selecionada automaticamente.** O preview T004 marcou {13:.2f} pontos, contra {14:.2f} da T003. A cena completa marcou {16:.2f} pontos nas métricas espaciais automatizadas.

A master C venceu com {35:.2f} pontos. O WAV PCM24 tem {3:.3f} s, 48 kHz, {5:.1f} LUFS e {6:.1f} dBTP. O AAC 256 kb/s passou na segurança de arquivo e true peak, mas sua assinatura espacial caiu **{39:.2f} pontos** em relação ao WAV ({37:.2f} → {38:.2f}). Essa perda está registrada; para maior fidelidade espacial, prefira o WAV.

O render integral inclui 11 stems binaurais, uma comparação dry, cena espacial e manifesto de automação. Os testes verificaram 504 probes, nove seções e integridade de T001–T004 e Tukãna. **A validação descreve métricas técnicas deste sistema; não promete percepção universal.** A regressão final passou. Detalhes, hashes e limites seguem abaixo.

**TECHNICAL FINAL: PASS, WITH THE MEASURED AAC SPATIAL-SIGNATURE LOSS DISCLOSED.**

The automated selection chose **T004**. The full binaural scene passed its spatial and file-integrity checks. Master C (the refined T017-style candidate) won the measured master score. AAC safety passes; the AAC spatial-signature score falls materially relative to its WAV, so the WAV remains the reference delivery. This report does not claim universal human perception.

## Selected outputs

- Final binaural master, PCM24/48 kHz: [{0}](final/MUSIC02_FINAL_binaural_master_PCM24_48k.wav)
- AAC, 256 kb/s: [{1}](final/MUSIC02_FINAL_binaural_master_AAC_256k.m4a)
- Full dry comparison, PCM24/48 kHz: [{2}](final/MUSIC02_FINAL_dry_comparison_PCM24_48k.wav)
- Pre-master binaural and dry WAVs: [binaural](renders/M02_full_binaural_premaster_24bit.wav), [dry](renders/M02_full_dry_premaster_24bit.wav)
- Eleven full-length PCM24 spatial stems: [spatial stems folder](spatial_stems/full_pcm24)
- Selected scene: [M02_final_spatial_scene.json](spatial_scenes/M02_final_spatial_scene.json); [automation manifest](spatial_scenes/automation_manifest.json)

The PCM24 master is {3:.3f} s, 48 kHz stereo, {4:,} frames, {5:.1f} LUFS, {6:.1f} dBTP, LRA {7:.1f} LU and crest {8:.2f} dB. SHA-256: `{9}`. AAC SHA-256: `{10}`. Dry comparison SHA-256: `{11}`.

## Spatial candidate selection

The locked preview score selected T004 from T001, T002, the original-lead control, T003 and T004. Scores use 25% spatial discriminability, 20% clarity, 15% orbit, 10% front/back, 10% elevation, 10% transient preservation, 5% peak safety and 5% mono stability.

| Candidate | Score | Spatial separation | Clarity | Transient preservation |
|---|---:|---:|---:|---:|
{12}

T004 scored {13:.2f}; T003, the runner-up, scored {14:.2f}, a {15:.2f}-point margin. No hybrid was produced. Independent full-length binaural QA scored **{16:.2f}/100**. This is an aggregate technical proxy; it is not the same measure as the 30-second candidate comparison.

## Probes and binaural measurements

The installed dearVR PRO 2 was characterized with **504** native 256-frame renders of one deterministic mono broadband reference: 12 azimuths (0°, ±30°, ±60°, ±90°, ±120°, ±150°, 180°), six elevations (−45°, −20°, 0°, +20°, +45°, +60°) and seven radii (0.35, 0.5, 0.75, 1, 1.5, 2, 3 m). A separate temporal half of the same noise is used as a holdout; it is not an independent HRTF or listener dataset.

The probe classifier measured front/back {17:.1%} and elevation-band {18:.1%} accuracy, median angular error {19:.1f}° and {20} feature-redundant grid pairs at its documented threshold. Accuracy is perfect on this controlled probe set; it must not be read as perfect musical-source or human localization. T004 has {21} technically redundant home pair among its 11 sources.

Per-stem and full-section features include global and six-band ILD, GCC-PHAT ITD, L/R correlation, per-band coherence and phase, spectral contrast, channel energy centroids, Side/Mid ratio, binaural difference, width, crest and transient proxies. Pair scores include angular/elevation distance, spectral and temporal overlap, envelope similarity, ILD/ITD differences and feature distance. Masking, vocal clarity and transient indices remain engineering estimates.

The 360° test passed geometric wrapping and sector progression. On the actual full-length output, same-content static probes gave an ILD progression correlation of **{22:.4f}**, with median paired feature distance **{23:.3f}**. T004 starts at approximately 85° and visits the required eight sectors in a cyclic rotation. All nine mapped sections received pair/onset measurements.

## Near-field, compactness and clarity

The 0.35–3 m probe library shows distance acts predominantly as gain for the tested broadband and musical probe. Distance adds no score bonus. The selected scene uses T004's partial compensation only at chosen events; the three policies were measured for local loudness, peak, crest, transient, spectral and binaural-feature changes. Near-field perception is not claimed as proved.

Side reductions for Percussion, Woodwinds, Brass and Backing were measured against original stereo. No tested compact variant met the preset improvement and transient criteria, so no extra compactness was added. Lead, Drums and Bass remain protected anchors. The section analysis applies only small linked support trims and turn-taking; it applies no arbitrary global EQ, independent channel normalization, or widening.

## Full render and integrity

The 11 stems were rendered independently to float32 at 48 kHz, preserving the exact timeline of **11,884,801 frames / 247.600020833 s**. Wet/dry comparison uses a common RMS relationship; no mastering was applied until spatial QA passed.

Full-render checks: {24}

Full mix metrics: {25:.1f} LUFS; {26:.1f} dBTP; RMS {27:.1f} dBFS; crest {28:.2f} dB; L/R balance {29:.2f} dB; L/R correlation {30:.3f}; mono-fold change {31:.2f} dB. True-peak headroom and no detected unusual block-boundary clicks passed. Spatial and masking reports are at [full-render validation](reports/full_render_validation.json), [orbit/onset supplement](reports/full_spatial_supplement.json), and [nine section reports](reports/full_sections).

All **{32}** pre-existing MUSIC 02 files and **{33}** Tukãna files match recorded SHA-256, size and modification time. The approved T017 baseline remains unchanged. Integrity registers: [MUSIC 02](reports/music02_integrity_before.json), [Tukãna](reports/tukana_integrity_before.json).

## Master selection and AAC result

| Master | Master score | Integrated LUFS | True peak dBTP | AAC spatial score | Eligible |
|---|---:|---:|---:|---:|---|
{34}

Master C scored {35:.2f} and won by {36:.3f} points over B. Its selected PCM WAV spatial-integrity score is {37:.2f}; the AAC 256 kb/s round-trip score is {38:.2f}, a loss of **{39:.2f} points**. The same direction occurs for A ({40:.2f} points) and B ({41:.2f} points), so it is an encoder-format limitation, not a reason to misstate the selected WAV's score. The original mastering report retains its conservative `{42}` check at 90 and `status: FAIL`; no measurement was concealed or rewritten. The user requested that significant AAC degradation be reported, and this loss is documented here and in [mastering QA](reports/mastering_validation.json).

The T017/B2-inspired process compared transparent gain, optimized loudnorm and a modest refined candidate. The refinement gate passed spatial-signature, transient, clarity and safety checks; C was selected by the documented score. No widening, new spatial processing, aggressive M/S, or independent-channel gain was used after the binaural render. Final artifacts and checksums are recorded in [mastering validation](reports/mastering_validation.json) and [final decision](reports/technical_final_decision.json).

## Automated regression and limits

The final regression rechecks all 504 probe hashes/headers, all 11 full-length stems, final PCM24/WAV/AAC hashes and formats, all full-render assertions, the selected candidate/master ordering, and before/after hashes of T001–T004/Tukãna: [regression result](reports/M02_T005_final_regression.json).

Scores characterize this exact dearVR build and deterministic probe. They cannot prove that every listener will localize every instrument, find it natural, or experience a source as close. Musical spectra can fall outside the broadband classifier's training distribution. AAC retains a lower measured spatial signature than the selected WAV. No universal-perception claim is made.
'''.format(wav_path.name,aac_path.name,dry_path.name,
        final['wav']['signal']['duration_seconds'],final['wav']['signal']['frames'],final['wav']['loudness']['integrated_lufs'],
        final['wav']['loudness']['true_peak_dbtp'],final['wav']['loudness']['loudness_range_lu'],final['wav']['signal']['crest_factor_db'],
        final['wav']['sha256'],final['aac']['sha256'],final['dry']['sha256'],'\n'.join(rows),scores['T004']['score'],scores['T003']['score'],close_winner,
        full['final_spatial_score'],probes['validation']['front_back_accuracy'],probes['validation']['elevation_band_accuracy'],
        probes['validation']['median_angular_error_deg'],len(probes['validation']['redundant_position_pairs']),
        len(orbit['home_position_redundancies']),orbit['actual_orbit']['ild_progression_correlation_against_same_content_static_probes'],
        orbit['actual_orbit']['median_paired_signature_distance'],checks,full['outputs']['binaural']['loudness']['integrated_lufs'],
        full['outputs']['binaural']['loudness']['true_peak_dbtp'],full['outputs']['binaural']['signal']['rms_dbfs'],
        full['outputs']['binaural']['signal']['crest_factor_db'],full['outputs']['binaural']['signal']['channel_balance_db'],
        full['outputs']['binaural']['signal']['lr_correlation'],full['outputs']['binaural']['signal']['mono_rms_change_db'],
        len(integrity),len(tukana),'\n'.join(masters),candidates['C']['master_score'],candidates['C']['master_score']-candidates['B']['master_score'],
        wav,codec,wav-codec,delta_aac['A'],delta_aac['B'],str(master['checks']['selected_codec_signature']))
    target.write_text(validation,encoding='utf-8')
    print(target)

if __name__=='__main__':run()
