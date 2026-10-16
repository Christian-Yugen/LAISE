"""Aggregate approved metadata; write only the Visualizer technical manifest."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VISUALIZER = ROOT / "visualizer"
EXPERIMENTS = ROOT / "projects/tukana_02_a_mata_se_move/experiments"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build_manifest():
    paths = {
        "mastering": EXPERIMENTS / "TUK2_T008R1/reports/TUK2_T008R1_master_adjudication.json",
        "delivery": EXPERIMENTS / "TUK2_T009/reports/TUK2_T009_delivery_validation.json",
        "spatial": EXPERIMENTS / "TUK2_T007/spatial_scenes/TUK2_T007_automation_manifest.json",
        "cues": VISUALIZER / "public/audio/tukana-stem-cues.json",
    }
    data = {key: json.loads(path.read_text(encoding="utf-8-sig")) for key, path in paths.items()}
    mastering, delivery, cues = (data[key] for key in ("mastering", "delivery", "cues"))
    assert mastering["status"] == delivery["status"] == "PASS"
    assert delivery["release_state"] == "FINAL_DELIVERY_VALIDATED"
    artifact = delivery["artifacts"]["wav_pcm24_48k"]
    master = VISUALIZER / "public" / cues["master"]["url"].lstrip("/")
    assert digest(master) == cues["master"]["sha256"] == artifact["sha256"] == mastering["approved_PCM"]["sha256"]
    assert digest(paths["spatial"]) == cues["analysis"]["manifestSha256"]
    for stem in cues["stems"]:
        path = ROOT / stem["file"]
        assert path.resolve().is_relative_to((EXPERIMENTS / "TUK2_T007/spatial_stems").resolve())
        assert digest(path) == stem["sha256"]
    assert len({stem["id"] for stem in cues["stems"]}) == len(cues["stems"]) > 0
    metrics = mastering["selected_metrics"]
    for key in ("integrated_lufs", "true_peak_dbtp", "spatial_integrity"):
        assert metrics[key] == delivery["final_master_metrics"][key]
    fmt = artifact["format"]
    assert float(fmt["duration"]) == cues["duration"]
    return {
        "schema_version": "laise-visualizer-manifest-v1",
        "track": "Tukãna — A Mata se Move",
        "master_url": cues["master"]["url"],
        "master_sha256": artifact["sha256"],
        "master_label": "LAISE FINAL MASTER",
        "duration_seconds": float(fmt["duration"]),
        "sample_rate": int(fmt["sample_rate"]),
        "channels": fmt["channels"],
        "source_count": len(cues["stems"]),
        "spatial_source": "T007",
        "integrated_lufs": metrics["integrated_lufs"],
        "true_peak_dbtp": metrics["true_peak_dbtp"],
        "spatial_integrity": metrics["spatial_integrity"],
        "delivery_status": "VALIDATED",
        "delivery_source": "T009",
        "visualizer_version": "V1.1",
        "stems_state": "READY",
        "motion_state": "OFFLINE",
        "provenance": {
            key: {"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path)}
            for key, path in paths.items()
        },
    }


if __name__ == "__main__":
    output = VISUALIZER / "public/audio/tukana-visualizer-manifest.json"
    output.write_text(json.dumps(build_manifest(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
