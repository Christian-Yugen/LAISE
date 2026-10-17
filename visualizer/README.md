# LAISE Visualizer

Vite + Three.js visualizer for **Tukãna — A Mata se Move**. The approved master
is the only audible source. The surface follows measured attacks from its 12
aligned T007 spatial stems, while free edges reflect and dissipate the waves.

## Run

Place the approved `TUKANA02_FINAL_MASTER_PCM24_48k.wav` in `public/audio/`.
Audio assets are deliberately excluded from Git. The expected master SHA-256 is
`4f4d46a870faf29fa51867450a5a70cc82faad1b863d83bd40e89c6d27a3e271`.

```powershell
cd visualizer
npm ci
npm run dev
npm run build
```

## Controls

In `src/main.js`:

- `TERRAIN`: surface width, depth and maximum wave height.
- `MESH_ANGLES`: horizontal, vertical and lateral rotations, in degrees.
- `SCREEN_POSITION`: horizontal/vertical pixel offset; positive means right/down.
- `CAMERA.span`, `CAMERA.elevation`, `CAMERA.distance`, `CAMERA.widthTarget`: orthographic composition.
  `frameTerrain()` preserves approved width and anchors the base FRONT above the listener.

In `src/ripple-field.js`, `RIPPLE_SETTINGS` controls propagation speed, damping,
edge damping, restoring force and impulse intensity. Camera and surface pose
remain fixed during animation; only local vertex heights change.

## Stem synchronization

`public/audio/tukana-stem-cues.json` is the committed visual cue asset; the browser
does not need to load or mix the stems. Each cue contains a detected attack time,
absolute RMS-derived strength and a position projected from the T007 spatial
automation. A common amplitude reference preserves differences between sources.
Attack analysis uses an 8 ms hop and adaptive multiband spectral flux, rejecting
timbre changes without an amplitude attack. This is automatic attack detection,
not a manually verified transcription of every musical note.

`src/audio-cue-timeline.js` schedules cues against the master's playback clock,
including multiple attacks within one rendered frame. Pause flushes pending
attacks; seeking clears prior waves; background jumps discard stale cues.
Reflections and interference continue after their originating audio attack.

To regenerate cues, run from the repository root with Python, NumPy and FFmpeg:

```powershell
python visualizer/tools/build_audio_cues.py
```

This requires the local project assets in
`projects/tukana_02_a_mata_se_move/experiments/TUK2_T007/`, plus the T009 delivery
validation report. The generator checks master identity and stem duration and
records source hashes. It does not change audio files or rendering project data.

## Validation

Run from the repository root:

```powershell
node --test visualizer/tests/ripple-field.test.js visualizer/tests/audio-cue-timeline.test.js
python -m unittest discover -s visualizer/tests -p test_attack_analysis.py
node visualizer/tools/validate_cue_track.mjs
```

Browser checks require local Vite on port 5173, Chrome and Python Playwright:

```powershell
python visualizer/validate_stem_sync.py
python visualizer/validate_ripples.py
python visualizer/validate_terrain.py
```

The committed reports in `validation-stem-sync/` cover the full 330-second cue
simulation and browser checks of two musical passages. Backups and intermediate
screenshots/recordings remain local and are not required to build the app.

## V1.1R1 — Stabilization & Data Integrity

Duration is synchronized from the media element immediately and on
`loadedmetadata` / `durationchange`. Technical HUD values now come from
`public/audio/tukana-visualizer-manifest.json` (schema
`laise-visualizer-manifest-v1`). A metadata failure displays neutral values and
`UNAVAILABLE`, logs an error, and does not block playback when master/cues work.

Regenerate only this manifest from the approved local reports and assets:

```powershell
python -B visualizer/tools/build_visualizer_manifest.py
```

The aggregator reads T008R1 mastering metrics, T009 delivery/format data, and the
T007 manifest/stem references in the existing cue asset. It verifies their
hashes and writes only the technical manifest. Track title, master label,
version and READY/OFFLINE labels are explicit display configuration in that
generator, not new measured quantities. T009 PASS plus its release state maps
to VALIDATED. `provenance` records input paths and hashes. The browser validates
the schema, fields, ranges, status and master URL, **not the full WAV SHA-256**;
that hash is checked offline by the generator. Runtime duration uses the audio
element, not the manifest's duration field.

Unlit materials remain unchanged. Ineffective PointLights and their exclusive
bass/intensity computations were removed; FFT, ENERGY and bloom remain intact.

Run the complete unit suite and build:

```powershell
node --test visualizer/tests/*.test.js
python -B -m unittest discover -s visualizer/tests -p "test_*.py"
cd visualizer
npm run build
```

`tools/validate_stabilization.py before|after` records controlled 1920×1080
captures, tests playback/seek/duration and verifies that manifest failure does
not block audio. The `before` mode uses the recorded pre-stabilization local
snapshot; it requires that snapshot and is evidence tooling, not an application
dependency. Controlled captures freeze the clock and seed particle creation;
the musical sample injects the unchanged cues from 46 to 48 s. Live playback is
tested separately without frozen animation. Evidence is written under
`reports/v1_1r1-evidence/`.

## LAISE Visualizer V1.2 - APPROVED

Final approved baseline: R3B composition, automatic R1 Audio Motion Recovery and
R3B-R1 Playback Continuity Recovery. The physical domain is 16x16 with 128x128
segments, yaw 45 degrees and an OrthographicCamera at 16 degrees elevation.
At 1920x1080 the field base is 1682.861971 px wide; FRONT is Y=870, eight pixels
above the listener. The negative deformation envelope may pass behind existing
listener/HUD overlays and, at large viewports, below the viewport edge.
The camera remains fixed during playback. No instrument-specific behavior.

The media clock drives cue processing. Render stalls trigger deterministic
catch-up, never inferred seek or discarded cues. Explicit seeks start a new
epoch, clear the field and resynchronize to the destination. Ended flushes the
last played interval. Physical equations, cues, master, manifest, R1 calibration,
colors, particles and bloom remain preserved.

Validation: 78 JavaScript + 4 Python unit tests PASS; production build PASS;
90 synthetic stall cases and full-track stress/equivalence PASS. Three normal
330 s playbacks and a fourth with injected stalls each applied 10,282/10,282
unique cues with zero dropped, duplicate or unexpected reset.

From the visualizer directory:

```powershell
node --test tests/*.test.js
python -B -m unittest discover -s tests -p "test_*.py"
node tools/audit_playback_continuity.mjs
npm run build
```

With Vite on localhost:5173 and Chrome/Playwright installed,
`tools/validate_playback_continuity.py` repeats the four real playbacks and controls.
`tools/verify_continuity_freeze.py` checks protected files and seeded normal PNGs
against the minimal `tests/fixtures/r3b-pre-continuity` fixture. The WAV is local
and intentionally ignored; its expected hash is recorded in the technical report.

Evidence: `reports/LAISE_VISUALIZER_V1_2B_R3B_R1_PLAYBACK_CONTINUITY_RECOVERY.md`
and `reports/v1_2br3b_r1-playback-continuity/`. Historical working backups,
exploratory renders and older phase validators remain local. No V1.3 changes.
