# T018 rollback inventory (2026-10-11)

Audit before pipeline changes: HEAD 8ce8268; history contains four commits,
none identifying T017/T018 completion. All T012-T018 project-specific additions
are untracked. No T018 commit can be selectively reverted.

Experimental execution files:
- backend/spatial/t018_acoustic_depth.py: dynamic distance, compensation,
  parameter audit and isolated experimental rendering.
- backend/spatial/t0181_proximal_depth.py: microdistance, early reflections,
  clarity comparisons; imports the T018 module.
- backend/tests/test_t018_acoustic_depth.py and test_t0181_proximal_depth.py:
  executable experiment entry points.

These four files will move under evidence/EXPERIMENTAL_REJECTED/t018,
outside active backend imports and test discovery. Historical reports and WAVs
remain in place, explicitly rejected by the baseline manifest and markers.
Archived test filenames end in .py.txt to avoid discovery even from repository
root. Source contents are preserved; no experimental DSP was merged back.

No imports of these modules exist in the T015 renderer, T016 mastering,
T017 refinement, composer, profiles or other active scripts.

Preserve the working-tree dearvr_adapter.py changes: azimuth wrapping and
unwrapped interpolation for 360-degree orbits, timeline offsets and keyframe
gain automation. They are used by T013-T017. The adapter still applies the
calibrated fixed distance 3 m / raw 0.0969899744. Restoring HEAD would remove
these necessary pre-T018 capabilities. No shared T018 DSP delta was found.

Preserve importer, analyzer, composer, previews, full renderer, mastering,
T012-T017 tests, scene, profile, analysis and prior approvals. Git history alone
cannot date these uncommitted files; attribution also uses imports, reports,
test IDs, rendering paths and approved-reference hashes.

Protected B2 initial SHA-256:
9daf544d7e073d8791f6260eed2630863a9280a2cca7d22053132a881e2c0df9

Validation will use a separate scratch project for full T015/T016/T017
regeneration; existing approved audio is never an output destination.
