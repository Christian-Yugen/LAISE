from __future__ import annotations
import hashlib, json, platform, random, sys, wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pedalboard
from pedalboard import load_plugin

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPT_DIR = PROJECT_ROOT / "backend" / "spatial" / "optimization"
if str(OPT_DIR) not in sys.path:
    sys.path.insert(0, str(OPT_DIR))

from candidate_generator import generate_candidates
from acoustic_features import extract_features
from candidate_scorer import (
    score_candidate,
    select_exploration_exploitation,
    shortlist_diagnostics,
)
from perceptual_dataset import save_sheet

SR = 48000
DURATION = 5.0
AMP = 0.10
BUFFER = 256
SEED = 20260920

PLUGIN = Path(
    r"C:\Program Files\Common Files\VST3\dearVR PRO 2.vst3"
    r"\Contents\x86_64-win\dearVR PRO 2.vst3"
)

OUT = PROJECT_ROOT / "evidence" / "T001" / "T001-M-v02"
ALL_AUDIO = OUT / "all_candidates"
SHORT = OUT / "blind_shortlist"
PRIVATE = OUT / "PRIVATE"
RESULTS = OUT / "t001m_v02_results.json"
KEY = PRIVATE / "t001m_v02_blind_key.json"
SHEET = OUT / "listener_sheet.json"


def raw_az(d):
    return (max(-180.0, min(180.0, d)) + 180.0) / 360.0


def raw_el(d):
    return (max(-90.0, min(90.0, d)) + 90.0) / 180.0


def raw_dist(m):
    return round((max(0.1, min(30.0, m)) - 0.1) / 0.1) / 299.0


def raw_db(v):
    return (max(-96.0, min(24.0, v)) + 96.0) / 120.0


def setraw(plugin, name, value):
    if name not in plugin.parameters:
        raise RuntimeError(f"Missing parameter: {name}")
    plugin.parameters[name].raw_value = float(value)


def discrete(plugin, name, text):
    vals = [str(v).strip() for v in (plugin.parameters[name].valid_values or [])]
    if text not in vals:
        raise RuntimeError(
            f"{text!r} unavailable for {name}: {vals[:20]}"
        )
    setraw(
        plugin,
        name,
        0.0 if len(vals) == 1 else vals.index(text) / (len(vals) - 1),
    )


def stimulus():
    rng = np.random.default_rng(SEED)
    x = rng.normal(0, 1, int(SR * DURATION)).astype(np.float32)
    x /= max(np.max(np.abs(x)), 1e-12)
    x *= AMP
    return np.vstack([x, x]).astype(np.float32)


def render(inp, candidate):
    plugin = load_plugin(str(PLUGIN))

    setraw(plugin, "coordinate_system", 1.0)
    setraw(plugin, "azimuth", raw_az(candidate["azimuth_deg"]))
    setraw(plugin, "elevation", raw_el(candidate["elevation_deg"]))
    setraw(plugin, "distance", raw_dist(candidate["distance_m"]))
    setraw(plugin, "occlusion", 0.0)
    setraw(plugin, "performance_mode", 0.0)

    discrete(plugin, "virtual_acoustics", candidate["virtual_acoustics"])
    setraw(plugin, "reflection", 1.0 if candidate["reflection"] else 0.0)
    setraw(plugin, "reverb", 1.0 if candidate["reverb"] else 0.0)

    if candidate["reflection_gain_db"] is not None:
        setraw(
            plugin,
            "reflection_gain",
            raw_db(candidate["reflection_gain_db"]),
        )

    return np.asarray(
        plugin.process(
            inp,
            sample_rate=SR,
            buffer_size=BUFFER,
            reset=True,
        ),
        dtype=np.float32,
    )


