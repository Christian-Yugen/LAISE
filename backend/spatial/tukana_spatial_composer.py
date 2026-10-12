from __future__ import annotations

from pathlib import Path
import json


def _keyframe(time: float, azimuth: float, elevation: float, distance: float,
              reason: str, gain_db: float = 0.0, width: float = 1.0) -> dict:
    return {
        "time_seconds": round(float(time), 6),
        "azimuth_deg_unwrapped": float(azimuth),
        "elevation_deg": float(elevation),
        "distance_m_artistic_intent": float(distance),
        "gain_db": float(gain_db),
        "width": float(width),
        "reason": reason,
    }


def _active_at(regions: list[dict], time: float) -> bool:
    return any(region["start_seconds"] <= time <= region["end_seconds"] for region in regions)


def _deduplicate(keyframes: list[dict]) -> list[dict]:
    ordered = sorted(keyframes, key=lambda item: item["time_seconds"])
    result = []
    for item in ordered:
        if result and item["time_seconds"] == result[-1]["time_seconds"]:
            result[-1] = item
        else:
            result.append(item)
    return result


def _percussion_motion(base: dict, musical_map: dict, duration: float) -> list[dict]:
    lead_regions = musical_map["stem_events"]["lead_vocal"]["active_regions"]
    percussion_regions = musical_map["stem_events"]["percussion"]["active_regions"]
    start_azimuth = base["azimuth_deg"]
    keyframes = [_keyframe(0, start_azimuth, base["elevation_deg"], base["distance_m"],
                           "profile anchor; awaiting a safe instrumental window")]
    orbit_count = 0
    for section in musical_map["sections"]:
        start, end = section["start_seconds"], section["end_seconds"]
        midpoint = (start + end) / 2
        if end - start < 8 or _active_at(lead_regions, midpoint) or not _active_at(percussion_regions, midpoint):
            continue
        orbit_count += 1
        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
            keyframes.append(_keyframe(
                start + (end - start) * fraction,
                start_azimuth + 360.0 * fraction,
                base["elevation_deg"] + 6.0 * (1.0 - abs(0.5 - fraction) * 2.0),
                base["distance_m"],
                f"full orbit {orbit_count}: percussion active while lead vocal is absent",
                gain_db=-1.5,
            ))
        if orbit_count == 1:
            break
    keyframes.append(_keyframe(duration, start_azimuth, base["elevation_deg"], base["distance_m"],
                               "return to profile anchor"))
    return _deduplicate(keyframes)


def build_tukana_scene(import_manifest: dict, musical_map: dict, profile: dict) -> dict:
    duration = float(import_manifest["timeline_duration_seconds"])
    sources = []
    for role, stem in import_manifest["stems"].items():
        base = profile["sources"][role]
        azimuth, elevation, distance = (
            base["azimuth_deg"], base["elevation_deg"], base["distance_m"]
        )
        if role == "percussion":
            trajectory = "phrase_synced_orbit_candidate"
            keyframes = _percussion_motion(base, musical_map, duration)
        elif role == "woodwinds":
            trajectory = "transition_synced_traverse"
            keyframes = [_keyframe(0, azimuth, elevation, distance, "profile anchor")]
            direction = 1
            for event in musical_map["transitions"]:
                time = event["time_seconds"]
                keyframes.extend([
                    _keyframe(max(0, time - 1.5), azimuth, elevation, distance,
                              "prepare woodwind motion at detected transition"),
                    _keyframe(min(duration, time + 1.5), azimuth + direction * 70,
                              min(45, elevation + 12), distance,
                              "woodwind traverse follows ensemble transition", -1.0),
                ])
                direction *= -1
            keyframes.append(_keyframe(duration, azimuth, elevation, distance, "return to anchor"))
            keyframes = _deduplicate(keyframes)
        elif role == "synth":
            trajectory = "slow_atmospheric_elevation"
            keyframes = [
                _keyframe(0, azimuth, elevation, distance, "distant atmospheric anchor", -2.0),
                _keyframe(duration / 2, azimuth + 25, min(55, elevation + 15), distance,
                          "slow elevation across composition", -2.0),
                _keyframe(duration, azimuth, elevation, distance, "return to atmospheric anchor", -2.0),
            ]
        elif role == "backing_vocals":
            trajectory = "section_aware_chorus_expansion"
            keyframes = [_keyframe(0, azimuth, elevation, distance, "centered backing-vocal anchor", -1.0)]
            for section in musical_map["sections"]:
                if section["label"] in ("chorus", "climax"):
                    keyframes.extend([
                        _keyframe(section["start_seconds"], -28, elevation, distance,
                                  "expand backing vocals in high-energy section", -1.0, 1.3),
                        _keyframe(section["end_seconds"], 28, elevation, distance,
                                  "complete controlled chorus expansion", -1.0, 1.3),
                    ])
            keyframes.append(_keyframe(duration, azimuth, elevation, distance, "return to vocal center", -1.0))
            keyframes = _deduplicate(keyframes)
        else:
            trajectory = "stable_anchor" if role in ("lead_vocal", "drums", "bass") else base["behavior"]
            keyframes = [
                _keyframe(0, azimuth, elevation, distance, f"{role} profile anchor"),
                _keyframe(duration, azimuth, elevation, distance, f"preserve {role} anchor"),
            ]
        sources.append({
            "source_id": role, "input_file": stem["path"], "trajectory": trajectory,
            "keyframes": keyframes, "analysis_events_used": True,
        })

    return {
        "schema": "LAISE Spatial Scene v1.0", "project": "tukana",
        "profile_id": profile["profile_id"], "profile_version": profile["version"],
        "variant": "balanced", "duration_seconds": duration,
        "coordinate_system": {"type": "polar", "azimuth": "unwrapped degrees; 0=front",
                              "elevation": "degrees; positive=up", "distance": "meters artistic intent"},
        "renderer_policy": {
            "scene_is_renderer_independent": True, "requested_distance_is_not_claimed_as_applied": True,
            "dearvr_current_distance_m": 3.0, "dearvr_current_distance_raw": 0.0969899744,
            "frontal_externalization": "PENDING_HUMAN_VALIDATION",
        },
        "musical_map_summary": {"bpm": musical_map["bpm"],
                                "section_count": len(musical_map["sections"]),
                                "transition_count": len(musical_map["transitions"])},
        "sources": sources,
    }


def write_tukana_scene(import_manifest_path: str | Path, musical_map_path: str | Path,
                       profile_path: str | Path, output_path: str | Path) -> dict:
    load = lambda path: json.loads(Path(path).read_text(encoding="utf-8-sig"))
    scene = build_tukana_scene(load(import_manifest_path), load(musical_map_path), load(profile_path))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(scene, indent=2, ensure_ascii=False), encoding="utf-8")
    return scene
