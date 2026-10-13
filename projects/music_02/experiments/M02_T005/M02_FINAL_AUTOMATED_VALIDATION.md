# LAISE — MUSIC 02: M02_FINAL_AUTOMATED_VALIDATION

## Resultado em português

**T005 validada tecnicamente; T004 foi selecionada automaticamente.** O preview T004 marcou 71,17 pontos, contra 68,25 da T003. A cena completa marcou 71,89 pontos nas métricas espaciais automatizadas.

A master C (refinada pelo método T017/B2) venceu com 97,84 pontos. O WAV PCM24 tem 247,600 s, 48 kHz, −17,2 LUFS e −2,0 dBTP. O AAC 256 kb/s passou na segurança de arquivo e true peak, mas sua assinatura espacial caiu **10,02 pontos** em relação ao WAV (98,58 → 88,56). Essa perda está registrada; para maior fidelidade espacial, prefira o WAV.

O render integral inclui 11 stems binaurais, uma comparação dry, cena espacial e manifesto de automação. Os testes verificaram os 504 probes, nove seções e integridade de T001–T004 e Tukãna. **A validação descreve métricas técnicas deste sistema; não promete percepção universal.** A regressão final passou. Detalhes, hashes e limites abaixo.

**TECHNICAL FINAL: PASS, WITH THE MEASURED AAC SPATIAL-SIGNATURE LOSS DISCLOSED.**

The automated selection chose **T004**. The full binaural scene passed its spatial and file-integrity checks. Master C (the refined T017-style candidate) won the measured master score. AAC safety passes; the AAC spatial-signature score falls materially relative to its WAV, so the WAV remains the reference delivery. This report does not claim universal human perception.

## Selected outputs

- Final binaural master, PCM24/48 kHz: [MUSIC02_FINAL_binaural_master_PCM24_48k.wav](final/MUSIC02_FINAL_binaural_master_PCM24_48k.wav)
- AAC, 256 kb/s: [MUSIC02_FINAL_binaural_master_AAC_256k.m4a](final/MUSIC02_FINAL_binaural_master_AAC_256k.m4a)
- Full dry comparison, PCM24/48 kHz: [MUSIC02_FINAL_dry_comparison_PCM24_48k.wav](final/MUSIC02_FINAL_dry_comparison_PCM24_48k.wav)
- Pre-master binaural and dry WAVs: [binaural](renders/M02_full_binaural_premaster_24bit.wav), [dry](renders/M02_full_dry_premaster_24bit.wav)
- Eleven full-length PCM24 spatial stems: [spatial stems folder](spatial_stems/full_pcm24)
- Selected scene: [M02_final_spatial_scene.json](spatial_scenes/M02_final_spatial_scene.json); [automation manifest](spatial_scenes/automation_manifest.json)

The PCM24 master is 247.600 s, 48 kHz stereo, 11,884,801 frames, -17.2 LUFS, -2.0 dBTP, LRA 6.9 LU and crest 17.28 dB. SHA-256: `e5342108bb9de47aaabe2c111681f8055b714130a17356198a8e328c50f3ed17`. AAC SHA-256: `16c138554e08f3b753ac9dc7303bca98fa93ca7b02b5f234e02c5667d576992b`. Dry comparison SHA-256: `6901602648f6ac737f6635da85db2730592687629ab6198f92df1768e4df9d52`.

## Spatial candidate selection

The locked preview score selected T004 from T001, T002, the original-lead control, T003 and T004. Scores use 25% spatial discriminability, 20% clarity, 15% orbit, 10% front/back, 10% elevation, 10% transient preservation, 5% peak safety and 5% mono stability.

| Candidate | Score | Spatial separation | Clarity | Transient preservation |
|---|---:|---:|---:|---:|
| T001 | 65.21 | 57.40 | 73.24 | 85.30 |
| T002 | 65.10 | 54.89 | 73.25 | 85.30 |
| T002_ORIGINAL_LEAD | 64.89 | 55.20 | 73.21 | 85.30 |
| T003 | 68.25 | 63.21 | 72.82 | 89.77 |
| T004 | 71.17 | 65.05 | 73.76 | 88.12 |

T004 scored 71.17; T003, the runner-up, scored 68.25, a 2.92-point margin. No hybrid was produced. Independent full-length binaural QA scored **71.89/100**. This is an aggregate technical proxy; it is not the same measure as the 30-second candidate comparison.

## Probes and binaural measurements

The installed dearVR PRO 2 was characterized with **504** native 256-frame renders of one deterministic mono broadband reference: 12 azimuths (0°, ±30°, ±60°, ±90°, ±120°, ±150°, 180°), six elevations (−45°, −20°, 0°, +20°, +45°, +60°) and seven radii (0.35, 0.5, 0.75, 1, 1.5, 2, 3 m). A separate temporal half of the same noise is used as a holdout; it is not an independent HRTF or listener dataset.

