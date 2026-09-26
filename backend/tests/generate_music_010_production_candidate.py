from __future__ import annotations

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
    ROOT / "backend" / "sound_design",
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
from t010_hybrid_renderer import write_pcm16, sha256_file
from t0102_semantic_router import T0102SemanticRouter
from t0103_native_fx import NativeCinematicFX, NativeFXConfig
from t0103_governance import ProductionGovernance

OUT = ROOT / "evidence" / "MUSIC-010"
MIDI = OUT / "midi"
DRY = OUT / "dry_stems"
SP = OUT / "spatial_stems"
MIX = OUT / "LAISE_PRODUCTION_CANDIDATE_001.wav"
MAN = OUT / "generation_manifest.json"
GOV = OUT / "production_governance_snapshot.json"
ATTRIBUTION = OUT / "ATTRIBUTION.txt"
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

    return planner, performed, performance_diag, predrop


def split_percussion(notes, router):
    groups = {
        "percussion_low": [],
        "percussion_snare": [],
        "percussion_cymbal": [],
    }
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
        groups[role].append(
            type(n)(n.start, n.duration, target, n.velocity, 0)
        )
    return groups


def main():
    print("=" * 78)
    print("LAISE — MUSIC 010 | T010.3 Production Governance Candidate")
    print("=" * 78)

    for d in (OUT, MIDI, DRY, SP):
        d.mkdir(parents=True, exist_ok=True)

    planner, performed, performance_diag, predrop = build_frozen_score()
    router = T0102SemanticRouter(ROOT, SR)

    percussion_groups = split_percussion(performed.pop("percussion"), router)
    performed.update(percussion_groups)

    # Remove final TEST_ONLY audio dependencies. They become LAISE-native FX.
    braam_notes = performed.pop("braam")
    ping_notes = performed.pop("ping")

    programs = {
        "piano": 0, "theme": 73, "strings": 48, "bass": 42,
        "ostinato": 48, "brass": 61, "countermelody": 40,
        "brass_attack": 61,
        "percussion_low": 0, "percussion_snare": 0, "percussion_cymbal": 0,
    }

    midi_paths = {}
    print("\nPRODUCTION-CANDIDATE ROUTING")
    for i, (role, notes) in enumerate(performed.items(), 1):
        route = router.route(role)
        p = MIDI / f"{i:02d}_{role}.mid"
        write_midi(p, notes, programs[role], 0)
        midi_paths[role] = p
        print(
            f"{role:<20} -> {route.family:<11} | {route.instrument:<14} | "
            f"{Path(route.asset_path).name}"
        )

    dry = {}
    asset_records = {}

    print("\nSYNTHESIS")
    for role in performed:
        route = router.route(role)
        if route.renderer != "sfizz_render":
            raise RuntimeError(
                f"Production candidate cannot use renderer fallback for role={role}"
            )

        wav_path = DRY / f"{role}.wav"
        print("Rendering", role, "...")
        audio, info, tail = router.render_sfizz(
            route, midi_paths[role], wav_path
        )
        dry[role] = audio
        asset_records[role] = {
            **router.provenance(role),
            "audio_info": info,
            "wav": str(wav_path),
            "wav_sha256": sha256_file(wav_path),
        }

    # Native braam/ping replace GeneralUser GS entirely.
    current_n = max(x.shape[1] for x in dry.values())
    fx = NativeCinematicFX(NativeFXConfig(SR, 20260929))

    dry["braam"] = fx.place_events(
        braam_notes, "braam", current_n, PPQ, BPM
    )
    dry["ping"] = fx.place_events(
        ping_notes, "ping", current_n, PPQ, BPM
    )
    write_pcm16(DRY / "braam.wav", dry["braam"], SR)
    write_pcm16(DRY / "ping.wav", dry["ping"], SR)

    n = max(x.shape[1] for x in dry.values())
    duration = n / SR
    dearvr = DearVRRenderer(SR, 256)

    gains = {
        "piano": -3.0, "theme": -5.0, "strings": -7.0, "bass": -5.8,
        "ostinato": -10.0, "brass": -10.0, "countermelody": -8.0,
        "brass_attack": -9.5, "braam": -11.5, "ping": -10.5,
        "percussion_low": -8.5, "percussion_snare": -10.0,
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
            "trajectory": "T008 + T009 + T010.3 production candidate",
            "gain_db": gains[role],
            "keyframes": frames,
        }

        y = dearvr.render(x, src)
        y = apply_depth_tail(y, SR, depth_role)
        spatial[role] = y

    mixai = MixIntelligence(SR)
    cleanup_frames = 0

    for role in ("strings", "bass", "brass"):
        spatial[role], c, _ = mixai.conditional_lowmid_cleanup(spatial[role])
        cleanup_frames += c

    trigger_len = max(
        spatial[r].shape[1]
        for r in ("percussion_low", "percussion_snare", "percussion_cymbal")
    )
    trigger = np.zeros((2, trigger_len), dtype=np.float32)
    for r in ("percussion_low", "percussion_snare", "percussion_cymbal"):
        x = spatial[r]
        trigger[:, : x.shape[1]] += x

    min_duck = 1.0
    for role in ("bass", "strings"):
        spatial[role], g = mixai.percussion_duck(spatial[role], trigger)
        min_duck = min(min_duck, g)

    for role, y in spatial.items():
        write_pcm16(SP / f"{role}_spatial.wav", y, SR)

    mix = np.zeros((2, n), dtype=np.float32)
    for y in spatial.values():
        mix[:, : y.shape[1]] += y

    mix = mixai.preserve_dynamic_range(mix, .90)
    write_pcm16(MIX, mix, SR)

    # ---------------- Governance freeze ----------------
    gov = ProductionGovernance(ROOT)

    used_routes = [
        r for r in performed
        if router.route(r).renderer == "sfizz_render"
    ]

    unique_assets = {}
    for role in used_routes:
        route = router.route(role)
        key = route.asset_path
        if key in unique_assets:
            continue

        path_lower = route.asset_path.lower()
        if "salamander" in path_lower:
            policy_key = "SALAMANDER"
        else:
            policy_key = "VSCO2CE"

        unique_assets[key] = gov.freeze_sfz_asset(
            asset_id=route.asset_id,
            sfz_path=Path(route.asset_path),
            policy_key=policy_key,
            status=route.asset_status,
        )

    native_fx_path = ROOT / "backend" / "sound_design" / "t0103_native_fx.py"
    native_assets = [
        gov.freeze_native_asset(
            asset_id="LAISE-NATIVE-BRAAM-001",
            code_path=native_fx_path,
            seed=20260929,
            role="braam",
        ),
        gov.freeze_native_asset(
            asset_id="LAISE-NATIVE-PING-001",
            code_path=native_fx_path,
            seed=20260929,
            role="ping",
        ),
    ]

    governed_assets = list(unique_assets.values()) + native_assets
    promotions = [gov.evaluate_asset_promotion(a) for a in governed_assets]

    engine_paths = [
        ROOT / "backend" / "composition" / "phrase_engine.py",
        ROOT / "backend" / "composition" / "harmonic_narrative.py",
        ROOT / "backend" / "composition" / "t008_orchestration.py",
        ROOT / "backend" / "composition" / "t008_mix_intelligence.py",
        ROOT / "backend" / "composition" / "t009_instrument_realism.py",
        ROOT / "backend" / "asset_pipeline" / "t0102_semantic_catalog.py",
        ROOT / "backend" / "asset_pipeline" / "t0102_semantic_router.py",
        ROOT / "backend" / "asset_pipeline" / "t0103_governance.py",
        ROOT / "backend" / "sound_design" / "t0103_native_fx.py",
        ROOT / "backend" / "spatial" / "dearvr_adapter.py",
    ]

    runtime = gov.runtime_snapshot()
    engines = gov.engine_snapshot(engine_paths)

    attribution_lines = [
        "LAISE — Production Candidate Attribution",
        "",
        "Salamander Grand Piano v3",
        "Author: Alexander Holm",
        "License: Creative Commons Attribution 3.0 Unported (CC BY 3.0)",
        "Source: https://github.com/sfzinstruments/SalamanderGrandPiano",
        "",
        "VSCO 2 Community Edition",
        "License: Creative Commons Zero (CC0)",
        "Source: https://versilian-studios.com/vsco-community/",
        "",
        "sfizz runtime",
        "License: BSD 2-Clause",
        "Source: https://github.com/sfztools/sfizz",
        "",
        "Note: dearVR PRO 2 is a separately licensed runtime dependency.",
    ]
    ATTRIBUTION.write_text("\n".join(attribution_lines), encoding="utf-8")

    no_test_audio_assets = all(
        rec["asset_status"] != "TEST_ONLY"
        for rec in asset_records.values()
    )
    all_assets_promotable = all(p["eligible"] for p in promotions)
    runtime_frozen = (
        runtime["sfizz_render"]["exists"]
        and runtime["sfizz_render"]["sha256"]
        and runtime["dearvr_pro2"]["exists"]
        and runtime["dearvr_pro2"]["sha256"]
    )
    engines_frozen = all(x["exists"] and x["sha256"] for x in engines)

    checks = {
        "no_generaluser_audio_dependency": no_test_audio_assets,
        "native_braam_active": "braam" in dry,
        "native_ping_active": "ping" in dry,
        "all_sfz_dependency_closures_complete": all(
            a["dependency_closure_complete"] for a in governed_assets
        ),
        "all_assets_promotion_eligible": all_assets_promotable,
        "required_attribution_file_created": ATTRIBUTION.is_file(),
        "renderer_runtime_hashes_frozen": runtime_frozen,
        "engine_source_hashes_frozen": engines_frozen,
        "t008_lowmid_cleanup_preserved": cleanup_frames > 0,
        "t008_percussion_ducking_preserved": min_duck < .999,
        "mix_finite": bool(np.isfinite(mix).all()),
        "mix_non_silent":
            float(np.sqrt(np.mean(mix.astype(np.float64) ** 2))) > 1e-6,
        "mix_no_clipping": float(np.max(np.abs(mix))) < .999,
    }

    objective = "PASS" if all(checks.values()) else "FAIL"
    release_status = (
        "PRODUCTION_CANDIDATE"
        if objective == "PASS"
        else "DEVELOPMENT_ONLY"
    )

    governance_snapshot = {
        "governance_version": "LAISE-T010.3-1.0",
        "work_id": "LAISE-MUSIC-010",
        "release_status": release_status,
        "assets": governed_assets,
        "promotion_decisions": promotions,
        "runtime_snapshot": runtime,
        "engine_snapshot": engines,
        "attribution_file": str(ATTRIBUTION),
        "mix": {
            "path": str(MIX),
            "sha256": sha256_file(MIX),
        },
        "checks": checks,
        "note": (
            "PRODUCTION_CANDIDATE means the automated LAISE governance gate passed. "
            "It is not a legal opinion or guarantee of third-party rights."
        ),
    }
    GOV.write_text(
        json.dumps(governance_snapshot, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    manifest = {
        "work_id": "LAISE-MUSIC-010",
        "title": "Production Candidate 001",
        "engine": "T006+T007+T008+T009+T010.2+T010.3",
        "objective_result": objective,
        "perceptual_result": "PENDING",
        "release_status": release_status,
        "no_test_only_audio_assets": no_test_audio_assets,
        "native_fx": {
            "braam": "LAISE-NATIVE-BRAAM-001",
            "ping": "LAISE-NATIVE-PING-001",
        },
        "mix": str(MIX),
        "mix_sha256": sha256_file(MIX),
        "governance_snapshot": str(GOV),
        "attribution": str(ATTRIBUTION),
        "checks": checks,
    }
    MAN.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nAUTOMATED GOVERNANCE VALIDATION")
    for k, v in checks.items():
        print(f"{k:<58}{'PASS' if v else 'FAIL'}")

    print("\nMUSIC-010 / T010.3 OBJECTIVE RESULT:", objective)
    print("RELEASE STATUS:", release_status)
    print("PERCEPTUAL RESULT: PENDING")
    print("Mix:", MIX)
    print("SHA256:", sha256_file(MIX))
    print("Governance:", GOV)
    print("Attribution:", ATTRIBUTION)


if __name__ == "__main__":
    main()
