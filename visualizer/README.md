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
- `CAMERA.magnification`: screen size multiplier, constrained to retain margins.

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

**KNOWN LIMITATION:** Full negative terrain envelope framing is deferred to
LAISE Visualizer V1.2 — Spatial Field Composition. V1.1R1 intentionally preserves
the approved camera, pose and geometry; it does not guarantee fit of all −2.8
extremes. No V1.2 behavior is implemented.
