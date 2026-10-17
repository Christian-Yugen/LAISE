# LAISE Visualizer V1.2B-R3B-R1 - Playback Continuity Recovery

**PASS** - all four complete real playbacks: 10,282/10,282; zero missing, duplicates or unexpected resets. No commit, push, merge or tag.

## Root cause and failing reproduction

Before: main.updateSoundWaves reset RippleField when abs(currentTime-lastTime)>0.3. AudioCueTimeline.step independently interpreted the same forward interval as seek(time), using lower-bound search to discard pending events. This conflated render delay with media discontinuity. A visible-tab 949.952 ms media gap therefore lost attacks. No evidence establishes the underlying cause of that browser stall.

The mandatory 950 ms test was added and run BEFORE the fix. It failed: only the final cue was emitted, instead of all five. Evidence: regression-before.txt. The same test now passes.

```text
BEFORE: media advances -> late RAF -> delta > .3 -> field reset + seek -> cues skipped
AFTER:  media advances -> late RAF -> advance existing physics to each cue timestamp
                                 -> apply stable cue index once -> advance to media target
Explicit seeking/currentTime write/reload/replay -> new epoch + reset/resync
pause -> flush played fraction; idle field may settle; no new musical cues
ended -> flush min(currentTime,duration) before ended presentation/audit completion
```

## Temporal architecture and scope

AudioCueTimeline now exposes mediaTime, simulationTime, lastTime (completed update target), index, playbackEpoch, isSeeking, isPlaying, catchUpCount and largestCatchUpMs. Event metadata includes stable original cue index, epoch, timestamp/simulationTime and media target. The .1 s telemetry boundary is not seek authority and never drops events. Forward gaps have no reset threshold. Backward clock values are not simulated; real media seek/play lifecycle explicitly repositions the timeline.

Catch-up advances the SAME RippleField in intervals <=0.1 s (its existing input clamp), stopping at every cue timestamp before injecting that cue. Physics equations, fixed timestep, kernels, damping, impulse strengths and amplitude calibration remain unchanged. Equal-time cues remain in original array/index order. There are 3,488 adjacent equal-time pairs; no timestamp-keyed deduplication is used.

Seek policy preserves the previous reset-to-flat behavior: explicit seek clears old waves and FFT smoothing, starts one new epoch, suppresses injection while seeking, and resynchronizes lower-bound index at the final seeked destination. Skipped intervals are not replayed. Cues at the destination are eligible. Backward seek permits future cues again in the new epoch. Internal timeline clicks mark seeking before writing currentTime. Native seeking/seeked handle other assignments. Source emptied resets the field and timeline; replay handles the real restart lifecycle.

Pause flushes only media already played. Paused RAF updates do not move the musical cursor. Existing passive wave settling during pause/end remains unchanged. Resume uses currentTime, not wall-clock delay. waiting/stalled/suspend do not reset the field. ended has an explicit final flush, including when no further RAF follows.

## Synthetic and physical validation

- 90 stall/location cases: 50, 100, 250, 301, 350, 500, 950, 1500, 3000 and 5000 ms; start, calm, dense, middle, end, and immediately before/exactly/after a cue. Zero missing/duplicate cues.
- Comparison includes full heights and velocities, original cue index/order/times, next index and completed media/simulation target. Tolerance: absolute 1e-6. Observed errors: zero.
- Normal BEFORE versus AFTER across all 330 s: identical cue order/times and full height/velocity arrays; maximum error 0.
- Fixed-seed stress (seed 73129), variable render gaps throughout 330 s: 10,282 applied/unique; final index 10,282; simulationTime 330; height/velocity errors 0.
- Final flush without another render, full replay after ended, forward/backward and multiple seek intervals, paused seeks, dense/near-start/near-end seeks: PASS. Expectations count only deliberately played intervals per epoch.

Catch-up benchmark (16x16, 128x128, original physics):

| Media gap | CPU milliseconds |
|---|---:|
| 1 s | 18.845 |
| 3 s | 60.385 |
| 5 s | 103.602 |
| 10 s | 207.686 |

Direct recovery is retained: 950 ms is approximately a 1 s benchmark; even the measured 10 s recovery took about 208 ms, not seconds. No approximate physics or cue dropping is used. This implementation is synchronous; much longer absences can cost proportionally more CPU. No unlimited-absence UI latency guarantee is claimed.

## Real playbacks (330 s each)

| Run | Applied | Unique | Dropped | Duplicate | Unexpected reset | Largest media update gap |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 10282 | 10282 | 0 | 0 | 0 | 90.667 ms |
| 2 | 10282 | 10282 | 0 | 0 | 0 | 37.900 ms |
| 3 | 10282 | 10282 | 0 | 0 | 0 | 69.333 ms |
| 4 controlled | 10282 | 10282 | 0 | 0 | 0 | 3001.349 ms |

