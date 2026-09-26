from __future__ import annotations

import hashlib
import json
import random
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
    build_harmonic_map,
    write_midi,
    piano,
    make_theme,
    strings,
    bass,
    ostinato,
    percussion,
    brass,
    ExpressiveTiming,
    BPM,
    SEED,
    PPQ,
    BAR,
)
from t008_orchestration import CinematicOrchestrationEngine
from t008_mix_intelligence import MixIntelligence
from t008_depth import depth_profile, apply_depth_tail
from t009_instrument_realism import InstrumentRealismEngine
from music005_spatial import narrative_keyframes
from dearvr_adapter import DearVRRenderer
from t010_hybrid_renderer import HybridInstrumentRenderer, write_pcm16, sha256_file

OUT = ROOT / "evidence" / "MUSIC-008"
MIDI = OUT / "midi"
DRY = OUT / "dry_stems"
SP = OUT / "spatial_stems"
MIX = OUT / "LAISE_MUSIC007_SFZ_ASSET_AB.wav"
MAN = OUT / "generation_manifest.json"

SR = 48000


def build_music007_performance():
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


def main():
    print("=" * 78)
    print("LAISE — MUSIC 008 | MUSIC-007 + SFZ Asset Upgrade A/B")
    print("=" * 78)

    for d in (OUT, MIDI, DRY, SP):
        d.mkdir(parents=True, exist_ok=True)

    (
        curve,
        hevents,
        planner,
        hbars,
        performed,
        performance_diag,
        predrop,
    ) = build_music007_performance()

    programs = {
        "piano": 0,
        "theme": 73,
        "strings": 48,
        "bass": 42,
        "ostinato": 48,
        "percussion": 0,
        "brass": 61,
        "countermelody": 40,
        "brass_attack": 61,
        "braam": 61,
        "ping": 0,
    }
    channels = {k: (9 if k == "percussion" else 0) for k in performed}

    midi_paths = {}
    for i, (role, notes) in enumerate(performed.items(), 1):
        p = MIDI / f"{i:02d}_{role}.mid"
        write_midi(p, notes, programs[role], channels[role])
        midi_paths[role] = p

    hybrid = HybridInstrumentRenderer(ROOT, SR)
    rendered = {}
    dry = {}

    print("\nINSTRUMENT ROUTING")
    for role in performed:
        route = hybrid.route(role)
        print(
            f"{role:<16} -> {route.renderer:<13} | "
            f"{route.asset_id} | {route.asset_path.name}"
        )

    print("\nSYNTHESIS")
    for role in performed:
        print("Rendering", role, "...")
        wav_path = DRY / f"{role}.wav"
        rec = hybrid.render(role, midi_paths[role], wav_path)
        dry[role] = rec.pop("audio")
        rendered[role] = rec

    n = max(x.shape[1] for x in dry.values())
    duration = n / SR

    renderer = DearVRRenderer(SR, 256)
    gains = {
        "piano": -3.0,
        "theme": -4.5,
        "strings": -7.0,
        "bass": -5.0,
        "ostinato": -10.0,
        "percussion": -7.5,
        "brass": -10.0,
        "countermelody": -8.0,
        "brass_attack": -9.0,
        "braam": -11.0,
        "ping": -10.0,
    }

    spatial = {}
    print("\nSPATIALIZATION")
    for role, x in dry.items():
        print("Spatializing", role, "...")
        base_role = (
            role
            if role in (
                "piano",
                "theme",
                "strings",
                "bass",
                "ostinato",
                "percussion",
                "brass",
            )
            else ("theme" if role == "countermelody" else "brass")
        )

        frames = narrative_keyframes(duration, base_role, planner)
        prof = depth_profile(role)
        for f in frames:
            f["distance_m"] = prof["distance_m"]

        src = {
            "source_id": role,
            "trajectory": "T008_depth + T009_performance + T010_SFZ",
            "gain_db": gains[role],
            "keyframes": frames,
        }

        y = renderer.render(x, src)
        y = apply_depth_tail(y, SR, role)
        spatial[role] = y

    mixai = MixIntelligence(SR)
    cleanup_frames = 0
    cleanup_analysis = {}

    for role in ("strings", "bass", "brass"):
        spatial[role], c, diag = mixai.conditional_lowmid_cleanup(spatial[role])
        cleanup_frames += c
        cleanup_analysis[role] = {"processed_frames": c, **diag}

    trigger = spatial["percussion"]
    min_duck = 1.0
    for role in ("bass", "strings"):
        spatial[role], g = mixai.percussion_duck(spatial[role], trigger)
        min_duck = min(min_duck, g)

    for role, y in spatial.items():
        write_pcm16(SP / f"{role}_spatial.wav", y, SR)

    mix = np.zeros((2, n), dtype=np.float32)
    for y in spatial.values():
        mix[:, : y.shape[1]] += y

    mix = mixai.preserve_dynamic_range(mix, 0.90)
    write_pcm16(MIX, mix, SR)

    sfz_roles = [
        r for r, rec in rendered.items()
        if rec["renderer"] == "sfizz_render"
    ]
    gs_roles = [
        r for r, rec in rendered.items()
        if rec["renderer"] == "fluidsynth"
    ]

    checks = {
        "music007_score_preserved": all(
            k in performed for k in (
                "piano",
                "theme",
                "strings",
                "bass",
                "ostinato",
                "percussion",
                "brass",
                "countermelody",
                "brass_attack",
                "braam",
                "ping",
            )
        ),
        "salamander_piano_active":
            rendered["piano"]["asset_id"] == "LAISE-SFZ-PIANO-SALAMANDER-V3",
        "vsco_sustain_strings_active":
            rendered["strings"]["asset_id"] == "LAISE-SFZ-VSCO2CE-STRINGS-SUS-001",
        "vsco_countermelody_active":
            rendered["countermelody"]["renderer"] == "sfizz_render",
        "ostinato_asset_semantically_strings":
            (
                rendered["ostinato"]["renderer"] != "sfizz_render"
                or any(
                    token in rendered["ostinato"]["asset_path"].lower()
                    for token in ("strings", "violin", "viola", "cello", "bassens")
                )
            ),
        "sfz_renderer_used": len(sfz_roles) >= 3,
        "hybrid_fallback_preserved": len(gs_roles) >= 1,
        "all_dry_stems_non_silent": all(
            rec["audio_info"]["rms"] > 1e-7 for rec in rendered.values()
        ),
        "all_dry_stems_48khz": all(
            rec["audio_info"]["sample_rate"] == SR for rec in rendered.values()
        ),
        "t008_lowmid_cleanup_preserved": cleanup_frames > 0,
        "t008_percussion_ducking_preserved": min_duck < 0.999,
        "mix_finite": bool(np.isfinite(mix).all()),
        "mix_non_silent":
            float(np.sqrt(np.mean(mix.astype(np.float64) ** 2))) > 1e-6,
        "mix_no_clipping": float(np.max(np.abs(mix))) < 0.999,
        "onboarding_assets_not_declared_production_approved": all(
            rec["asset_status"] != "PRODUCTION_APPROVED"
            for rec in rendered.values()
            if rec["renderer"] == "sfizz_render"
        ),
    }

    status = "PASS" if all(checks.values()) else "FAIL"

    payload = {
        "work_id": "LAISE-MUSIC-008",
        "title": "MUSIC-007 SFZ Asset Upgrade A/B",
        "comparison_basis": "MUSIC-007 frozen score/performance/mix/spatial architecture",
        "engine": "T006 + T007 + T008 + T009 frozen + T010.1 hybrid SFZ assets",
        "objective_result": status,
        "perceptual_result": "PENDING",
        "rendered_assets": rendered,
        "routing_summary": {
            "sfz_roles": sfz_roles,
            "generaluser_fallback_roles": gs_roles,
            "vsco_short_candidate": str(hybrid.vsco_short)
            if hybrid.vsco_short else None,
        },
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
            "MUSIC-008 validates real asset substitution. SFZ assets remain "
            "ONBOARDING/ONBOARDING_VALIDATED until license/provenance snapshot "
            "is frozen and promoted through the T010 production gate."
        ),
    }

    MAN.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nAUTOMATED VALIDATION")
    for k, v in checks.items():
        print(f"{k:<58}{'PASS' if v else 'FAIL'}")

    print("\nMUSIC-008 OBJECTIVE RESULT:", status)
    print("PERCEPTUAL RESULT: PENDING")
    print("SFZ roles:", ", ".join(sfz_roles))
    print("GeneralUser fallback:", ", ".join(gs_roles))
    print("Mix:", MIX)
    print("SHA256:", sha256_file(MIX))


if __name__ == "__main__":
    main()
