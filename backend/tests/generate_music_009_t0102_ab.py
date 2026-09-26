from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for d in (
    ROOT / "backend" / "composition",
    ROOT / "backend" / "spatial",
    ROOT / "backend" / "mastering",
    ROOT / "backend" / "asset_pipeline",
):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

from music005_narrative_composer import (
    build_harmonic_map, write_midi, piano, make_theme, strings, bass, ostinato,
    percussion, brass, ExpressiveTiming, BPM, SEED, PPQ, BAR
)
from t008_orchestration import CinematicOrchestrationEngine
from t008_mix_intelligence import MixIntelligence
from t008_depth import depth_profile, apply_depth_tail
from t009_instrument_realism import InstrumentRealismEngine
from music005_spatial import narrative_keyframes
from dearvr_adapter import DearVRRenderer
from t010_hybrid_renderer import write_pcm16, read_wav_float, sha256_file
from t0102_semantic_router import T0102SemanticRouter

OUT = ROOT / "evidence" / "MUSIC-009"
MIDI = OUT / "midi"
DRY = OUT / "dry_stems"
SP = OUT / "spatial_stems"
MIX = OUT / "LAISE_MUSIC008_T0102_FULL_ORCHESTRAL_AB.wav"
MAN = OUT / "generation_manifest.json"

SR = 48000


def build_frozen_score():
    curve, hevents, planner, hbars = build_harmonic_map()
    r = random.Random(SEED)
    ex = ExpressiveTiming(SEED, PPQ)
    motif, theme, _ = make_theme(ex, planner)

    note_map = {
        "piano": piano(r, ex, planner, hbars),
        "theme": theme,
        "strings": strings(r, planner, hbars),
        "bass": bass(r, planner, hbars),
        "ostinato": ostinato(r, planner, hbars, motif),
        "percussion": percussion(r, planner),
        "brass": brass(r, planner, hbars),
    }

    orch = CinematicOrchestrationEngine(PPQ, 40)
    note_map, predrop = orch.apply_predrop(note_map)
    note_map["countermelody"] = orch.countermelody(hbars)
    note_map["brass_attack"] = orch.brass_attack_layer(hbars)
    note_map.update(orch.cinematic_punctuation(hbars, True, True))

    realism = InstrumentRealismEngine(PPQ, BPM, 20260928)
    performed, performance_diag = realism.apply(note_map, planner, BAR)
    return curve, hevents, planner, hbars, performed, performance_diag, predrop


def split_percussion(notes, router):
    """
    Current score keeps a GM-style percussion line.
    T010.2 semantically separates it into three orchestral families and remaps
    each event to a playable key of the selected SFZ patch.
    """
    groups = {
        "percussion_low": [],
        "percussion_snare": [],
        "percussion_cymbal": [],
    }

    low_pitches = {35, 36, 41, 43, 45, 47, 48, 50}
    snare_pitches = {37, 38, 39, 40}
    cymbal_pitches = {42, 44, 46, 49, 51, 52, 55, 57, 59}

    for n in notes:
        if n.pitch in snare_pitches:
            role = "percussion_snare"
        elif n.pitch in cymbal_pitches:
            role = "percussion_cymbal"
        else:
            role = "percussion_low"

        target = router.route(role).playable_center or 60

        # Preserve subtle vertical variation for low drums without escaping
        # the patch's semantic center.
        if role == "percussion_low" and n.pitch in low_pitches:
            target = max(0, min(127, target + ((n.pitch % 3) - 1)))

        groups[role].append(
            type(n)(n.start, n.duration, target, n.velocity, 0)
        )

    return groups


