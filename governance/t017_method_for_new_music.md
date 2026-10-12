# T017 approved method

Official reference: LAISE_T017_APPROVED_BASELINE; see the adjacent JSON manifest
for the protected reference hash and the rejected T018 evidence registry.

1. Import new stems with stem_importer, preserving complete timeline and silence.
2. Analyze the new music with musical_analyzer: BPM, beat grid, sections,
   entrances and transitions. Review the musical map before scene decisions.
3. Create a new project, role profile and scene based on that music. The Tukana
   profile and trajectories are a worked example, not a universal preset.
4. Reuse dearVR independent instances, polar azimuth/elevation, unwrapped
   360-degree trajectories, keyframe interpolation and gain automation.
   Effective distance stays fixed at 3 m (raw 0.0969899744); reflections and
   reverb stay disabled by configure_direct_signal. Artistic distance fields
   in scenes are metadata and must not become dynamic DSP automation.
5. Use synchronized binaural multistem rendering, objective validation and
   human comparison before conservative mastering and transient refinement.
   T017 used two-pass EBU R128, target -16.3 LUFS / -1.5 dBTP / LRA 11;
   reassess musical/perceptual suitability for the new track.
6. Keep separate output directories and preserve every approved master.
   The T017 refinement refuses to overwrite an existing B2. Its original
   generation test is for a fresh project; use validate_t017_baseline.py to
   validate this baseline without overwriting the approved audio.

No dynamic distance, automatic distance compensation, extra early reflections,
occlusion, clarity/stereo-width manipulation, microdistance or T018 acoustic
depth logic belongs in this baseline. All T018/T018.1 renders are historical
EXPERIMENTAL_REJECTED artifacts; they are not active candidates.

Quality over effect count; clarity over artificial depth; presence over excessive
distance; naturalness over technological display; musical intention over random
motion. No new music has been processed as part of this rollback.

The current Tukana full-render harness has its approved frame count fixed in
code. For a different song, adapt frame count/project-specific wrappers to its
import manifest and validate synchronization; do not truncate or pad to Tukana.
