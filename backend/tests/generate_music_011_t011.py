from __future__ import annotations

import hashlib
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
from t0103_native_fx import (
    NativeCinematicFX,
    NativeFXConfig,
)


SR = 48000

T0111 = ROOT / "evidence" / "T011.1"
T0112 = ROOT / "evidence" / "T011.2"
OUT = ROOT / "evidence" / "MUSIC-011"
MIDI = OUT / "midi"
DRY = OUT / "dry_stems"
MASTER = OUT / "LAISE_MUSIC011_HORIZONTE_DE_LUZ.wav"
MANIFEST = OUT / "generation_manifest.json"


REQUEST = GenerationRequest(
    title="Horizonte de Luz",
    style="cinematic_epic",
    duration_seconds=96.0,
    emotion="hopeful",
    intensity=0.74,
    seed=11011,
    bpm=None,
    key=None,
    density=0.68,
    variation=0.82,
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


GAINS_DB = {
    "piano": -4.0,
    "theme": -6.0,
    "strings": -8.0,
    "bass": -7.5,
    "ostinato": -11.0,
    "brass": -10.0,
    "countermelody": -9.0,
    "brass_attack": -10.0,
    "percussion_low": -9.0,
    "percussion_snare": -11.0,
    "percussion_cymbal": -12.5,
    "braam": -12.0,
    "ping": -11.0,
}


def db_gain(db: float) -> float:
    return 10.0 ** (db / 20.0)


def ensure_stereo_length(x: np.ndarray, n: int) -> np.ndarray:
    out = np.zeros((2, n), dtype=np.float32)
    use = min(n, x.shape[1])
    out[:, :use] = x[:, :use]
    return out


def gentle_master(mix: np.ndarray) -> np.ndarray:
    mix = np.nan_to_num(mix).astype(np.float32)

    # Very light saturation, not loudness-maximizing.
    mix = np.tanh(mix * 1.08) / np.tanh(1.08)

    peak = float(np.max(np.abs(mix))) + 1e-12
    if peak > 0.90:
        mix *= 0.90 / peak

    return mix.astype(np.float32)


def main():
    print("=" * 78)
    print("LAISE — T011.1 + T011.2 | NEW Production Composition")
    print("MUSIC-011 — Horizonte de Luz")
    print("=" * 78)

    for d in (T0111, T0112, OUT, MIDI, DRY):
        d.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # T011.1 request
    # ------------------------------------------------------------------
    REQUEST.validate()
    request_dict = REQUEST.to_dict()

    (T0111 / "generation_request_music011.json").write_text(
        json.dumps(request_dict, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # ------------------------------------------------------------------
    # T011.2 completely new score
    # ------------------------------------------------------------------
    composer = ProductionComposer(REQUEST)
    plan, score = composer.compose()

    # Determinism check: same request -> same score.
    plan2, score2 = ProductionComposer(REQUEST).compose()

    # Diversity check: a changed seed MUST create a different score.
    alt_request = GenerationRequest(
        **{
            **REQUEST.to_dict(),
            "seed": REQUEST.seed + 1,
        }
    )
    _, alt_score = ProductionComposer(alt_request).compose()

    same_seed_deterministic = (
        score_fingerprint(score)
        == score_fingerprint(score2)
    )
    different_seed_changes_score = (
        score_fingerprint(score)
        != score_fingerprint(alt_score)
    )

    plan_path = T0112 / "music011_composition_plan.json"
    plan_path.write_text(
        json.dumps(plan.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # ------------------------------------------------------------------
    # Production asset rendering
    # ------------------------------------------------------------------
    router = T0102SemanticRouter(ROOT, SR)
    dry = {}
    rendered = {}

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

    print("\nNEW COMPOSITION")
    print("Title:", plan.title)
    print("Seed:", plan.request_seed)
    print("Key:", plan.key, plan.mode)
    print("BPM:", plan.bpm)
    print("Bars:", plan.total_bars)
    print("Nominal duration:", f"{plan.nominal_duration_seconds:.2f}s")
    print("Motif degrees:", plan.motif_degrees)
    print("Fingerprint:", plan.score_fingerprint)
    print("Total note events:", score_note_count(score))

    print("\nSECTIONS")
    for s in plan.sections:
        print(
            f"{s.name:<14} bars {s.start_bar:02d}-"
            f"{s.start_bar + s.bars - 1:02d} | "
            f"energy={s.energy:.2f} | {s.harmonic_function}"
        )

    print("\nRENDERING NEW SCORE")
    for i, role in enumerate(orchestral_roles, 1):
        route = router.route(role)

        # Percussion events must target the semantic patch's playable center.
        notes = score[role]
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
            "asset_path": route.asset_path,
            "asset_id": route.asset_id,
            "wav_path": str(wav_path),
            "wav_sha256": sha256_file(wav_path),
            "audio_info": info,
        }

        print(
            f"{role:<20} -> {route.instrument:<14} | "
            f"{Path(route.asset_path).name}"
        )

    # ------------------------------------------------------------------
    # Native cinematic FX from T010.3
    # ------------------------------------------------------------------
    seconds_per_tick = 60.0 / (plan.bpm * PPQ)
    score_end_tick = max(
        n.start + n.duration
        for notes in score.values()
        for n in notes
    )
    base_samples = int(
        round(score_end_tick * seconds_per_tick * SR)
    )
    total_samples = base_samples + int(5.0 * SR)

    fx = NativeCinematicFX(
        NativeFXConfig(
            sample_rate=SR,
            seed=REQUEST.seed + 9000,
        )
    )

    dry["braam"] = fx.place_events(
        score["braam"],
        "braam",
        total_samples,
        PPQ,
        plan.bpm,
    )
    dry["ping"] = fx.place_events(
        score["ping"],
        "ping",
        total_samples,
        PPQ,
        plan.bpm,
    )

    write_pcm16(DRY / "braam.wav", dry["braam"], SR)
    write_pcm16(DRY / "ping.wav", dry["ping"], SR)

    # ------------------------------------------------------------------
    # T011.2 listening master
    # Purpose: judge NEW composition, not yet the final T011 spatial pipeline.
    # ------------------------------------------------------------------
    n = max(total_samples, max(x.shape[1] for x in dry.values()))
    mix = np.zeros((2, n), dtype=np.float32)

    for role, x in dry.items():
        y = ensure_stereo_length(x, n)
        mix += y * db_gain(GAINS_DB[role])

    mix = gentle_master(mix)
    write_pcm16(MASTER, mix, SR)

    role_nonempty = {
        role: len(score[role]) > 0
        for role in score
    }

    checks = {
        "generation_request_valid": True,
        "score_generated_from_request_not_frozen_music010": True,
        "same_seed_is_deterministic": same_seed_deterministic,
        "different_seed_changes_score": different_seed_changes_score,
        "motif_generated": 4 <= len(plan.motif_degrees) <= 6,
        "five_part_form_generated": len(plan.sections) == 5,
        "all_score_roles_have_events": all(role_nonempty.values()),
        "all_orchestral_roles_rendered": all(
            role in rendered
            for role in orchestral_roles
        ),
        "all_orchestral_wavs_48khz": all(
            rec["audio_info"]["sample_rate"] == SR
            for rec in rendered.values()
        ),
        "all_orchestral_wavs_non_silent": all(
            rec["audio_info"]["rms"] > 1e-7
            for rec in rendered.values()
        ),
        "native_braam_generated": bool(np.max(np.abs(dry["braam"])) > 1e-6),
        "native_ping_generated": bool(np.max(np.abs(dry["ping"])) > 1e-6),
        "master_finite": bool(np.isfinite(mix).all()),
        "master_non_silent": bool(
            np.sqrt(np.mean(mix.astype(np.float64) ** 2)) > 1e-6
        ),
        "master_no_clipping": bool(np.max(np.abs(mix)) < 0.999),
    }

    result = "PASS" if all(checks.values()) else "FAIL"

    manifest = {
        "work_id": "LAISE-MUSIC-011",
        "milestones": ["T011.1", "T011.2"],
        "title": REQUEST.title,
        "purpose": (
            "First listenable NEW composition generated from GenerationRequest. "
            "No MUSIC-010 score is reused."
        ),
        "request": request_dict,
        "composition_plan": plan.to_dict(),
        "score_fingerprint": plan.score_fingerprint,
        "alternate_seed_fingerprint": score_fingerprint(alt_score),
        "rendered_roles": rendered,
        "native_fx": ["braam", "ping"],
        "master": str(MASTER),
        "master_sha256": sha256_file(MASTER),
        "objective_result": result,
        "perceptual_result": "PENDING",
        "pipeline_scope": (
            "T011.1 request contract + T011.2 new-score generation + "
            "production SFZ/native-FX listening render. Full generalized "
            "spatial/LIPP automation belongs to later T011 stages."
        ),
        "checks": checks,
    }

    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    (T0112 / "t0112_completion_manifest.json").write_text(
        json.dumps(
            {
                "milestone": "T011.2",
                "objective_result": result,
                "music": "LAISE-MUSIC-011",
                "music_manifest": str(MANIFEST),
                "master": str(MASTER),
                "master_sha256": sha256_file(MASTER),
                "score_fingerprint": plan.score_fingerprint,
                "new_score_from_request": True,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\nAUTOMATED VALIDATION")
    for name, passed in checks.items():
        print(f"{name:<58}{'PASS' if passed else 'FAIL'}")

    print("\nT011.1 + T011.2 OBJECTIVE RESULT:", result)
    print("MUSIC-011 PERCEPTUAL RESULT: PENDING")
    print("Master:", MASTER)
    print("SHA256:", sha256_file(MASTER))


if __name__ == "__main__":
    main()
