from __future__ import annotations

from pathlib import Path
import numpy as np
from pedalboard import load_plugin

PLUGIN_PATH = Path(
    r"C:\Program Files\Common Files\VST3\dearVR PRO 2.vst3\Contents\x86_64-win\dearVR PRO 2.vst3"
)
CALIBRATED_DISTANCE_M = 3.0
CALIBRATED_DISTANCE_RAW = 0.0969899744


def wrap_azimuth(degrees: float) -> float:
    """Translate an unwrapped Composer angle to dearVR [-180, 180)."""
    return ((float(degrees) + 180.0) % 360.0) - 180.0


def azimuth_to_raw(degrees: float) -> float:
    return (wrap_azimuth(degrees) + 180.0) / 360.0


def elevation_to_raw(degrees: float) -> float:
    degrees = max(-90.0, min(90.0, float(degrees)))
    return (degrees + 90.0) / 180.0


def _set_raw(parameter, value: float) -> None:
    parameter.raw_value = float(value)


def configure_direct_signal(plugin) -> None:
    parameters = plugin.parameters
    _set_raw(parameters["coordinate_system"], 1.0)
    if "virtual_acoustics" in parameters:
        try:
            parameters["virtual_acoustics"].raw_value = 0.0
        except Exception:
            pass
    for name in ("reflection", "reverb"):
        if name in parameters:
            try:
                _set_raw(parameters[name], 0.0)
            except Exception:
                pass
    _set_raw(parameters["distance"], CALIBRATED_DISTANCE_RAW)


def set_pose(plugin, azimuth_deg: float, elevation_deg: float) -> None:
    parameters = plugin.parameters
    _set_raw(parameters["azimuth"], azimuth_to_raw(azimuth_deg))
    _set_raw(parameters["elevation"], elevation_to_raw(elevation_deg))


def _keyframe_azimuth(keyframe: dict) -> float:
    if "azimuth_deg_unwrapped" in keyframe:
        return float(keyframe["azimuth_deg_unwrapped"])
    return float(keyframe["azimuth_deg"])


def interpolate_keyframe_value(keyframes: list[dict], time_seconds: float,
                               name: str, default: float) -> float:
    if not keyframes:
        return float(default)
    if time_seconds <= keyframes[0]["time_seconds"]:
        return float(keyframes[0].get(name, default))
    if time_seconds >= keyframes[-1]["time_seconds"]:
        return float(keyframes[-1].get(name, default))
    for first, second in zip(keyframes, keyframes[1:]):
        if first["time_seconds"] <= time_seconds <= second["time_seconds"]:
            span = second["time_seconds"] - first["time_seconds"]
            fraction = 0.0 if span <= 0 else (time_seconds - first["time_seconds"]) / span
            start = float(first.get(name, default))
            end = float(second.get(name, default))
            return start + fraction * (end - start)
    return float(default)

def interpolate_pose(keyframes: list[dict], time_seconds: float) -> tuple[float, float]:
    if not keyframes:
        raise ValueError("Trajectory has no keyframes")
    if time_seconds <= keyframes[0]["time_seconds"]:
        keyframe = keyframes[0]
        return _keyframe_azimuth(keyframe), float(keyframe["elevation_deg"])
    if time_seconds >= keyframes[-1]["time_seconds"]:
        keyframe = keyframes[-1]
        return _keyframe_azimuth(keyframe), float(keyframe["elevation_deg"])
    for first, second in zip(keyframes, keyframes[1:]):
        if first["time_seconds"] <= time_seconds <= second["time_seconds"]:
            span = second["time_seconds"] - first["time_seconds"]
            fraction = 0.0 if span <= 0 else (time_seconds - first["time_seconds"]) / span
            first_azimuth = _keyframe_azimuth(first)
            second_azimuth = _keyframe_azimuth(second)
            azimuth = first_azimuth + fraction * (second_azimuth - first_azimuth)
            elevation = first["elevation_deg"] + fraction * (second["elevation_deg"] - first["elevation_deg"])
            return float(azimuth), float(elevation)
    keyframe = keyframes[-1]
    return _keyframe_azimuth(keyframe), float(keyframe["elevation_deg"])


class DearVRRenderer:
    def __init__(self, sample_rate: int = 48000, buffer_size: int = 256):
        if not PLUGIN_PATH.is_file():
            raise FileNotFoundError(f"dearVR PRO 2 not found: {PLUGIN_PATH}")
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size

    def render(self, stereo_audio: np.ndarray, source: dict,
               timeline_offset_seconds: float = 0.0) -> np.ndarray:
        if stereo_audio.ndim != 2 or stereo_audio.shape[0] != 2:
            raise ValueError("Expected audio shape (2, samples)")
        plugin = load_plugin(str(PLUGIN_PATH))
        configure_direct_signal(plugin)
        output = np.zeros_like(stereo_audio, dtype=np.float32)
        first_block = True
        for start in range(0, stereo_audio.shape[1], self.buffer_size):
            end = min(start + self.buffer_size, stereo_audio.shape[1])
            time_seconds = timeline_offset_seconds + start / self.sample_rate
            azimuth, elevation = interpolate_pose(source["keyframes"], time_seconds)
            set_pose(plugin, azimuth, elevation)
            block = stereo_audio[:, start:end].astype(np.float32, copy=False)
            processed = plugin.process(
                block, sample_rate=self.sample_rate,
                buffer_size=self.buffer_size, reset=first_block,
            )
            first_block = False
            if processed.shape[1] != block.shape[1]:
                processed = processed[:, :block.shape[1]]
            keyframe_gain_db = interpolate_keyframe_value(
                source["keyframes"], time_seconds, "gain_db", 0.0
            )
            gain_db = float(source.get("gain_db", 0.0)) + keyframe_gain_db
            output[:, start:end] = processed * (10.0 ** (gain_db / 20.0))
        return output
