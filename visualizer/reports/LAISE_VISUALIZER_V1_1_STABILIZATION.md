# LAISE Visualizer V1.1 — Stabilization Report

Revision: V1.1R1. Completed 2026-10-16 (America/Cuiaba).

## Baseline

- Branch: `stabilization/data-integrity`.
- HEAD: `4b39fc5efd5b40b704cef2d47f70223afa4e9a91`.
- Tracked working tree was clean before runtime changes. Existing untracked backups, reports, screenshots and historical versions were preserved.
- The complete technical audit was read in the previous phase. Its camera diagnosis remains valid.
- Rollback snapshot: `visualizer/backups/V1_PRE_STABILIZATION_20261015_235716/`.
- Original interrupted V1.1 report preserved there as `V1_1_PRE_R1_REPORT.md`.
- Baseline: 12 JavaScript tests and 3 Python tests passed, repeated before R1 runtime edits. The previous phase's baseline build passed (17 modules, Vite 8.3.4).
- R1 product decision explicitly removes full negative-envelope correction from the PASS criteria. No V1.2 feature was implemented.

## Correction 1 — Duration

**PASS**

The previous implementation listened only for `loadedmetadata`, which could have fired during preload before registration. A single `syncDurationLabel()` now reads `audio.duration` only if finite and positive and uses the existing `formatTime()` function. It runs immediately after registering `loadedmetadata` and `durationchange`.

No 330/05:30 literal was added to runtime duration logic. Current time, progress and seek code are unchanged. The technical manifest records asset duration for provenance, but does not supply the duration label.

Three new unit tests cover already-available metadata, later metadata, duration changes and invalid/nonpositive values. Browser evidence confirms **05:30** before play, during play, after pause, after seek and after resume, both with valid and unavailable technical metadata. The baseline controlled capture shows 00:00; the after capture shows 05:30.

## Correction 2 — Camera Envelope

**DEFERRED TO V1.2**

CAMERA FULL ±2.8 ENVELOPE:
DEFERRED TO V1.2 BY PRODUCT DECISION

KNOWN LIMITATION:
Full negative terrain envelope framing is deferred to
LAISE Visualizer V1.2 — Spatial Field Composition.

`frameTerrain()`, TERRAIN, CAMERA, SCREEN_POSITION, pose and geometry were not changed. Byte comparisons of the entire camera block and terrain/particle/material construction against the snapshot passed. The current fit still excludes the full negative range; this report does not claim that limitation was fixed.

### Preserved diagnostic calculations from the interrupted phase

These are **in-memory rejected-candidate calculations**, not runtime changes or newly implemented behavior. The candidate considered X={-8,+8}, Z={-6,+6}, Y={-2.8,+2.825}. NDC viewport limits are [-1,+1]. It would fit the full volume but visibly shrink the approved composition. That candidate remains rejected.

| Viewport | Envelope atual: minY / maxY | Candidato: minX / maxX | Candidato: minY / maxY | Largura da base, antes → candidato | Altura da base, antes → candidato |
|---|---|---|---|---|---|
| 1920×1080 | −1.061437 / +0.693844 | −0.687787 / +0.846147 | −0.812000 / +0.593206 | 1675.60 → 1446.47 px (−13.67%) | 408.51 → 323.17 px (−20.89%) |
| 1920×960 | −1.194117 / +0.780575 | −0.603264 / +0.760233 | −0.812000 / +0.593206 | 1675.60 → 1285.75 px (−23.27%) | 408.51 → 287.26 px (−29.68%) |
| 1366×768 | −1.061955 / +0.694183 | −0.657843 / +0.875342 | −0.812000 / +0.593206 | 1192.12 → 1028.60 px (−13.72%) | 290.64 → 229.81 px (−20.93%) |
| 2560×1440 | −1.061437 / +0.693844 | −0.706016 / +0.827918 | −0.812000 / +0.593206 | 2234.13 → 1928.62 px (−13.67%) | 544.68 → 430.89 px (−20.89%) |
| 3840×2160 | −1.061437 / +0.693844 | −0.724245 / +0.809689 | −0.812000 / +0.593206 | 3351.19 → 2892.94 px (−13.67%) | 817.02 → 646.33 px (−20.89%) |

