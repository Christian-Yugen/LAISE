# LAISE Visualizer V1.3B-R1 — Causal Eligibility & Dominance Integrity

STATUS: PASS. Offline analytical correction only. No commit, push, tag or V1.3C.

## Root cause and narrowly scoped recovery

The original B eligibility mask combined measured audio activity OR intent coverage. Residual RMS therefore admitted sources without a causal intent. The filter already reset outside eligibility, but the upstream mask incorrectly kept those sources eligible. The previous suite checked synthetic ineligible masks and ownership totals without independently joining every source/frame score to actual intent intersections; it therefore missed this integration defect.

`source_features` now separates `audioActive` from intent-only `eligible`. Raw arbitration is gated before filtering; filtered salience and memory are zero outside causal eligibility. Continuation relationships do not grant eligibility. No continuation bridge was invented. An ended source cannot retain a priority through release; future physical waves may continue propagating independently.

Frame fields `audioActiveSources` and `causalActiveSources` distinguish measurement from eligibility; `activeSources` remains a compatibility alias of the latter. Existing schema and ten numerical columns remain intact. Measured descriptors, including persistence calculated on the original measured-relevance union, remain exactly unchanged; persistence alone cannot grant eligibility.

All original 505 intents, 2,583 gesture references, 10,282 attacks/unique owners, relationships and 12 sources are preserved. Full-track tests compare topology and every measurement column against the rollback snapshot. Absolute/source-relative/track-relative/local intensity, novelty, persistence and visualEnergyCandidate are unchanged. No source priority or per-stem gain introduced. Common P95 calibration unchanged: `{"commonFluxP95": 8.935e-06, "commonRmsP95": 0.005356348549999996, "meaning": "common robust scale, no peak reference and no per-source gain applied", "sourceRmsP95": {"backing_vocals": 0.009132155, "bass": 0.004479926, "brass": 1.9701e-05, "drums": 0.006631926, "guitar": 0.000490435, "keyboards": 0.00061288, "lead_vocal": 0.006036722, "other": 0.001476863, "percussion": 0.007998184, "strings": 0.000388275, "synth": 0.003778825, "woodwinds": 0.004646464}}`.

All analysis parameters, weights and arbitration formulas are unchanged: novelty .15, rhythm .10, persistence .10, isolation .10; attack 40 ms, release 120 ms, hysteresis 8%, hold 150 ms, strong-change ratio 1.5, tie 1%. Only causal gating and its downstream arbitration consequences change.

## Full-track independent audit

6,600 windows × 12 sources = 79,200 rows. The independent auditor reconstructs interval ownership at integer microseconds without importing producer masking/arbitration. It checks dominant → actual active intent → gesture → feature/attack evidence → hashed stem → T007. Source hashes are independently rechecked by `sanity-checks.json`. New regression tests failed before the fix (`regression-before.txt`) and pass after it.

| Invariant violation | Before | After |
|---|---:|---:|
| inactiveSourceWithArbitrationSalience | 909 | 0 |
| inactiveSourceWithRawSalience | 909 | 0 |
| inactiveSourceWithFilteredSalience | 909 | 0 |
| inactiveSourceWithSupportingRole | 83 | 0 |
| inactiveSourceWithSecondaryRole | 17 | 0 |
| inactiveSourceWithDominantRole | 2 | 0 |
| zeroIntentFramesWithDominant | 1 | 0 |
| orphanDominants | 2 | 0 |
| activeIntentListMismatch | 0 | 0 |
| causalSourceListMismatch | 0 | 0 |
| framesWithInactiveRawSalience | 830 | 0 |
| framesWithInactiveNonBackgroundRole | 89 | 0 |
| inactiveNonBackgroundRecords | 102 | 0 |

329.90–329.95: no intents, zero raw/filtered arbitration salience and zero dominants for all sources. Brass no longer dominates.

329.95–330.00: only `backing_vocals:i00068` is eligible. Its measured/filtered salience produces dominance under the unchanged formula; score `0.020418323`. Other sources remain background/zero arbitration. Backing vocals was not forced or given instrument priority.

## Dominance runs and limits

737 maximal runs including empty sets; 381 nonempty runs at most 200 ms. Full duration distribution (nonempty):

| Duration ms | Runs |
|---:|---:|
| 50 | 78 |
| 100 | 69 |
| 150 | 121 |
| 200 | 113 |
| 250 | 69 |
| 300 | 45 |
| 350 | 43 |
| 400 | 37 |
| 450 | 22 |
| 500 | 21 |
| 550 | 9 |
| 600 | 8 |
| 650 | 5 |
| 700 | 1 |
| 750 | 4 |
| 800 | 1 |
| 850 | 6 |
| 900 | 10 |
| 950 | 4 |
| 1000 | 6 |
| 1050 | 1 |
| 1100 | 2 |
| 1150 | 3 |
| 1250 | 1 |
| 1300 | 4 |
| 1350 | 2 |
| 1400 | 1 |
| 1450 | 1 |
| 1500 | 2 |
| 1550 | 2 |
| 1600 | 5 |
| 1650 | 1 |
| 1700 | 3 |
| 1750 | 1 |
| 1850 | 2 |
| 1900 | 3 |
| 1950 | 1 |
| 2150 | 4 |
| 2200 | 1 |
| 2350 | 4 |
| 2400 | 1 |
| 2500 | 1 |
| 2700 | 2 |
| 2800 | 1 |
| 3650 | 1 |
| 3750 | 1 |
| 4250 | 1 |
| 4300 | 1 |
| 4400 | 1 |
| 4600 | 1 |
| 4650 | 1 |
| 4950 | 1 |
| 5000 | 1 |
| 5950 | 1 |
| 6750 | 1 |
| 7650 | 1 |
| 9050 | 1 |

