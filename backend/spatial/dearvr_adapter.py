from __future__ import annotations

from pathlib import Path
import numpy as np
from pedalboard import load_plugin

PLUGIN_PATH = Path(
    r"C:\Program Files\Common Files\VST3\dearVR PRO 2.vst3\Contents\x86_64-win\dearVR PRO 2.vst3"
)

# Calibrated during LAISE T001-H:
# dearVR raw distance ~= 0.0969899744 corresponds to 3.0 m.
# T003 v0.1.1 intentionally freezes distance at this validated point.
CALIBRATED_DISTANCE_M = 3.0
CALIBRATED_DISTANCE_RAW = 0.0969899744


def azimuth_to_raw(degrees: float) -> float:
    degrees = max(-180.0, min(180.0, float(degrees)))
    return (degrees + 180.0) / 360.0


def elevation_to_raw(degrees: float) -> float:
    degrees = max(-90.0, min(90.0, float(degrees)))
    return (degrees + 90.0) / 180.0


def _set_raw(parameter, value: float) -> None:
    parameter.raw_value = float(value)


def configure_direct_signal(plugin) -> None:
    p = plugin.parameters

    # T001-H: raw 1.0 = Polar.
    _set_raw(p["coordinate_system"], 1.0)

    # DirectSignal selection is optional here. If Pedalboard exposes the
    # discrete parameter as read-only text, we leave the current preset and
    # still explicitly disable reflections/reverb below.
    if "virtual_acoustics" in p:
        try:
            p["virtual_acoustics"].raw_value = 0.0
        except Exception:
            pass

    for name in ("reflection", "reverb"):
        if name in p:
            try:
                _set_raw(p[name], 0.0)
            except Exception:
                pass

    # Use the physically calibrated 3 m point from T001-H.
    _set_raw(p["distance"], CALIBRATED_DISTANCE_RAW)


def set_pose(plugin, azimuth_deg: float, elevation_deg: float) -> None:
    p = plugin.parameters
    _set_raw(p["azimuth"], azimuth_to_raw(azimuth_deg))
    _set_raw(p["elevation"], elevation_to_raw(elevation_deg))
    # Distance intentionally remains fixed at the validated 3 m raw value.


def interpolate_pose(keyframes: list[dict], t: float) -> tuple[float, float]:
    if not keyframes:
        raise ValueError("Trajectory has no keyframes")

    if t <= keyframes[0]["time_seconds"]:
        k = keyframes[0]
        return float(k["azimuth_deg"]), float(k["elevation_deg"])

    if t >= keyframes[-1]["time_seconds"]:
        k = keyframes[-1]
        return float(k["azimuth_deg"]), float(k["elevation_deg"])

    for a, b in zip(keyframes, keyframes[1:]):
        if a["time_seconds"] <= t <= b["time_seconds"]:
            span = b["time_seconds"] - a["time_seconds"]
            f = 0.0 if span <= 0 else (t - a["time_seconds"]) / span
            az = a["azimuth_deg"] + f * (b["azimuth_deg"] - a["azimuth_deg"])
            el = a["elevation_deg"] + f * (b["elevation_deg"] - a["elevation_deg"])
            return float(az), float(el)

    k = keyframes[-1]
    return float(k["azimuth_deg"]), float(k["elevation_deg"])


class DearVRRenderer:
    def __init__(self, sample_rate: int = 48000, buffer_size: int = 256):
        if not PLUGIN_PATH.is_file():
            raise FileNotFoundError(f"dearVR PRO 2 not found: {PLUGIN_PATH}")
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size

    def render(self, stereo_audio: np.ndarray, source: dict) -> np.ndarray:
        if stereo_audio.ndim != 2 or stereo_audio.shape[0] != 2:
            raise ValueError("Expected audio shape (2, samples)")

        plugin = load_plugin(str(PLUGIN_PATH))
        configure_direct_signal(plugin)

        out = np.zeros_like(stereo_audio, dtype=np.float32)
        n = stereo_audio.shape[1]
        first = True

        for start in range(0, n, self.buffer_size):
            end = min(start + self.buffer_size, n)
            t = start / self.sample_rate
            az, el = interpolate_pose(source["keyframes"], t)
            set_pose(plugin, az, el)

            block = stereo_audio[:, start:end].astype(np.float32, copy=False)
            processed = plugin.process(
                block,
                sample_rate=self.sample_rate,
                buffer_size=self.buffer_size,
                reset=first,
            )
            first = False

            if processed.shape[1] != block.shape[1]:
                processed = processed[:, :block.shape[1]]
            out[:, start:end] = processed

        gain = 10.0 ** (float(source.get("gain_db", 0.0)) / 20.0)
        return out * gain