O candidato contém todos os cantos na viewport nas cinco resoluções. Entretanto, o fit afasta a câmera e altera a perspectiva/tamanho da base mesmo em repouso:

| Propriedade | Atual | Candidato apenas em memória |
|---|---|---|
| Posição calculada, nas cinco resoluções | `(0, 7.281008, 22.065013)` | `(0, 10.108336, 29.833034)` |
| Zoom, 1920×1080 / 2560×1440 / 3840×2160 | 1.196283 | 1.4 |
| Zoom, 1920×960 | 1.345819 | 1.4 |
| Zoom, 1366×768 | 1.196867 | 1.4 |


## Correction 3 — Technical Metadata Manifest

**PASS**

Runtime asset: `public/audio/tukana-visualizer-manifest.json`.
Schema: `laise-visualizer-manifest-v1`.
Reproducible aggregator: `tools/build_visualizer_manifest.py`.

The generator only reads approved reports/audio/cues and writes the technical manifest. It does not master audio, regenerate cues, recalculate spatial scores or rewrite project reports. It verifies the actual local master and all 12 stem hashes, T007 manifest hash, agreement of T008R1/T009 mastering metrics, PASS/release state, duration and source uniqueness. A new Python test rebuilds the object in memory, compares it to the saved JSON and verifies that input hashes are unchanged.

### Field provenance

| Fields | Source / transformation |
|---|---|
| `schema_version` | Explicit schema contract in the generator |
| `track`, `master_label` | Approved existing display title and label, explicit generator display configuration |
| `master_url` | Existing cue asset `master.url`, checked at runtime against the unchanged audio src |
| `master_sha256` | T009 WAV artifact, cross-checked with T008R1, cues and actual local WAV |
| `duration_seconds` | T009 WAV `format.duration`, checked against cue duration |
| `sample_rate`, `channels` | T009 WAV `format.sample_rate` and `format.channels` |
| `source_count` | Unique entries in the existing T007-derived cue `stems` array (12); actual source hashes checked |
| `spatial_source` | T007 source identity, established by the checked T007 scene/stem paths and manifest hash |
| `integrated_lufs`, `true_peak_dbtp`, `spatial_integrity` | T008R1 `selected_metrics`, checked against T009 `final_master_metrics` |
| `delivery_status` | T009 status PASS plus `release_state=FINAL_DELIVERY_VALIDATED`, mapped to VALIDATED |
| `delivery_source` | T009 report identity |
| `visualizer_version` | Explicit product/display version V1.1; R1 is the stabilization revision |
| `stems_state` | READY: existing offline cue asset, not browser stem playback |
| `motion_state` | OFFLINE: positions sampled from the T007 automation at attack times, not live spatial tracking |
| `provenance` | Relative paths and SHA-256 of T008R1 report, T009 report, T007 automation manifest and cues |

Full source paths and hashes are recorded in the JSON, rather than duplicated as operational frontend constants.

### Runtime validation and failure behavior

`validateTechnicalManifest()` checks the schema, required strings, master URL equality, SHA-256 syntax, finite numeric types, positive integer source count/sample rate/channels, duration/range and supported states. `renderTechnicalHud()` fills neutral HTML slots only after validation.

**The full WAV hash is not computed or validated in the browser.** The hash is verified offline by the generator. Runtime validation is not a cryptographic guarantee that a WAV at the same URL has remained unchanged.

Technical metadata fetch is independent of `cueReady` and the Play handler. On failure, data slots become `--`, delivery state becomes UNAVAILABLE, associated provenance attributes are cleared and an error is logged. A simulated HTTP 503 verified that playback, seek, ENERGY and waves still work with valid master/cues. No new restrictions were added to audio playback.

### Removed operational hardcodes

