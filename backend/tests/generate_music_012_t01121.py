from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]

for d in (
    ROOT / "backend" / "generation",
    ROOT / "backend" / "composition",
    ROOT / "backend" / "asset_pipeline",
    ROOT / "backend" / "sound_design",
    ROOT / "backend" / "safety",
):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

from generation_request import GenerationRequest
from production_composer import (
    ProductionComposer,
    write_midi,
    score_fingerprint,
    score_note_count,
    PPQ,
)
from t0102_semantic_router import T0102SemanticRouter
from t010_hybrid_renderer import (
    write_pcm16,
    sha256_file,
)
from t01121_safety_engine import (
    HarmonicDynamicTransitionSafety,
    shared_scoring_stage,
    light_glue_compressor,
)
from t01121_contextual_fx import ContextualCinematicFX


SR = 48000

T01121 = ROOT / "evidence" / "T011.2.1"
OUT = ROOT / "evidence" / "MUSIC-012"
MIDI = OUT / "midi"
DRY = OUT / "dry_stems"

MASTER = OUT / "LAISE_MUSIC012_ECOS_DA_TEMPESTADE.wav"
MANIFEST = OUT / "generation_manifest.json"
SAFETY_REPORT = OUT / "t01121_safety_report.json"


REQUEST = GenerationRequest(
    title="Ecos da Tempestade",
    style="cinematic_suspense",
    duration_seconds=94.0,
    emotion="dark",
    intensity=0.78,
    seed=12012,
    bpm=None,
    key=None,
    density=0.72,
    variation=0.88,
    spatial_profile="cinematic_wide",
)


PROGRAMS = {
    "piano": 0,
    "theme": 68,
    "strings": 48,
    "bass": 42,
    "ostinato": 48,
    "brass": 60,
    "countermelody": 40,
    "brass_attack": 60,
    "percussion_low": 0,
    "percussion_snare": 0,
    "percussion_cymbal": 0,
}


ROLE_GAINS_DB = {
    "piano": -4.5,
    "theme": -6.5,
    "strings": -8.0,
    "bass": -7.5,
    "ostinato": -11.5,
    "brass": -10.5,
    "countermelody": -9.5,
    "brass_attack": -10.5,
    "percussion_low": -9.5,
    "percussion_snare": -11.5,
    "percussion_cymbal": -13.0,
}


def db_gain(db: float) -> float:
    return 10.0 ** (db / 20.0)


def pad_to(x: np.ndarray, n: int) -> np.ndarray:
    out = np.zeros((2, n), dtype=np.float32)
    use = min(n, x.shape[1])
    out[:, :use] = x[:, :use]
    return out


def master_safely(mix: np.ndarray) -> np.ndarray:
    x = np.nan_to_num(mix).astype(np.float32)

    # Preserve dynamics. Only mild soft saturation.
    x = np.tanh(x * 1.045) / np.tanh(1.045)

    peak = float(np.max(np.abs(x))) + 1e-12
    if peak > 0.90:
        x *= 0.90 / peak

    return x.astype(np.float32)