def fluidsynth_render(root, midi_path, wav_path):
    fs = root / "tools" / "fluidsynth" / "bin" / "fluidsynth.exe"
    sf = root / "assets" / "soundfonts" / "GeneralUser GS v1.471.sf2"
    cp = subprocess.run(
        [
            str(fs), "-ni", "-g", "0.8", "-r", str(SR),
            "-F", str(wav_path), str(sf), str(midi_path)
        ],
        check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    if cp.returncode != 0:
        raise RuntimeError(cp.stdout[-4000:])
    audio, info = read_wav_float(wav_path)
    return audio, info


def main():
    print("=" * 78)
    print("LAISE — MUSIC 009 | T010.2 Full Orchestral Asset Migration A/B")
    print("=" * 78)

    for d in (OUT, MIDI, DRY, SP):
        d.mkdir(parents=True, exist_ok=True)

    (
        curve, hevents, planner, hbars,
        performed, performance_diag, predrop
    ) = build_frozen_score()

    router = T0102SemanticRouter(ROOT, SR)

    # Replace the monolithic GM percussion role with semantic orchestral roles.
    percussion_groups = split_percussion(performed.pop("percussion"), router)
    performed.update(percussion_groups)

    programs = {
        "piano": 0, "theme": 73, "strings": 48, "bass": 42,
        "ostinato": 48, "brass": 61, "countermelody": 40,
        "brass_attack": 61, "braam": 61, "ping": 0,
        "percussion_low": 0, "percussion_snare": 0, "percussion_cymbal": 0,
    }

    midi_paths = {}
    print("\nSEMANTIC ROUTING")
    for i, (role, notes) in enumerate(performed.items(), 1):
        route = router.route(role)
        channel = 0
        p = MIDI / f"{i:02d}_{role}.mid"
        write_midi(p, notes, programs[role], channel)
        midi_paths[role] = p

        print(
            f"{role:<20} -> {route.family:<11} | {route.instrument:<14} | "
            f"{route.articulation:<8} | {route.function:<20} | "
            f"{Path(route.asset_path).name}"
        )

    dry = {}
    render_records = {}

    print("\nSYNTHESIS")
    for role in performed:
        route = router.route(role)
        wav_path = DRY / f"{role}.wav"
        print(f"Rendering {role} via {route.renderer} ...")

        if route.renderer == "sfizz_render":
            audio, info, tail = router.render_sfizz(
                route, midi_paths[role], wav_path
            )
        else:
            audio, info = fluidsynth_render(
                ROOT, midi_paths[role], wav_path
            )
            tail = ""

        dry[role] = audio
        render_records[role] = {
            **router.provenance(role),
            "audio_info": info,
            "wav": str(wav_path),
            "wav_sha256": sha256_file(wav_path),
            "console_tail": tail,
        }

    n = max(x.shape[1] for x in dry.values())
    duration = n / SR
    dearvr = DearVRRenderer(SR, 256)

    gains = {
        "piano": -3.0,
        "theme": -5.0,
        "strings": -7.0,
        "bass": -5.8,
        "ostinato": -10.0,
        "brass": -10.0,
        "countermelody": -8.0,
        "brass_attack": -9.5,
        "braam": -11.0,
        "ping": -10.0,
        "percussion_low": -8.5,
        "percussion_snare": -10.0,
        "percussion_cymbal": -11.5,
    }

    spatial = {}
    print("\nSPATIALIZATION")
    for role, x in dry.items():
        if role.startswith("percussion_"):
            base_role = "percussion"
            depth_role = "percussion"
        elif role in (
            "piano", "theme", "strings", "bass", "ostinato", "brass"
        ):
            base_role = role
            depth_role = role
        else:
            base_role = "theme" if role == "countermelody" else "brass"
            depth_role = role

        print("Spatializing", role, "...")
        frames = narrative_keyframes(duration, base_role, planner)
        prof = depth_profile(depth_role)

        for f in frames:
            f["distance_m"] = prof["distance_m"]

        src = {
            "source_id": role,
            "trajectory": "T008 + T009 + T010.2 semantic assets",
            "gain_db": gains[role],
            "keyframes": frames,
        }

        y = dearvr.render(x, src)
        y = apply_depth_tail(y, SR, depth_role)
        spatial[role] = y

    mixai = MixIntelligence(SR)

    cleanup_frames = 0
    cleanup_analysis = {}
    for role in ("strings", "bass", "brass"):
        spatial[role], c, diag = mixai.conditional_lowmid_cleanup(spatial[role])
        cleanup_frames += c
        cleanup_analysis[role] = {"processed_frames": c, **diag}

    # Combine the three real percussion families as the T008 trigger.
    trigger_len = max(
        spatial[r].shape[1]
        for r in ("percussion_low", "percussion_snare", "percussion_cymbal")
    )
    trigger = np.zeros((2, trigger_len), dtype=np.float32)
    for r in ("percussion_low", "percussion_snare", "percussion_cymbal"):
        x = spatial[r]
        trigger[:, :x.shape[1]] += x

    min_duck = 1.0
    for role in ("bass", "strings"):
        spatial[role], g = mixai.percussion_duck(spatial[role], trigger)
        min_duck = min(min_duck, g)

    for role, y in spatial.items():
        write_pcm16(SP / f"{role}_spatial.wav", y, SR)

    mix = np.zeros((2, n), dtype=np.float32)
    for y in spatial.values():
        mix[:, :y.shape[1]] += y

    mix = mixai.preserve_dynamic_range(mix, .90)
    write_pcm16(MIX, mix, SR)

    orchestral_roles = [
        "piano", "theme", "strings", "bass", "ostinato", "brass",
        "countermelody", "brass_attack",
        "percussion_low", "percussion_snare", "percussion_cymbal"
    ]
    semantic_families = {
        role: router.route(role).family for role in orchestral_roles
    }

    checks = {
        "music008_score_preserved": all(
            k in performed for k in (
                "piano", "theme", "strings", "bass", "ostinato",
                "brass", "countermelody", "brass_attack", "braam", "ping"
            )
        ),
        "theme_migrated_from_generaluser":
            router.route("theme").renderer == "sfizz_render",
        "bass_migrated_from_generaluser":
            router.route("bass").renderer == "sfizz_render",
        "brass_migrated_from_generaluser":
            router.route("brass").renderer == "sfizz_render",
        "brass_attack_migrated_from_generaluser":
            router.route("brass_attack").renderer == "sfizz_render",
        "percussion_split_into_orchestral_roles":
            all(k in performed for k in (
                "percussion_low", "percussion_snare", "percussion_cymbal"
            )),
        "all_orchestral_roles_use_sfz":
            all(router.route(r).renderer == "sfizz_render" for r in orchestral_roles),
        "only_sound_design_uses_test_fallback":
            all(
                router.route(r).renderer == "fluidsynth"
                for r in ("braam", "ping")
            ),
        "ostinato_family_is_strings":
            semantic_families["ostinato"] == "strings",
        "brass_attack_family_is_brass":
            semantic_families["brass_attack"] == "brass",
        "percussion_roles_are_percussion_family":
            all(
                semantic_families[r] == "percussion"
                for r in ("percussion_low", "percussion_snare", "percussion_cymbal")
            ),
        "percussion_low_instrument_semantically_valid":
            router.route("percussion_low").instrument in ("bass_drum", "timpani", "tom"),
        "percussion_snare_instrument_is_snare":
            router.route("percussion_snare").instrument == "snare",
        "percussion_cymbal_instrument_semantically_valid":
            router.route("percussion_cymbal").instrument in ("cymbal", "gong"),
        "generated_snare_wrapper_selected":
            "LAISE_VSCO2CE_Snare.sfz" in router.route("percussion_snare").asset_path,
        "generated_cymbal_wrapper_selected":
            "LAISE_VSCO2CE_Cymbal.sfz" in router.route("percussion_cymbal").asset_path,
        "all_dry_stems_non_silent":
            all(rec["audio_info"]["rms"] > 1e-7 for rec in render_records.values()),
        "all_dry_stems_48khz":
            all(rec["audio_info"]["sample_rate"] == SR for rec in render_records.values()),
        "t008_lowmid_cleanup_preserved": cleanup_frames > 0,
        "t008_percussion_ducking_preserved": min_duck < .999,
        "mix_finite": bool(np.isfinite(mix).all()),
        "mix_non_silent":
            float(np.sqrt(np.mean(mix.astype(np.float64) ** 2))) > 1e-6,
        "mix_no_clipping": float(np.max(np.abs(mix))) < .999,
        "production_gate_not_bypassed":
            all(
                rec["asset_status"] != "PRODUCTION_APPROVED"
                for rec in render_records.values()
            ),
    }

    status = "PASS" if all(checks.values()) else "FAIL"

    payload = {
        "work_id": "LAISE-MUSIC-009",
        "title": "T010.2 Full Orchestral Asset Migration A/B",
        "comparison_basis": "MUSIC-008 frozen composition/performance/mix/spatial design",
        "engine": "T006 + T007 + T008 + T009 frozen + T010.2 semantic SFZ routing",
        "objective_result": status,
        "perceptual_result": "PENDING",
        "semantic_routes": {
            role: router.provenance(role) for role in router.routes
        },
        "generated_percussion_wrappers": router.percussion_wrappers,
        "rendered_assets": render_records,
        "performance_manifest": performance_diag,
        "t008_preserved": {
            "predrop": predrop,
            "lowmid_processed_frames": cleanup_frames,
            "lowmid_analysis": cleanup_analysis,
            "minimum_duck_gain": min_duck,
        },
        "checks": checks,
        "mix": str(MIX),
        "mix_sha256": sha256_file(MIX),
        "release_status": "DEVELOPMENT_ONLY",
        "release_note": (
            "Full orchestral roles migrated to semantic SFZ routing. "
            "Braam/ping remain isolated sound-design fallbacks. "
            "No onboarding asset is promoted to PRODUCTION_APPROVED here."
        ),
    }

    MAN.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("\nAUTOMATED VALIDATION")
    for k, v in checks.items():
        print(f"{k:<62}{'PASS' if v else 'FAIL'}")

    print("\nMUSIC-009 / T010.2 OBJECTIVE RESULT:", status)
    print("PERCEPTUAL RESULT: PENDING")
    print("Mix:", MIX)
    print("SHA256:", sha256_file(MIX))


if __name__ == "__main__":
    main()