The probe classifier measured front/back 100.0% and elevation-band 100.0% accuracy, median angular error 0.0° and 28 feature-redundant grid pairs at its documented threshold. Accuracy is perfect on this controlled probe set; it must not be read as perfect musical-source or human localization. T004 has 1 technically redundant home pair among its 11 sources.

Per-stem and full-section features include global and six-band ILD, GCC-PHAT ITD, L/R correlation, per-band coherence and phase, spectral contrast, channel energy centroids, Side/Mid ratio, binaural difference, width, crest and transient proxies. Pair scores include angular/elevation distance, spectral and temporal overlap, envelope similarity, ILD/ITD differences and feature distance. Masking, vocal clarity and transient indices remain engineering estimates.

The 360° test passed geometric wrapping and sector progression. On the actual full-length output, same-content static probes gave an ILD progression correlation of **0.9980**, with median paired feature distance **0.610**. T004 starts at approximately 85° and visits the required eight sectors in a cyclic rotation. All nine mapped sections received pair/onset measurements.

## Near-field, compactness and clarity

The 0.35–3 m probe library shows distance acts predominantly as gain for the tested broadband and musical probe. Distance adds no score bonus. The selected scene uses T004's partial compensation only at chosen events; the three policies were measured for local loudness, peak, crest, transient, spectral and binaural-feature changes. Near-field perception is not claimed as proved.

Side reductions for Percussion, Woodwinds, Brass and Backing were measured against original stereo. No tested compact variant met the preset improvement and transient criteria, so no extra compactness was added. Lead, Drums and Bass remain protected anchors. The section analysis applies only small linked support trims and turn-taking; it applies no arbitrary global EQ, independent channel normalization, or widening.

## Full render and integrity

The 11 stems were rendered independently to float32 at 48 kHz, preserving the exact timeline of **11,884,801 frames / 247.600020833 s**. Wet/dry comparison uses a common RMS relationship; no mastering was applied until spatial QA passed.

Full-render checks: eleven_independent_roles: PASS; frame_equality: PASS; full_duration_frames: PASS; timeline_origin_0: PASS; no_activity_trimming: PASS; finite_unclipped: PASS; true_peak_headroom: PASS; dc_safe: PASS; no_detected_block_clicks: PASS; exact_full_stem_delivery: PASS; dry_rms_matched: PASS; approved_cached_renderer_equivalence: PASS; all_sections_measured: PASS

Full mix metrics: -23.2 LUFS; -5.9 dBTP; RMS -25.2 dBFS; crest 19.24 dB; L/R balance 0.61 dB; L/R correlation 0.696; mono-fold change -0.72 dB. True-peak headroom and no detected unusual block-boundary clicks passed. Spatial and masking reports are at [full-render validation](reports/full_render_validation.json), [orbit/onset supplement](reports/full_spatial_supplement.json), and [nine section reports](reports/full_sections).

All **310** pre-existing MUSIC 02 files and **79** Tukãna files match recorded SHA-256, size and modification time. The approved T017 baseline remains unchanged. Integrity registers: [MUSIC 02](reports/music02_integrity_before.json), [Tukãna](reports/tukana_integrity_before.json).

## Master selection and AAC result

| Master | Master score | Integrated LUFS | True peak dBTP | AAC spatial score | Eligible |
|---|---:|---:|---:|---:|---|
| A | 96.88 | -19.3 | -2.0 | 88.52 | True |
| B | 97.78 | -16.9 | -2.0 | 88.19 | True |
| C | 97.84 | -17.2 | -2.0 | 88.56 | True |

Master C scored 97.84 and won by 0.061 points over B. Its selected PCM WAV spatial-integrity score is 98.58; the AAC 256 kb/s round-trip score is 88.56, a loss of **10.02 points**. The same direction occurs for A (11.45 points) and B (10.24 points), so it is an encoder-format limitation, not a reason to misstate the selected WAV's score. The original mastering report retains its conservative `False` check at 90 and `status: FAIL`; no measurement was concealed or rewritten. The user requested that significant AAC degradation be reported, and this loss is documented here and in [mastering QA](reports/mastering_validation.json).

The T017/B2-inspired process compared transparent gain, optimized loudnorm and a modest refined candidate. The refinement gate passed spatial-signature, transient, clarity and safety checks; C was selected by the documented score. No widening, new spatial processing, aggressive M/S, or independent-channel gain was used after the binaural render. Final artifacts and checksums are recorded in [mastering validation](reports/mastering_validation.json) and [final decision](reports/technical_final_decision.json).

## Automated regression and limits

The final regression rechecks all 504 probe hashes/headers, all 11 full-length stems, final PCM24/WAV/AAC hashes and formats, all full-render assertions, the selected candidate/master ordering, and before/after hashes of T001–T004/Tukãna: [regression result](reports/M02_T005_final_regression.json).

Scores characterize this exact dearVR build and deterministic probe. They cannot prove that every listener will localize every instrument, find it natural, or experience a source as close. Musical spectra can fall outside the broadband classifier's training distribution. AAC retains a lower measured spatial signature than the selected WAV. No universal-perception claim is made.