The HTML no longer supplies track/master label, LUFS, true peak, spatial integrity, source count, T007 state, delivery status or version claims as literal operational data. Semantic headings and the approved audio src remain unchanged so a metadata outage cannot remove the audio source.

Displayed current values remain -16.90 LUFS, -2.00 dBTP, 97.34, 12 SOURCES, T007 and VALIDATED. False V002 READY claims are replaced by manifest-derived V1.1 READY and V1.1 OFFLINE. ORIGINAL CONCEPT now displays V1.1. These authorized technical text corrections are the only intended HUD text differences beyond duration. No CSS, typography, spacing, layout or color was changed. Delivery source and master URL/hash are also bound as DOM provenance attributes without adding visible UI.

## Correction 4 — Reactive Lights

**PASS**

All active scene materials remain MeshBasicMaterial / PointsMaterial, which do not receive PointLight illumination. The two PointLights, their position/add calls and per-frame intensity assignments were removed. `bandEnergy()` and its bass call were used exclusively by the removed lights and were also removed.

No materials, colors, FFT settings/smoothing, ENERGY computation, bloom, particles, rings, wave physics or cue scheduling were changed. The controlled scene comparison is pixel-identical after normalizing particle randomness, including the musical geometry sample.

## Regression Tests

| Check | Result |
|---|---|
| Existing JavaScript | 12/12 PASS |
| New JavaScript | 11/11 PASS |
| Existing Python | 3/3 PASS |
| New manifest reproducibility Python test | 1/1 PASS |
| `npm run build` | PASS, Vite 8.3.4, 17 modules |
| Browser Play/Pause/Continue/Seek | PASS |
| Duration in all tested player states | 05:30 |
| Manifest outage with playback | PASS, safe HUD + console error, no page exception |
| ENERGY / bloom / particles / wave activity | PASS |
| Controlled idle and musical image pixels | Identical |
| Controlled musical vertex positions | Identical SHA-256 |

Commands from repository root:

```powershell
node --test visualizer/tests/ripple-field.test.js visualizer/tests/audio-cue-timeline.test.js visualizer/tests/stabilization.test.js
python -B -m unittest discover -s visualizer/tests -p "test_*.py"
python -B visualizer/tools/validate_stabilization.py before
python -B visualizer/tools/validate_stabilization.py after
```

Build runs from `visualizer/`: `npm run build`. The pre-existing >500 kB chunk warning remains nonfatal; bundle optimization was outside scope. Output CSS retains its baseline asset name/hash (`index-ZQlKfo3t.css`). No existing test or build failed after the runtime edits.

During authoring, three new duration tests initially could not locate their code boundary because the harness assumed LF on a CRLF file; the harness now normalizes line endings. Image comparison initially required unavailable Pillow; it now decodes/compares pixels in Chrome without installing dependencies. Neither issue required a runtime change.

## Visual Regression

Evidence: `reports/v1_1r1-evidence/`, with before/after JSON and PNGs.

Controlled viewport: 1920x1080, DPR 1, muted Chrome, paused at audio time zero, identical visual clock and deterministic particle seed. The baseline is served from the rollback snapshot by a test-only route; no restored source was written into the running app. The musical sample advances the unchanged timeline from 46 to 48 seconds at 120 steps per second and renders its resulting geometry.

Removing PointLights changes Three.js UUID allocations, which consume Math.random. An initial comparison seeded only page startup and therefore produced different random particle realizations. The final test seeds at the particle creation boundary for both snapshots, isolating this expected nondeterminism. This instrumentation applies only to responses in the isolated test browser. Production particle generation was not changed.

After identical inputs:

- `idlePixelIdentical: true`.
- `musicalPixelIdentical: true`.
- Musical vertex-position SHA-256: `46df9d2e450180474c35eee962799dec632d252960e0f22a21f9f3c83a2aa6c7`, equal before/after.
- Camera position `(0,7.281007851924716,22.065012728625934)`, zoom 1.196283218219135, Euler pose and unit scale match.
- Full HUD captures were visually inspected; duration/version/source-state text corrections are expected. The scene-only pixel assertion excludes HUD data changes.

