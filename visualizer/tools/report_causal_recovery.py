"""Render R1's audited evidence without changing analysis or runtime."""
from pathlib import Path
import html,json
V=Path(__file__).resolve().parents[1];OUT=V/'reports/v1_3br1-causal-eligibility'
def load(n):return json.loads((OUT/n).read_text(encoding='utf-8'))
def main():
 c=load('final-checks.json');assert c['pass'];runs=load('dominance-runs.json');before=load('causal-before.json');after=load('causal-after.json')
 d=json.loads((V/'public/audio/tukana-musical-visual-intents-v1.json').read_text(encoding='utf-8'))
 metrics='\n'.join(f'| {k} | {before["metrics"][k]} | {v} |' for k,v in after['metrics'].items())
 hist='\n'.join(f'| {ms} | {count} |' for ms,count in runs['nonemptyRunDurationHistogramMs'].items())
 protected='\n'.join(f'- `{p}`: `{x["sha256"]}` (MATCH)' for p,x in c['protectedHashes'].items())
 examples=[]
 for label in ['strong-change-bypass','causally-owned-co-dominance-under-existing-tie-hysteresis-rule','near-tie-threshold-sensitive','causal-owner-ended']:
  r=next((r for r in runs['runs'] if r['dominants'] and r['durationMs']<=200 and label in r['evidenceLabels']),None)
  if r:examples.append(f'- {r["startTime"]:.2f}–{r["endTime"]:.2f} s: {", ".join(r["dominants"])}; {label}. Full owner, measured RMS/salience delta and attack evidence: `dominance-runs.json`.')
 text=f'''# LAISE Visualizer V1.3B-R1 — Causal Eligibility & Dominance Integrity

STATUS: PASS. Offline analytical correction only. No commit, push, tag or V1.3C.

## Root cause and narrowly scoped recovery

The original B eligibility mask combined measured audio activity OR intent coverage. Residual RMS therefore admitted sources without a causal intent. The filter already reset outside eligibility, but the upstream mask incorrectly kept those sources eligible. The previous suite checked synthetic ineligible masks and ownership totals without independently joining every source/frame score to actual intent intersections; it therefore missed this integration defect.

`source_features` now separates `audioActive` from intent-only `eligible`. Raw arbitration is gated before filtering; filtered salience and memory are zero outside causal eligibility. Continuation relationships do not grant eligibility. No continuation bridge was invented. An ended source cannot retain a priority through release; future physical waves may continue propagating independently.

Frame fields `audioActiveSources` and `causalActiveSources` distinguish measurement from eligibility; `activeSources` remains a compatibility alias of the latter. Existing schema and ten numerical columns remain intact. Measured descriptors, including persistence calculated on the original measured-relevance union, remain exactly unchanged; persistence alone cannot grant eligibility.

All original 505 intents, 2,583 gesture references, 10,282 attacks/unique owners, relationships and 12 sources are preserved. Full-track tests compare topology and every measurement column against the rollback snapshot. Absolute/source-relative/track-relative/local intensity, novelty, persistence and visualEnergyCandidate are unchanged. No source priority or per-stem gain introduced. Common P95 calibration unchanged: `{json.dumps(d['calibration'],sort_keys=True)}`.

All analysis parameters, weights and arbitration formulas are unchanged: novelty .15, rhythm .10, persistence .10, isolation .10; attack 40 ms, release 120 ms, hysteresis 8%, hold 150 ms, strong-change ratio 1.5, tie 1%. Only causal gating and its downstream arbitration consequences change.

## Full-track independent audit

6,600 windows × 12 sources = 79,200 rows. The independent auditor reconstructs interval ownership at integer microseconds without importing producer masking/arbitration. It checks dominant → actual active intent → gesture → feature/attack evidence → hashed stem → T007. Source hashes are independently rechecked by `sanity-checks.json`. New regression tests failed before the fix (`regression-before.txt`) and pass after it.

| Invariant violation | Before | After |
|---|---:|---:|
{metrics}

329.90–329.95: no intents, zero raw/filtered arbitration salience and zero dominants for all sources. Brass no longer dominates.

329.95–330.00: only `backing_vocals:i00068` is eligible. Its measured/filtered salience produces dominance under the unchanged formula; score `{d['frames'][-1]['values'][d['sourceOrder'].index('backing_vocals')][5]}`. Other sources remain background/zero arbitration. Backing vocals was not forced or given instrument priority.

## Dominance runs and limits

{runs['runCount']} maximal runs including empty sets; {runs['shortNonemptyRunsAtMost200ms']} nonempty runs at most 200 ms. Full duration distribution (nonempty):

| Duration ms | Runs |
|---:|---:|
{hist}

Short-run evidence counts (overlapping labels): `{json.dumps(runs['shortRunEvidenceCounts'],sort_keys=True)}`. Overall {runs['strongChangeBypassFrames']} strong-change bypass frames and {runs['tieFrames']} multi-source tie-candidate frames. Examples:

{chr(10).join(examples)}

All short dominant episodes have causal owners and measured evidence. A nearby attack supports temporal correspondence, not proof that the set change is perceptually important. Co-dominance is permitted by the unchanged tie/hysteresis rule; it is not a source-count cap. Near-tie flags identify a 0.002 relative neighborhood around the 1% tie boundary, solely for audit. The complete 50 ms grid quantizes all run lengths; proximity to a threshold can cause short set changes. A threshold artifact versus a musically meaningful change cannot be conclusively labeled from these descriptors alone. These cases remain explicit listening-review candidates, with exact attacks, active owners, before/after RMS and scores, tie candidates, inactive incumbents and bypass decisions recorded per run. No smoothing or threshold was tuned to erase short runs.

Future contract: **roleCode is a priority/arbitration annotation, never a binary visual gain switch.** Continuous intensity and salience must drive future behavior. **visualEnergyCandidate = (I/R)^2 is relative energy, not mesh height; V1.3C must perform perceptual/dynamic calibration before mapping to Y.** Both rules are also in artifact metadata.

## Determinism and regressions

- Two independent complete analyses: byte-identical JSON; paired summaries, distributions, sensitivity and decision traces also identical. SHA-256: `{c['determinism']['sha256']}`.
- {c['testCounts']['total']} tests PASS: {c['testCounts']['javascript']} JavaScript + {c['testCounts']['python']} Python (138 existing + 14 R1). Existing test source files unchanged.
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

{protected}

Scope: only offline audio-evidence → intent eligibility → salience/arbitration integrity. No artistic tuning or renderer changes. PASS establishes causal consistency and regression preservation, not musical-ground-truth classification or future rendered perceptual legibility.
'''
 (V/'reports/LAISE_VISUALIZER_V1_3B_R1_CAUSAL_ELIGIBILITY_INTEGRITY.md').write_text(text,encoding='utf-8')
 (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>LAISE V1.3B-R1 audit</title><style>body{max-width:1200px;margin:30px auto;font:15px system-ui;line-height:1.5}pre{white-space:pre-wrap}a{margin-right:20px}</style><h1>LAISE V1.3B-R1 — PASS</h1><p><a href="causal-after.json">Full causal audit</a><a href="dominance-runs.json">Every dominance run</a><a href="final-checks.json">Checks</a><a href="determinism.json">Determinism</a></p><pre>'+html.escape(text)+'</pre>',encoding='utf-8')
 print('R1 report written')
if __name__=='__main__':main()