Short-run evidence counts (overlapping labels): `{"50ms-grid-quantized": 381, "causal-owner-ended": 2, "causally-owned-co-dominance-under-existing-tie-hysteresis-rule": 105, "measured-attack-within-50ms-not-proof-of-musical-importance": 355, "near-tie-threshold-sensitive": 25, "strong-change-bypass": 16}`. Overall 56 strong-change bypass frames and 134 multi-source tie-candidate frames. Examples:

- 53.35–53.40 s: percussion; strong-change-bypass. Full owner, measured RMS/salience delta and attack evidence: `dominance-runs.json`.
- 11.75–11.95 s: drums, percussion; causally-owned-co-dominance-under-existing-tie-hysteresis-rule. Full owner, measured RMS/salience delta and attack evidence: `dominance-runs.json`.
- 51.05–51.10 s: bass, percussion, synth; near-tie-threshold-sensitive. Full owner, measured RMS/salience delta and attack evidence: `dominance-runs.json`.
- 269.75–269.80 s: drums; causal-owner-ended. Full owner, measured RMS/salience delta and attack evidence: `dominance-runs.json`.

All short dominant episodes have causal owners and measured evidence. A nearby attack supports temporal correspondence, not proof that the set change is perceptually important. Co-dominance is permitted by the unchanged tie/hysteresis rule; it is not a source-count cap. Near-tie flags identify a 0.002 relative neighborhood around the 1% tie boundary, solely for audit. The complete 50 ms grid quantizes all run lengths; proximity to a threshold can cause short set changes. A threshold artifact versus a musically meaningful change cannot be conclusively labeled from these descriptors alone. These cases remain explicit listening-review candidates, with exact attacks, active owners, before/after RMS and scores, tie candidates, inactive incumbents and bypass decisions recorded per run. No smoothing or threshold was tuned to erase short runs.

Future contract: **roleCode is a priority/arbitration annotation, never a binary visual gain switch.** Continuous intensity and salience must drive future behavior. **visualEnergyCandidate = (I/R)^2 is relative energy, not mesh height; V1.3C must perform perceptual/dynamic calibration before mapping to Y.** Both rules are also in artifact metadata.

## Determinism and regressions

- Two independent complete analyses: byte-identical JSON; paired summaries, distributions, sensitivity and decision traces also identical. SHA-256: `d0e7857f927ac7e0946995c60eb6f096aaed5b351b42fd13030b512bc2a581df`.
- 152 tests PASS: 78 JavaScript + 74 Python (138 existing + 14 R1). Existing test source files unchanged.
- Production build PASS; git diff --check PASS. Existing bundle-size warning remains informational.
- Full real 330 s playback: 10,282/10,282 unique; zero dropped, duplicate or unexpected reset. `real-run-v13br1.json`.
- Main visual pixel-identical against approved V1.2 baseline at 0, 46.5 and 200.5 s: `pixel-regression.json`.
- V1.3A/T007/features and V1.2 protected files/hashes intact. No consumer of the intent JSON added to runtime.
- RippleField, ±2.8, camera, mesh, HUD, audio, composition and playback controls unchanged.

## Files and evidence

Behavior changes: `tools/musical_salience.py`, `tools/build_musical_visual_intents.py`, generated `public/audio/tukana-musical-visual-intents-v1.json`.

Added audit/testing tools: `tools/causal_eligibility_audit.py`, `tools/audit_causal_recovery.py`, `tools/validate_causal_playback_regression.py`, `tools/finalize_causal_recovery_evidence.py`, `tools/report_causal_recovery.py`, `tests/test_causal_eligibility.py`.

Evidence folder: `reports/v1_3br1-causal-eligibility/`. Original B snapshot and byte hashes: `before/` and `rollback.json`. Current B deterministic-test aliases were refreshed to corrected R1 evidence; original tests were not weakened. The old B report is historical and superseded by this R1 report for causal validity.

Protected artifact SHA-256 values:

- `index.html`: `e891a183ce0944bc5cf84b0de33fac7030e06fd182dc05a7e73578745810d967` (MATCH)
- `src/style.css`: `f4001a9fd55a73c30072ef3ed843c2ae5da078f568fdda09cd15cbb8875c1343` (MATCH)
- `src/audio-motion-recovery.js`: `2a9939775cbd54c0025eca3c594a69ae0d3324bfbc1d2dd882d24836abc05e21` (MATCH)
- `src/ripple-field.js`: `3525e4ee424a4af054be7195129dc6c458b1132412b46921ef6b42e9f7a03f50` (MATCH)
- `public/audio/TUKANA02_FINAL_MASTER_PCM24_48k.wav`: `4f4d46a870faf29fa51867450a5a70cc82faad1b863d83bd40e89c6d27a3e271` (MATCH)
- `public/audio/tukana-stem-cues.json`: `c880676240a480f72cf3dc42fc5b3a656bd38fd466a79474698abd81b99e944c` (MATCH)
- `public/audio/tukana-visualizer-manifest.json`: `d9e30acd15b532ce44e7a05ee3cffcf22c1e602e55623018ae9b241065e9f62d` (MATCH)
- `src/main.js`: `3bd2219c7cb6fdbb8d5de51bb3f1f2c614815f92db2d70d312601e7a2c12e65e` (MATCH)
- `src/audio-cue-timeline.js`: `27815f5567dcd02eb78283f524eabeeff953d87e32e101da8c3e59c1e3ce4ced` (MATCH)

Scope: only offline audio-evidence → intent eligibility → salience/arbitration integrity. No artistic tuning or renderer changes. PASS establishes causal consistency and regression preservation, not musical-ground-truth classification or future rendered perceptual legibility.