Separate playback sessions used real animation, without frozen clock/RAF. Normal playback reached approximately 62.50 s after seek/resume, ENERGY 22%, bloom 0.6277 and 42 impulses. Manifest-failure playback also reached approximately 62.50 s, ENERGY 22% and 42 impulses. Both had no page exceptions; normal playback had no console errors, while the simulated outage logged the expected 503 and technical-metadata error.

This is controlled visual/function regression evidence, not perceptual certification of every beat in the complete 330-second song or a cross-device performance benchmark.

## Files Changed

| File | Reason |
|---|---|
| `visualizer/src/main.js` | Duration sync, independent manifest validation/HUD binding, dead PointLight cleanup |
| `visualizer/index.html` | Neutral data slots with stable IDs, same visual structure |
| `visualizer/public/audio/tukana-visualizer-manifest.json` | Versioned technical data and provenance |
| `visualizer/tools/build_visualizer_manifest.py` | Reproducible read-only aggregation of approved sources |
| `visualizer/tools/validate_stabilization.py` | Controlled baseline/after capture and browser regression evidence |
| `visualizer/tests/stabilization.test.js` | 11 duration/manifest/HUD/dead-light tests |
| `visualizer/tests/test_visualizer_manifest.py` | Reproducibility and input-preservation test |
| `visualizer/README.md` | V1.1R1 data contract, verification commands and limitation |
| `visualizer/reports/LAISE_VISUALIZER_V1_1_STABILIZATION.md` | This report, replacing the interrupted-phase result |
| `visualizer/reports/v1_1r1-evidence/*` | JSON/PNG validation evidence |
| `visualizer/backups/V1_PRE_STABILIZATION_20261015_235716/*` | Rollback and preserved previous report/README |
| `visualizer/dist/*` | Ignored production build output |

`git diff --stat` for tracked changes: README +50 lines; index.html 24 changed lines; main.js 142 changed lines; total 141 insertions, 75 deletions. New files above remain untracked and therefore are not counted by that command. Pre-existing untracked files were not staged, deleted or modified.

Diff review found no unintended change to camera, terrainRig, PlaneGeometry, RippleField, colors, bloom, FFT or cue scheduling. Byte comparisons against the snapshot passed for the camera block, terrain/particle/material construction, cue scheduling and wave update function. Hash checks passed for CSS, RippleField, AudioCueTimeline, package files, master and cues. Git diff --check passed (only Git's normal LF/CRLF conversion notices). No commit or push was performed for this phase.

## Rollback

Snapshot: `C:\Projetos2026\LAISE\visualizer\backups\V1_PRE_STABILIZATION_20261015_235716`.
Read `ROLLBACK.md` there. Restore only `index.html`, `src/main.js` and `README.md` from that folder into their corresponding Visualizer paths. The original README was clean at baseline and is preserved from HEAD. Example:

```powershell
Copy-Item -LiteralPath "C:\Projetos2026\LAISE\visualizer\backups\V1_PRE_STABILIZATION_20261015_235716\src\main.js" -Destination "C:\Projetos2026\LAISE\visualizer\src\main.js"
```

Archive the newly created manifest/tests/tools separately if reverting; do not delete unrelated files. Restore the previous report from `V1_1_PRE_R1_REPORT.md` if desired. Rebuild from `visualizer/` after restoration. Do not use reset --hard. The snapshot includes the requested source/package/cue copies and baseline diff/status/hash records, not a duplicate master WAV or dist folder.

## Final State

V1.1 STABILIZATION: PASS

Correction 1: PASS. Correction 2: DEFERRED TO V1.2. Correction 3: PASS. Correction 4: PASS.

The approved appearance and musical systems are preserved under the controlled checks above. Full negative-envelope framing remains a known limitation deferred by explicit product decision. No V1.2 behavior is implemented.
