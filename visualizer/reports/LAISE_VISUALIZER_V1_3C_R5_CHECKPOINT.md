# LAISE Visualizer V1.3C — R5 Open Boundary Checkpoint

## Status

CHECKPOINT — BEST CURRENT VISUAL STATE

This checkpoint freezes the best visually validated state reached during
LAISE Visualizer V1.3C development.

It is NOT the final approval of V1.3C.

Remaining work includes:

- Dynamic Visual Headroom measurement/calibration
- full-track R5 playback/stability audit
- synthetic behavior cases A–P
- final V1.3C regression/closure
- later production integration decision

---

## Baseline

V1.3C branch:

feature/visualizer-v1.3c-spatial-behavior-engine

Approved parent:

LAISE_VISUALIZER_V1_3B_APPROVED

Parent commit:

6ef636332f202e2720ed3b2d90c43ea7e0598403

---

## V1.3C architecture frozen in this checkpoint

Pipeline:

MUSIC
→ EVIDENCE
→ GESTURE
→ INTENT
→ SALIENCE
→ BEHAVIOR
→ PHYSICS
→ IMAGE

Implemented components include:

- Musical Behavior Planner
- continuous Dynamic Physical Drive
- T007 spatial authority
- absolute-preserving physical drive
- dominant-source visual centering
- R3.2 bipolar wave morphology
- R4 dimensionally-correct transient reinforcement
- R5 invisible physical continuation / open visible boundary

---

## R5 — Invisible Continuation

Previous visible-boundary behavior reflected significant wave energy
back into the visible field.

R5 changes the physical interpretation:

The visible mesh boundary is the limit of the camera,
not a physical wall.

Visible domain:

16 × 16 physical units

Visible mesh:

128 × 128 segments
129 × 129 vertices
16641 visible height samples

Internal R5 physical domain:

22 × 22 physical units

Internal grid:

177 × 177

Hidden continuation:

24 cells / 3 physical units beyond each visible side

Visible simulation resolution remains:

dx = dz = 0.125

T007 visible coordinate semantics remain unchanged.

Absorption begins strictly outside the visible domain.

---

## R5 physical audit

VISIBLE_HEIGHT_COUNT=16641
EXPECTED_VISIBLE_HEIGHT_COUNT=16641

INITIAL_WAVE_RETENTION=1.0

Legacy late center return:

0.05959189683198929

R5 late center return:

0.002582500921562314

REFLECTION_REDUCTION:

0.9566635556367118

Approximately:

95.67%

R5_PHYSICS_CONTRACT=PASS

Validated contracts:

- visible height contract PASS
- initial wave preserved PASS
- visible edge moves PASS
- reflection reduced PASS
- coordinate scale preserved PASS

---

## Musical/physical contracts preserved

R3.2 bipolar morphology preserved.

R4 transient coupling preserved.

T007 remains spatial authority.

Dominant-source centering preserved.

Existing waves do not teleport when the dominant anchor changes.

Propagation speed remains physics-governed.

Intensity does not control propagation speed.

roleCode is not used as a binary visual gain.

visualEnergyCandidate is not mapped directly to mesh height.

No per-stem normalization introduced.

Dynamic Visual Headroom is NOT implemented in this checkpoint.

The existing visual maxHeight/tanh mapping remains unchanged.

---

## A/B isolation

V1.2 and V1.3C use independent physical fields in the Behavior Lab.

V1.2:

legacy reflective RippleField

V1.3C:

OpenBoundaryRippleFieldV13C

Both modes continue to use the same master audio/currentTime.

The renderer receives exactly 129 × 129 visible height samples
regardless of the larger internal V1.3C physical domain.

---

## Human visual validation

Continuous playback was evaluated without pausing the music to allow
the mesh to settle.

Observed result:

- previous waves no longer visibly return from the boundary;
- musical sequences that were previously masked became visible;
- more independent wave origins became perceptible;
- wave positions became easier to distinguish;
- mesh grid lines remained substantially more legible;
- accumulated deformation was reduced;
- simultaneous structures remained capable of physical interference;
- overall visual result was judged substantially more beautiful and
  closer to the intended LAISE spatial-field behavior.

This was the first tested state in which continuous playback approached
the clarity previously observed only after pausing and allowing the
physical field to settle.

---

## Production protection

The following approved production files remain untouched:

visualizer/src/main.js
visualizer/src/ripple-field.js
visualizer/src/audio-cue-timeline.js

PRODUCTION_PROTECTION=PASS

The official production visualizer therefore remains unchanged.

---

## Build / repository gates

Vite build:

PASS

Staged whitespace validation:

PASS

Large generated artifacts:

PASS

All primary generated JSON artifacts remain below GitHub size limits.

Branch base integrity:

PASS

---

## Architectural conclusion

R5 strongly supports the hypothesis that a significant portion of the
previous visual chaos was caused by numerical boundary reflection rather
than by musical interference itself.

The resulting architectural law is:

> The visible mesh boundary represents the limit of the camera,
> not the end of the physical surface.

And the legibility principle remains:

> Older physical waves may persist and interfere, but artificial
> boundary return must not mask subsequent relevant musical causes.

No additional anti-chaos mechanism should be introduced until full-track
R5 validation demonstrates that one is actually necessary.

---

## Checkpoint policy

This checkpoint exists as a protected return point before further
V1.3C experimentation.

Future work must branch from this state.

Do not overwrite this checkpoint with Dynamic Visual Headroom or later
experimental calibration.
