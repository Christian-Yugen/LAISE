from __future__ import annotations

import math
import numpy as np


class ContextualCinematicFX:
    """
    T011.2.1 pitch-aware cinematic FX.

    Unlike the T010 fixed-frequency prototypes, every event receives a MIDI
    pitch chosen by the Harmonic Safety Engine from the current chord.
    """

    def __init__(
        self,
        sample_rate: int = 48000,
        seed: int = 12012,
    ):
        self.sr = int(sample_rate)
        self.seed = int(seed)

    @staticmethod
    def midi_to_hz(pitch: int) -> float:
        return 440.0 * (
            2.0 ** ((int(pitch) - 69) / 12.0)
        )

    @staticmethod
    def _pan(
        mono: np.ndarray,
        pan: float,
    ) -> np.ndarray:
        pan = float(np.clip(pan, -1.0, 1.0))
        angle = (pan + 1.0) * math.pi / 4.0
        return np.vstack(
            [
                np.cos(angle) * mono,
                np.sin(angle) * mono,
            ]
        ).astype(np.float32)

    def braam(
        self,
        midi_pitch: int,
        duration_s: float = 3.4,
    ) -> np.ndarray:
        sr = self.sr
        n = max(1, int(round(duration_s * sr)))
        t = np.arange(n, dtype=np.float64) / sr

        rng = np.random.default_rng(
            self.seed + int(midi_pitch) * 17
        )

        target = self.midi_to_hz(midi_pitch)
        start_f = target * 1.13

        glide = np.clip(t / 1.55, 0.0, 1.0)
        f0 = start_f + (target - start_f) * glide
        phase = (
            2.0
            * np.pi
            * np.cumsum(f0)
            / sr
        )

        body = (
            0.78 * np.sin(phase)
            + 0.30 * np.sin(phase * 2.0 + 0.37)
            + 0.17 * np.sin(phase * 3.01 + 0.92)
            + 0.08 * np.sin(phase * 5.02 + 1.41)
        )

        transient = rng.standard_normal(n)
        transient *= np.exp(-t / 0.060) * 0.19

        attack = 1.0 - np.exp(-t / 0.038)
        decay = np.exp(-t / 1.72)
        mono = np.tanh(
            (body * attack * decay + transient)
            * 1.35
        )

        stereo = self._pan(
            mono.astype(np.float32),
            -0.04,
        )

        delay = int(round(0.012 * sr))
        if delay < n:
            stereo[1, delay:] += (
                stereo[0, :-delay] * 0.13
            )

        peak = float(np.max(np.abs(stereo))) + 1e-12
        return (
            stereo * (0.72 / peak)
        ).astype(np.float32)

    def ping(
        self,
        midi_pitch: int,
        duration_s: float = 4.0,
    ) -> np.ndarray:
        sr = self.sr
        n = max(1, int(round(duration_s * sr)))
        t = np.arange(n, dtype=np.float64) / sr
        f = self.midi_to_hz(midi_pitch)

        main = np.sin(2.0 * np.pi * f * t)
        upper = 0.18 * np.sin(
            2.0 * np.pi * f * 2.0 * t + 0.51
        )
        shimmer = 0.07 * np.sin(
            2.0 * np.pi * f * 3.0 * t + 1.07
        )

        attack = 1.0 - np.exp(-t / 0.0032)
        decay = np.exp(-t / 1.22)

        mono = (
            main + upper + shimmer
        ) * attack * decay

        stereo = self._pan(
            mono.astype(np.float32),
            0.10,
        )

        for ms, gain, cross in (
            (155, 0.21, True),
            (311, 0.13, False),
            (623, 0.07, True),
        ):
            delay = int(round(ms * sr / 1000.0))
            if delay < n:
                src = stereo[::-1] if cross else stereo
                stereo[:, delay:] += (
                    src[:, :-delay] * gain
                )

        peak = float(np.max(np.abs(stereo))) + 1e-12
        return (
            stereo * (0.56 / peak)
        ).astype(np.float32)

    def render_event(
        self,
        role: str,
        midi_pitch: int,
    ) -> np.ndarray:
        if role == "braam":
            return self.braam(midi_pitch)
        if role == "ping":
            return self.ping(midi_pitch)
        raise ValueError(f"Unsupported FX role: {role}")
