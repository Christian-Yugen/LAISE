from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class NativeFXConfig:
    sample_rate: int = 48000
    seed: int = 20260929


class NativeCinematicFX:
    """
    LAISE-native cinematic sound design.

    No sampled instrument asset is used here.  The waveform is generated
    deterministically from mathematical oscillators/noise and event timing.
    This replaces the final GeneralUser GS fallback used for braam/ping.
    """

    def __init__(self, config: NativeFXConfig = NativeFXConfig()):
        self.cfg = config

    @staticmethod
    def _equal_power_pan(mono: np.ndarray, pan: float) -> np.ndarray:
        pan = float(np.clip(pan, -1.0, 1.0))
        angle = (pan + 1.0) * math.pi / 4.0
        left = math.cos(angle) * mono
        right = math.sin(angle) * mono
        return np.vstack([left, right]).astype(np.float32)

    def braam(self, duration_s: float = 3.3) -> np.ndarray:
        sr = self.cfg.sample_rate
        n = max(1, round(duration_s * sr))
        t = np.arange(n, dtype=np.float64) / sr
        rng = np.random.default_rng(self.cfg.seed + 101)

        # Slight downward pitch glide with inharmonic upper partials.
        f0 = 52.0 - 10.0 * np.clip(t / 1.8, 0.0, 1.0)
        phase = 2.0 * np.pi * np.cumsum(f0) / sr
        body = (
            0.78 * np.sin(phase)
            + 0.34 * np.sin(phase * 2.01 + 0.4)
            + 0.20 * np.sin(phase * 3.17 + 1.1)
            + 0.11 * np.sin(phase * 5.03 + 0.7)
        )

        transient = rng.standard_normal(n)
        transient *= np.exp(-t / 0.055) * 0.30

        # Slow attack, large body, cinematic decay.
        attack = 1.0 - np.exp(-t / 0.032)
        decay = np.exp(-t / 1.65)
        env = attack * decay

        mono = np.tanh((body * env + transient) * 1.55)
        stereo = self._equal_power_pan(mono.astype(np.float32), -0.05)

        # Small deterministic Haas spread.
        delay = round(0.011 * sr)
        if delay < n:
            stereo[1, delay:] += stereo[0, :-delay] * 0.16

        peak = float(np.max(np.abs(stereo))) + 1e-12
        return (stereo * (0.78 / peak)).astype(np.float32)

    def ping(self, duration_s: float = 4.2) -> np.ndarray:
        sr = self.cfg.sample_rate
        n = max(1, round(duration_s * sr))
        t = np.arange(n, dtype=np.float64) / sr

        f = 1760.0
        main = np.sin(2.0 * np.pi * f * t)
        upper = 0.24 * np.sin(2.0 * np.pi * f * 2.01 * t + 0.6)
        shimmer = 0.10 * np.sin(2.0 * np.pi * f * 3.97 * t + 1.2)

        attack = 1.0 - np.exp(-t / 0.0025)
        decay = np.exp(-t / 1.15)
        mono = (main + upper + shimmer) * attack * decay

        stereo = self._equal_power_pan(mono.astype(np.float32), 0.12)

        # Multi-tap spatial tail, generated mathematically.
        for ms, gain, swap in ((170, 0.27, True), (340, 0.16, False), (690, 0.09, True)):
            d = round(ms * sr / 1000.0)
            if d < n:
                src = stereo[::-1] if swap else stereo
                stereo[:, d:] += src[:, :-d] * gain

        peak = float(np.max(np.abs(stereo))) + 1e-12
        return (stereo * (0.62 / peak)).astype(np.float32)

    def place_events(
        self,
        notes,
        effect: str,
        total_samples: int,
        ppq: int,
        bpm: float,
    ) -> np.ndarray:
        sr = self.cfg.sample_rate
        out = np.zeros((2, total_samples), dtype=np.float32)
        one = self.braam() if effect == "braam" else self.ping()

        seconds_per_tick = 60.0 / (bpm * ppq)

        for note in notes:
            start_s = note.start * seconds_per_tick
            start = round(start_s * sr)
            if start >= total_samples:
                continue

            vel = float(np.clip(note.velocity / 100.0, 0.35, 1.20))
            end = min(total_samples, start + one.shape[1])
            out[:, start:end] += one[:, : end - start] * vel

        peak = float(np.max(np.abs(out)))
        if peak > 0.88:
            out *= 0.88 / peak
        return out
