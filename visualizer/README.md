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