Runs 1, 2 and 3 completed independently and sequentially after synthetic validation. Only after those three PASS did controlled Run 4 begin. Run 4 injected main-thread stalls at 15/46/156/200/325 s (950/1500/950/3000/950 ms). Complete per-cue index/epoch/time records and lifecycle events are retained in real-run-1.json through real-run-4.json. No console or media errors. No attempt was selected or discarded: the earlier power-loss interruption is retained in interrupted-power-loss-log.txt; its last observation was 30.330667 s and it is not counted as a complete run or PASS.

## Controls and visibility

Browser controls PASS: Play, Pause, Resume, forward/backward seeks, paused seek, multiple seeks, near-start/end, and replay after ended. Replay starts a new epoch with a reset cursor and renewed future cue eligibility. Synthetic replay also traverses the whole track again with all 10,282 cues.

Actual hidden-tab validation was not available in this headless Chrome configuration: bringing another tab forward and CDP frozen/active kept document.visibilityState visible with no visibilitychange events. This limitation is recorded in visibility-lifecycle.json. The lifecycle probe passed with no missing cues or resets, but is NOT claimed as actual hidden-tab coverage. Deterministic no-frame intervals up to 5 s and real main-thread stalls prove clock-gap recovery independently of visibility. The first probe had a test-harness context error; a later probe read moving state non-atomically. Final probe pauses/flushes before collecting a consistent snapshot. These harness issues required no product change.

## Frozen visual and protected components

index.html, style.css, AudioMotionRecovery and RippleField match the rollback byte-for-byte. The entire camera-through-audio-analysis visual section and entire animate/render section match the snapshot. Camera, yaw 45 degrees, grid 128x128, physical 16x16, width, FRONT, listener/HUD, colors, particles, bloom and automatic motionGain were not changed. Three seeded normal captures at 0, 46.5 and 200.5 s are PNG-byte-identical before/after (therefore pixel-identical). See visual-freeze.json and six PNGs.

| Protected component | SHA-256 |
|---|---|
| index.html | `e891a183ce0944bc5cf84b0de33fac7030e06fd182dc05a7e73578745810d967` |
| src/style.css | `f4001a9fd55a73c30072ef3ed843c2ae5da078f568fdda09cd15cbb8875c1343` |
| src/audio-motion-recovery.js | `2a9939775cbd54c0025eca3c594a69ae0d3324bfbc1d2dd882d24836abc05e21` |
| src/ripple-field.js | `3525e4ee424a4af054be7195129dc6c458b1132412b46921ef6b42e9f7a03f50` |
| public/audio/TUKANA02_FINAL_MASTER_PCM24_48k.wav | `4f4d46a870faf29fa51867450a5a70cc82faad1b863d83bd40e89c6d27a3e271` |
| public/audio/tukana-stem-cues.json | `c880676240a480f72cf3dc42fc5b3a656bd38fd466a79474698abd81b99e944c` |
| public/audio/tukana-visualizer-manifest.json | `d9e30acd15b532ce44e7a05ee3cffcf22c1e602e55623018ae9b241065e9f62d` |

## Changed files in this phase

- Production: src/audio-cue-timeline.js; temporal lifecycle and updateSoundWaves portions of src/main.js ONLY. See temporal-only.diff and per-file diffs.
- Tests: tests/playback-continuity.test.js added; existing audio-cue-timeline.test.js stale-event test now explicitly calls seek(2), preserving its assertion that deliberately skipped hits must not burst. Implicit frame-gap dropping is the proven bug and cannot remain the expected behavior.
- tests/spatial-composition-recovery.test.js retains calibration/physics byte-hash assertions; temporal hash protection now targets the frozen pre-recovery baseline, since this phase expressly authorizes temporal repair. Normal-before/after equivalence provides behavioral regression coverage. No physical/calibration assertion was relaxed.
- Audit tools added: tools/audit_playback_continuity.mjs, tools/validate_playback_continuity.py, tools/verify_continuity_freeze.py, tools/check_continuity_visibility.py.
- This report, evidence directory and backups/V1_2BR3B_R1_PRE_CONTINUITY rollback snapshot. Earlier uncommitted V1.2 work, historical backups and unrelated files preserved.

## Checks and result

- Existing and new JavaScript unit tests: 78 PASS, 0 FAIL.
- Python unit tests: 4 PASS. Total unit tests: 82 PASS.
- Additional synthetic audit: 90 cases plus full-track normal equivalence, stress, seek, flush/replay and benchmarks PASS.
- Production build PASS; existing >500 kB bundle advisory remains.
- git diff --check PASS (exit 0); CRLF normalization advisories are not whitespace errors.
- Full real playbacks: 3/3 normal PASS; 1/1 controlled-stall PASS.
- Final: PASS. This phase repairs ONLY audio-to-simulation temporal continuity; the R3B composition and R1 response/calibration remain frozen. No version-control mutation or V1.3 work. Await review.
