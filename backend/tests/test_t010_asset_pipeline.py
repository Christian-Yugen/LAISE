from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PIPE=ROOT/"backend"/"asset_pipeline"
if str(PIPE) not in sys.path:
    sys.path.insert(0,str(PIPE))

from asset_registry import AssetRegistry
from instrument_router import InstrumentRouter, InstrumentRequest
from renderer_adapter import FluidSynthAssetAdapter, RenderJob, RendererRouter

MANIFEST=ROOT/"assets"/"t010_assets_manifest.json"
OUT=ROOT/"evidence"/"T010"
RESULT=OUT/"t010_asset_pipeline_result.json"
FS=ROOT/"tools"/"fluidsynth"/"bin"/"fluidsynth.exe"

def main():
    print("="*78)
    print("LAISE — T010 | Production Instrument Asset Pipeline v0.1")
    print("="*78)
    OUT.mkdir(parents=True,exist_ok=True)

    registry=AssetRegistry(ROOT,MANIFEST)
    verification=registry.verify("LAISE-SF-TEST-0001")
    router=InstrumentRouter(registry)

    dev_routes={}
    requests={
        "piano":"sustain",
        "strings":"legato",
        "brass":"marcato",
        "percussion":"hit",
        "countermelody":"legato",
    }
    for role,art in requests.items():
        resolved=router.resolve(InstrumentRequest(
            role=role,articulation=art,intensity=.70,mode="development"
        ))
        dev_routes[role]=resolved.__dict__

    production_blocked=False
    production_error=""
    try:
        router.resolve(InstrumentRequest(
            role="strings",articulation="legato",intensity=.70,mode="production"
        ))
    except PermissionError as e:
        production_blocked=True
        production_error=str(e)

    # Validate renderer abstraction without rendering audio.
    sample_route=dev_routes["piano"]
    RendererRouter.ensure_supported(sample_route["renderer"])
    adapter=FluidSynthAssetAdapter(FS)
    cmd=adapter.command(RenderJob(
        renderer=sample_route["renderer"],
        asset_path=sample_route["path"],
        midi_path=str(OUT/"example.mid"),
        output_path=str(OUT/"example.wav"),
        sample_rate=48000,
        gain=.8,
        program=sample_route["program"],
        channel=sample_route["channel"],
    ))

    provenance=registry.provenance_snapshot(["LAISE-SF-TEST-0001"])

    checks={
        "manifest_loaded":registry.schema_version=="LAISE-ASSET-REGISTRY-1.0",
        "asset_file_exists":verification["exists"],
        "asset_hash_verified":verification["hash_match"],
        "test_asset_development_allowed":registry.development_allowed("LAISE-SF-TEST-0001"),
        "test_asset_production_blocked":production_blocked,
        "router_resolves_five_roles":len(dev_routes)==5,
        "articulation_fallback_explicit":all(
            r["resolved_articulation"]=="performance_simulated"
            for r in dev_routes.values()
        ),
        "renderer_adapter_selected":sample_route["renderer"]=="fluidsynth",
        "renderer_command_constructed":len(cmd)>0 and str(FS)==cmd[0],
        "provenance_snapshot_created":len(provenance)==1 and provenance[0]["hash_verified"],
    }

    status="PASS" if all(checks.values()) else "FAIL"

    payload={
        "test":"T010",
        "engine":"LAISE Production Instrument Asset Pipeline v0.1",
        "objective_result":status,
        "asset_verification":verification,
        "development_routes":dev_routes,
        "production_gate":{
            "blocked":production_blocked,
            "reason":production_error,
        },
        "renderer_command_example":cmd,
        "provenance_snapshot":provenance,
        "checks":checks,
        "next_gate":"register first PRODUCTION_APPROVED orchestral asset(s)",
    }
    RESULT.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
    digest=hashlib.sha256(RESULT.read_bytes()).hexdigest()

    print("\nASSET")
    print("id:",verification["asset_id"])
    print("exists:",verification["exists"])
    print("hash_match:",verification["hash_match"])
    print("status:",verification["status"])
    print("license_state:",verification["license_state"])

    print("\nROUTING")
    for role,r in dev_routes.items():
        print(f"{role:<16} -> {r['asset_id']} | {r['requested_articulation']} "
              f"-> {r['resolved_articulation']} | {r['renderer']}")

    print("\nAUTOMATED VALIDATION")
    for k,v in checks.items():
        print(f"{k:<48}{'PASS' if v else 'FAIL'}")

    print("\nT010 OBJECTIVE RESULT:",status)
    print("Evidence:",RESULT)
    print("SHA256:",digest)

if __name__=="__main__":
    main()