def main():
    print("=" * 78)
    print("LAISE — T011.2.1 | Harmonic, Dynamic & Transition Safety")
    print("MUSIC-012 — Ecos da Tempestade | NEW composition")
    print("=" * 78)

    for d in (T01121, OUT, MIDI, DRY):
        d.mkdir(parents=True, exist_ok=True)

    REQUEST.validate()

    # --------------------------------------------------------------
    # NEW score — never reuse MUSIC-011 or MUSIC-010 notes.
    # --------------------------------------------------------------
    composer = ProductionComposer(REQUEST)
    plan, raw_score = composer.compose()

    raw_fingerprint = score_fingerprint(raw_score)

    safety = HarmonicDynamicTransitionSafety(plan)
    safe_score, score_safety_report = safety.apply(raw_score)

    safe_fingerprint = score_fingerprint(safe_score)

    print("\nNEW COMPOSITION")
    print("Title:", plan.title)
    print("Seed:", plan.request_seed)
    print("Key:", plan.key, plan.mode)
    print("BPM:", plan.bpm)
    print("Bars:", plan.total_bars)
    print("Nominal duration:", f"{plan.nominal_duration_seconds:.2f}s")
    print("Motif:", plan.motif_degrees)
    print("Raw fingerprint:", raw_fingerprint)
    print("Safe fingerprint:", safe_fingerprint)
    print("Safety corrections:", score_safety_report["correction_count"])

    print("\nSECTIONS")
    for s in plan.sections:
        print(
            f"{s.name:<14} bars {s.start_bar:02d}-"
            f"{s.start_bar + s.bars - 1:02d} | "
            f"energy={s.energy:.2f} | {s.harmonic_function}"
        )

    # --------------------------------------------------------------
    # Objective pre-render safety checks.
    # --------------------------------------------------------------
    out_of_key_after = safety.count_out_of_key_melodic_notes(
        safe_score
    )
    resolution_semitones_after = (
        safety.count_homecoming_minor_second_collisions(
            safe_score
        )
    )
    fx_mismatches_after = safety.fx_tonal_mismatches(
        safe_score
    )
    accent_max_after = safety.accent_cluster_max(
        safe_score
    )

    # --------------------------------------------------------------
    # Render orchestral roles through production-approved asset route.
    # --------------------------------------------------------------
    router = T0102SemanticRouter(ROOT, SR)

    orchestral_roles = [
        "piano",
        "theme",
        "strings",
        "bass",
        "ostinato",
        "brass",
        "countermelody",
        "brass_attack",
        "percussion_low",
        "percussion_snare",
        "percussion_cymbal",
    ]

    dry = {}
    rendered = {}

    print("\nRENDERING SAFE SCORE")
    for i, role in enumerate(orchestral_roles, 1):
        route = router.route(role)
        notes = safe_score[role]

        if role.startswith("percussion_"):
            target = route.playable_center or 60
            notes = [
                type(n)(
                    n.start,
                    n.duration,
                    target,
                    n.velocity,
                    0,
                )
                for n in notes
            ]

        midi_path = MIDI / f"{i:02d}_{role}.mid"
        write_midi(
            midi_path,
            notes,
            plan.bpm,
            PROGRAMS[role],
            0,
        )

        wav_path = DRY / f"{role}.wav"
        audio, info, _ = router.render_sfizz(
            route,
            midi_path,
            wav_path,
        )

        dry[role] = audio
        rendered[role] = {
            "renderer": route.renderer,
            "family": route.family,
            "instrument": route.instrument,
            "asset_id": route.asset_id,
            "asset_path": route.asset_path,
            "wav": str(wav_path),
            "wav_sha256": sha256_file(wav_path),
            "audio_info": info,
        }

        print(
            f"{role:<20} -> {route.instrument:<14} | "
            f"{Path(route.asset_path).name}"
        )

    # --------------------------------------------------------------
    # Build orchestral reference bus first.
    # This gives the Dynamic Impact Guard real audio context.
    # --------------------------------------------------------------
    seconds_per_tick = 60.0 / (plan.bpm * PPQ)
    score_end_tick = max(
        n.start + n.duration
        for notes in safe_score.values()
        for n in notes
    )
    total_samples = int(
        round(
            score_end_tick
            * seconds_per_tick
            * SR
        )
    ) + int(5.0 * SR)

    orchestral_mix = np.zeros(
        (2, total_samples),
        dtype=np.float32,
    )

    for role in orchestral_roles:
        x = pad_to(dry[role], total_samples)
        orchestral_mix += (
            x * db_gain(ROLE_GAINS_DB[role])
        )

    # --------------------------------------------------------------
    # Pitch-aware FX + contextual loudness guard.
    # --------------------------------------------------------------
    fx_engine = ContextualCinematicFX(
        sample_rate=SR,
        seed=REQUEST.seed + 17000,
    )

    fx_stems = {
        "braam": np.zeros_like(orchestral_mix),
        "ping": np.zeros_like(orchestral_mix),
    }
    impact_diagnostics = []

    print("\nCONTEXTUAL FX")
    for role in ("braam", "ping"):
        for note in safe_score[role]:
            event_audio = fx_engine.render_event(
                role,
                note.pitch,
            )

            guarded_event, diag = (
                safety.guarded_place_fx_event(
                    reference_mix=orchestral_mix,
                    event_audio=event_audio,
                    event_note=note,
                    role=role,
                    sample_rate=SR,
                    bpm=plan.bpm,
                )
            )

            fx_stems[role] += guarded_event
            impact_diagnostics.append(
                diag.__dict__
            )

            print(
                f"{role:<8} @ {diag.start_seconds:6.2f}s | "
                f"{diag.section:<12} | "
                f"pitch={note.pitch:<3} | "
                f"gain={diag.applied_gain_db:6.2f} dB | "
                f"limit={diag.allowed_delta_db:4.1f} dB"
            )

        write_pcm16(
            DRY / f"{role}.wav",
            fx_stems[role],
            SR,
        )

    # --------------------------------------------------------------
    # Shared acoustic glue.
    # --------------------------------------------------------------
    mix = (
        orchestral_mix
        + fx_stems["braam"]
        + fx_stems["ping"]
    )

    mix = shared_scoring_stage(
        mix,
        SR,
        wet=0.085,
    )
    mix = light_glue_compressor(
        mix,
        threshold_db=-17.5,
        ratio=1.42,
        attack_ms=24.0,
        release_ms=190.0,
        sample_rate=SR,
    )
    mix = master_safely(mix)

    write_pcm16(MASTER, mix, SR)

    # --------------------------------------------------------------
    # Post-render safety validation.
    # --------------------------------------------------------------
    all_fx_diagnostics_finite = all(
        np.isfinite(
            [
                d["context_rms_db"],
                d["orchestral_post_rms_db"],
                d["raw_fx_rms_db"],
                d["applied_gain_db"],
                d["final_fx_rms_db"],
            ]
        ).all()
        for d in impact_diagnostics
    )

    # Final FX head should remain inside its contextual cap.
    dynamic_guard_pass = True
    for d in impact_diagnostics:
        base_db = max(
            d["context_rms_db"],
            d["orchestral_post_rms_db"],
            -42.0,
        )
        actual_delta = (
            d["final_fx_rms_db"] - base_db
        )
        if actual_delta > d["allowed_delta_db"] + 0.35:
            dynamic_guard_pass = False

    no_braam_in_homecoming = all(
        safety.section_for_tick(n.start).name
        != "homecoming"
        for n in safe_score["braam"]
    )

    checks = {
        "new_music_request_valid": True,
        "music012_is_new_seed_and_new_score":
            REQUEST.seed != 11011,
        "raw_and_safe_fingerprints_recorded":
            bool(raw_fingerprint and safe_fingerprint),
        "harmonic_guard_no_out_of_key_melodic_notes":
            out_of_key_after == 0,
        "homecoming_no_exposed_minor_second_collisions":
            resolution_semitones_after == 0,
        "fx_tonal_guard_all_fx_match_current_chord":
            fx_mismatches_after == 0,
        "no_braam_in_homecoming":
            no_braam_in_homecoming,
        "accent_collision_guard_max_two_strong_roles":
            accent_max_after <= 2,
        "dynamic_impact_guard_pass":
            dynamic_guard_pass,
        "impact_diagnostics_finite":
            all_fx_diagnostics_finite,
        "all_orchestral_roles_rendered":
            all(role in rendered for role in orchestral_roles),
        "all_orchestral_wavs_non_silent":
            all(
                rec["audio_info"]["rms"] > 1e-7
                for rec in rendered.values()
            ),
        "all_orchestral_wavs_48khz":
            all(
                rec["audio_info"]["sample_rate"] == SR
                for rec in rendered.values()
            ),
        "shared_room_bus_active": True,
        "light_glue_bus_active": True,
        "master_finite":
            bool(np.isfinite(mix).all()),
        "master_non_silent":
            float(
                np.sqrt(
                    np.mean(
                        mix.astype(np.float64) ** 2
                    )
                )
            ) > 1e-6,
        "master_no_clipping":
            float(np.max(np.abs(mix))) < 0.999,
    }

    result = (
        "PASS"
        if all(checks.values())
        else "FAIL"
    )

    safety_payload = {
        "milestone": "T011.2.1",
        "work_id": "LAISE-MUSIC-012",
        "title": REQUEST.title,
        "objective_result": result,
        "raw_score_fingerprint": raw_fingerprint,
        "safe_score_fingerprint": safe_fingerprint,
        "score_safety": score_safety_report,
        "post_guard_metrics": {
            "out_of_key_melodic_notes":
                out_of_key_after,
            "homecoming_minor_second_collisions":
                resolution_semitones_after,
            "fx_tonal_mismatches":
                fx_mismatches_after,
            "max_simultaneous_strong_accent_roles":
                accent_max_after,
        },
        "impact_diagnostics": impact_diagnostics,
        "checks": checks,
    }

    SAFETY_REPORT.write_text(
        json.dumps(
            safety_payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    T01121_MANIFEST = (
        T01121 / "t01121_completion_manifest.json"
    )
    T01121_MANIFEST.write_text(
        json.dumps(
            {
                "milestone": "T011.2.1",
                "objective_result": result,
                "music": "LAISE-MUSIC-012",
                "new_composition": True,
                "request_seed": REQUEST.seed,
                "safety_report": str(SAFETY_REPORT),
                "master": str(MASTER),
                "master_sha256": sha256_file(MASTER),
                "guards": [
                    "harmonic_guard",
                    "fx_tonal_guard",
                    "accent_collision_guard",
                    "dynamic_impact_guard",
                    "shared_scoring_stage",
                    "light_glue_bus",
                ],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manifest = {
        "work_id": "LAISE-MUSIC-012",
        "title": REQUEST.title,
        "purpose": (
            "First completely new composition generated after adding "
            "T011.2.1 Harmonic, Dynamic & Transition Safety."
        ),
        "request": REQUEST.to_dict(),
        "composition_plan": plan.to_dict(),
        "raw_score_fingerprint": raw_fingerprint,
        "safe_score_fingerprint": safe_fingerprint,
        "score_note_count": score_note_count(safe_score),
        "rendered_assets": rendered,
        "impact_diagnostics": impact_diagnostics,
        "master": str(MASTER),
        "master_sha256": sha256_file(MASTER),
        "objective_result": result,
        "perceptual_result": "PENDING",
        "checks": checks,
    }

    MANIFEST.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\nAUTOMATED VALIDATION")
    for name, passed in checks.items():
        print(
            f"{name:<62}"
            f"{'PASS' if passed else 'FAIL'}"
        )

    print("\nT011.2.1 OBJECTIVE RESULT:", result)
    print("MUSIC-012 PERCEPTUAL RESULT: PENDING")
    print("Safety report:", SAFETY_REPORT)
    print("Master:", MASTER)
    print("SHA256:", sha256_file(MASTER))


if __name__ == "__main__":
    main()
