from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json

SCENE_VERSION = "LAISE Spatial Scene v0.1.1"
FIXED_DISTANCE_M = 3.0


@dataclass(frozen=True)
class SpatialKeyframe:
    time_seconds: float
    azimuth_deg: float
    elevation_deg: float
    distance_m: float = FIXED_DISTANCE_M


@dataclass(frozen=True)
class SpatialSource:
    source_id: str
    input_file: str
    trajectory: str
    gain_db: float
    keyframes: list[SpatialKeyframe]


def _make(duration, points):
    return [
        SpatialKeyframe(duration * fraction, azimuth, elevation)
        for fraction, azimuth, elevation in points
    ]


def _lead(duration):
    return _make(duration, [
        (0.00,-55,0),(0.12,-25,4),(0.25,15,0),(0.38,55,6),
        (0.50,20,0),(0.62,-35,5),(0.75,-60,0),(0.88,35,4),(1.00,0,0),
    ])


def _pad(duration):
    return _make(duration, [
        (0.00,-30,12),(0.25,-10,16),(0.50,25,12),(0.75,10,18),(1.00,-30,12),
    ])


def _bass(duration):
    return _make(duration, [(0.00,-4,-3),(0.50,4,-3),(1.00,-4,-3)])


def _drums(duration):
    return _make(duration, [
        (0.00,-42,2),(0.125,38,4),(0.25,-18,-2),(0.375,48,6),
        (0.50,-50,3),(0.625,22,-2),(0.75,52,5),(0.875,-28,2),(1.00,0,0),
    ])


def build_scene(stem_paths: dict[str, str | Path], duration_seconds: float) -> dict:
    required={"strings_pad","bass_sub","drums_impacts","lead_melody"}
    missing=required-set(stem_paths)
    if missing:
        raise ValueError(f"Missing stems: {sorted(missing)}")

    sources=[
        SpatialSource("strings_pad",str(Path(stem_paths["strings_pad"])),"wide_slow_motion",-5.0,_pad(duration_seconds)),
        SpatialSource("bass_sub",str(Path(stem_paths["bass_sub"])),"center_anchor",-3.0,_bass(duration_seconds)),
        SpatialSource("drums_impacts",str(Path(stem_paths["drums_impacts"])),"alternating_stage_motion",-7.0,_drums(duration_seconds)),
        SpatialSource("lead_melody",str(Path(stem_paths["lead_melody"])),"dynamic_lateral_motion",-2.0,_lead(duration_seconds)),
    ]

    return {
        "scene_version":SCENE_VERSION,
        "coordinate_system":{
            "type":"polar",
            "azimuth":"degrees; 0=front, -90=left, +90=right, ±180=back",
            "elevation":"degrees; 0=horizon, +up, -down",
            "distance":"meters",
        },
        "duration_seconds":duration_seconds,
        "renderer_policy":{
            "laise_owns_scene":True,
            "renderer":"dearVR PRO 2",
            "distance_policy":"FIXED_CALIBRATED_3M",
            "distance_m":FIXED_DISTANCE_M,
            "distance_raw":0.0969899744,
            "reason":"Pedalboard exposes dearVR distance text as read-only; T003 freezes the T001-H calibrated 3 m point instead of inventing a raw mapping.",
            "reflection":False,
            "reverb":False,
            "known_limitation":"convincing frontal externalization remains unresolved",
        },
        "sources":[{
            **{k:v for k,v in asdict(s).items() if k!="keyframes"},
            "keyframes":[asdict(k) for k in s.keyframes],
        } for s in sources],
    }


def write_scene(path: str | Path, scene: dict) -> None:
    Path(path).write_text(json.dumps(scene,indent=2,ensure_ascii=False),encoding="utf-8")