def write_wav(path, audio):
    pcm = (np.clip(audio, -1, 1).T * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


print(
    "\n"
    + "=" * 78
    + "\nLAISE — T001-M v0.2\n"
    + "Automated Frontal Externalization Search — Exploration/Exploitation\n"
    + "=" * 78
)
print("Python:", platform.python_version())
print("Pedalboard:", pedalboard.__version__)
print("Plugin:", PLUGIN)

if not PLUGIN.is_file():
    raise SystemExit("Plugin not found.")

for directory in [OUT, ALL_AUDIO, SHORT, PRIVATE]:
    directory.mkdir(parents=True, exist_ok=True)

inp = stimulus()
candidates = generate_candidates()

print(f"\nGenerated configurations: {len(candidates)}")

records = []

reference_candidate = next(
    c for c in candidates
    if c["family"] == "dry_control" and c["distance_m"] == 3.0
)
reference_audio = render(inp, reference_candidate)
reference_features = extract_features(reference_audio, SR)

print("\nRendering and analyzing candidates...")

for i, candidate in enumerate(candidates, 1):
    audio = render(inp, candidate)
    features = extract_features(audio, SR)
    score, parts = score_candidate(features, reference_features)

    path = ALL_AUDIO / f'{candidate["candidate_id"]}.wav'
    write_wav(path, audio)

    records.append(
        {
            "candidate": candidate,
            "features": features,
            "acoustic_candidate_score": score,
            "score_components": parts,
            "sha256": sha256(path),
            "wav": str(path),
        }
    )

    print(
        f'{i:02d}/{len(candidates)}  '
        f'{candidate["candidate_id"]}  '
        f'score={score:.5f}'
    )

shortlist = select_exploration_exploitation(records, top_n=8)
diagnostics = shortlist_diagnostics(shortlist)

blind_ids = list("ABCDEFGH")
rng = random.Random(SEED + 1300)
shuffled_shortlist = shortlist.copy()
rng.shuffle(shuffled_shortlist)

key = {}

for blind_id, record in zip(blind_ids, shuffled_shortlist):
    source = Path(record["wav"])
    target = SHORT / f"t001m_{blind_id}.wav"
    target.write_bytes(source.read_bytes())

    key[blind_id] = {
        "candidate": record["candidate"],
        "features": record["features"],
        "acoustic_candidate_score": record["acoustic_candidate_score"],
        "score_components": record["score_components"],
        "source_candidate_id": record["candidate"]["candidate_id"],
    }

KEY.write_text(
    json.dumps(
        {
            "WARNING": "DO NOT OPEN BEFORE HUMAN RATINGS ARE FROZEN.",
            "selection_policy": "exploration_exploitation_v0.2",
            "shortlist_diagnostics": diagnostics,
            "mapping": key,
        },
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)

save_sheet(SHEET, blind_ids)

validations = {
    "candidate_count_correct": len(candidates) == 51,
    "all_finite": all(r["features"]["finite"] for r in records),
    "no_clipping": all(r["features"]["no_clipping"] for r in records),
    "shortlist_has_8": len(shortlist) == 8,
    "blind_files_created": all(
        (SHORT / f"t001m_{b}.wav").is_file()
        for b in blind_ids
    ),
    "diversity_gate": diagnostics["passes_diversity_gate"],
    "six_reflected_distances_represented": (
        diagnostics["reflected_distance_coverage_count"] >= 6
    ),
    "dry_controls_present": diagnostics["has_dry_controls"],
}

objective_result = (
    "PASS" if all(validations.values()) else "FAIL"
)

payload = {
    "test_id": "T001-M-v0.2",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "objective_result": objective_result,
    "human_result": "PENDING",
    "candidate_count": len(candidates),
    "reference_features": reference_features,
    "selection_policy": "exploration_exploitation_v0.2",
    "shortlist_diagnostics": diagnostics,
    "validations": validations,
    "shortlist": shortlist,
    "ranked_candidates": sorted(
        records,
        key=lambda r: r["acoustic_candidate_score"],
        reverse=True,
    ),
}

RESULTS.write_text(
    json.dumps(payload, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print("\n" + "-" * 78)
print("EXPLORATION / EXPLOITATION SHORTLIST")
print("-" * 78)

for rank, record in enumerate(shortlist, 1):
    candidate = record["candidate"]
    print(
        f'{rank:02d}. {candidate["candidate_id"]}  '
        f'score={record["acoustic_candidate_score"]:.5f}  '
        f'family={candidate["family"]:<16}  '
        f'distance={candidate["distance_m"]}m  '
        f'reflection_gain={candidate["reflection_gain_db"]}'
    )

print("\n" + "-" * 78)
print("SHORTLIST DIAGNOSTICS")
print("-" * 78)
print("Unique distances:", diagnostics["unique_distances"])
print(
    "Reflected distance coverage:",
    diagnostics["reflected_distance_coverage"],
)
print("Families:", diagnostics["families"])
print(
    "Diversity gate:",
    "PASS" if diagnostics["passes_diversity_gate"] else "FAIL",
)

print("\n" + "-" * 78)
print("VALIDATIONS")
print("-" * 78)

for key_name, value in validations.items():
    print(f"{key_name:<42}{'PASS' if value else 'FAIL'}")

print("\n" + "=" * 78)
print("T001-M v0.2 OBJECTIVE RESULT:", objective_result)
print("T001-M v0.2 HUMAN RESULT: PENDING")
print("=" * 78)

print("\nBlind shortlist:", SHORT)
print("Human sheet:", SHEET)
print("PRIVATE KEY — DO NOT OPEN:", KEY)
print("Full machine results:", RESULTS)
