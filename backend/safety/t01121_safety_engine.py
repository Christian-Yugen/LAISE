from __future__ import annotations

from dataclasses import dataclass, asdict
import math
from typing import Iterable

import numpy as np

from production_composer import (
    BAR,
    PPQ,
    MAJOR_SCALE,
    MINOR_SCALE,
    NOTE_PC,
)


@dataclass(frozen=True)
class SafetyCorrection:
    role: str
    start_tick: int
    original_pitch: int | None
    corrected_pitch: int | None
    reason: str
    detail: str


@dataclass(frozen=True)
class ImpactDiagnostic:
    role: str
    start_tick: int
    start_seconds: float
    section: str
    context_rms_db: float
    orchestral_post_rms_db: float
    raw_fx_rms_db: float
    allowed_delta_db: float
    applied_gain_db: float
    final_fx_rms_db: float


class HarmonicDynamicTransitionSafety:
    """
    T011.2.1 — Harmonic, Dynamic & Transition Safety Engine.

    This module does not compose a song. It validates and repairs a generated
    score before rendering so that future songs do not repeat the localized
    failures heard in MUSIC-011.

    Guards:
      1) Harmonic Guard
      2) FX Tonal Guard
      3) Accent Collision Guard
      4) Section-aware dramatic-impact policy
      5) Render-time contextual FX gain guard
    """

    ACCENT_ROLES = (
        "braam",
        "percussion_cymbal",
        "brass_attack",
        "ping",
    )

    ACCENT_PRIORITY = {
        "braam": 100,
        "percussion_cymbal": 80,
        "brass_attack": 65,
        "ping": 45,
    }

    def __init__(self, plan):
        self.plan = plan
        self.scale = (
            MAJOR_SCALE if plan.mode == "major" else MINOR_SCALE
        )
        self.key_pc = NOTE_PC[plan.key]
        self.corrections: list[SafetyCorrection] = []

    # ------------------------------------------------------------------
    # Harmonic context
    # ------------------------------------------------------------------

    def section_for_tick(self, tick: int):
        bar = max(0, int(tick) // BAR)
        for section in self.plan.sections:
            if section.start_bar <= bar < section.start_bar + section.bars:
                return section
        return self.plan.sections[-1]

    def degree_for_tick(self, tick: int) -> int:
        bar = max(0, int(tick) // BAR)
        section = self.section_for_tick(tick)
        local = bar - section.start_bar
        progression = self.plan.progression_by_section[section.name]
        return int(progression[local % len(progression)])

    def scale_pcs(self) -> set[int]:
        return {
            (self.key_pc + interval) % 12
            for interval in self.scale
        }

    def chord_pcs(self, tick: int) -> set[int]:
        degree = self.degree_for_tick(tick) % 7
        pcs = set()
        for offset in (0, 2, 4):
            idx = degree + offset
            pc = (
                self.key_pc
                + self.scale[idx % 7]
                + 12 * (idx // 7)
            ) % 12
            pcs.add(pc)
        return pcs

    def chord_root_pc(self, tick: int) -> int:
        degree = self.degree_for_tick(tick) % 7
        return (self.key_pc + self.scale[degree]) % 12

    @staticmethod
    def _pc_distance(a: int, b: int) -> int:
        d = abs((a - b) % 12)
        return min(d, 12 - d)

    @staticmethod
    def _candidate_pitches_for_pcs(
        center: int,
        allowed_pcs: set[int],
        radius: int = 12,
    ) -> list[int]:
        low = max(0, center - radius)
        high = min(127, center + radius)
        return [
            p for p in range(low, high + 1)
            if p % 12 in allowed_pcs
        ]

    def _nearest_allowed_pitch(
        self,
        pitch: int,
        allowed_pcs: set[int],
        previous_pitch: int | None,
    ) -> int:
        candidates = self._candidate_pitches_for_pcs(
            pitch,
            allowed_pcs,
            radius=12,
        )
        if not candidates:
            return pitch

        desired_direction = 0
        if previous_pitch is not None:
            if pitch < previous_pitch:
                desired_direction = -1
            elif pitch > previous_pitch:
                desired_direction = 1

        def rank(candidate: int):
            distance = abs(candidate - pitch)

            if previous_pitch is None or desired_direction == 0:
                direction_penalty = 0
            else:
                actual = (
                    -1 if candidate < previous_pitch
                    else 1 if candidate > previous_pitch
                    else 0
                )
                direction_penalty = (
                    0 if actual == desired_direction
                    else 1
                )

            leap = (
                abs(candidate - previous_pitch)
                if previous_pitch is not None
                else 0
            )

            return (
                distance,
                direction_penalty,
                leap,
                candidate,
            )

        return min(candidates, key=rank)

    # ------------------------------------------------------------------
    # Harmonic Guard
    # ------------------------------------------------------------------

    def _repair_melodic_role(
        self,
        role: str,
        notes: list,
    ) -> list:
        repaired = []
        previous_pitch = None
        scale_pcs = self.scale_pcs()

        for note in sorted(notes, key=lambda n: (n.start, n.pitch)):
            original = int(note.pitch)
            pitch = original
            section = self.section_for_tick(note.start)
            chord = self.chord_pcs(note.start)

            # 1. No accidental chromatic note unless it is deliberately
            # introduced by a later expressive-chromatic subsystem.
            if pitch % 12 not in scale_pcs:
                pitch = self._nearest_allowed_pitch(
                    pitch,
                    scale_pcs,
                    previous_pitch,
                )
                self.corrections.append(
                    SafetyCorrection(
                        role,
                        note.start,
                        original,
                        pitch,
                        "OUT_OF_KEY",
                        (
                            f"{section.name}: snapped chromatic note "
                            f"to nearest in-key pitch."
                        ),
                    )
                )

            # 2. During resolution, exposed semitone friction against the
            # sustaining chord is not allowed unless the note itself is a
            # chord tone.
            if section.name == "homecoming":
                pc = pitch % 12
                minor_second_collision = (
                    pc not in chord
                    and any(
                        self._pc_distance(pc, c) == 1
                        for c in chord
                    )
                )

                if minor_second_collision:
                    old = pitch
                    pitch = self._nearest_allowed_pitch(
                        pitch,
                        chord,
                        previous_pitch,
                    )
                    self.corrections.append(
                        SafetyCorrection(
                            role,
                            note.start,
                            old,
                            pitch,
                            "RESOLUTION_MINOR_SECOND",
                            (
                                "Homecoming exposed semitone collision "
                                "re-voiced to a stable chord tone."
                            ),
                        )
                    )

                # 3. Resolution voice-leading should be mostly conjunct.
                if (
                    previous_pitch is not None
                    and abs(pitch - previous_pitch) > 8
                ):
                    candidates = self._candidate_pitches_for_pcs(
                        pitch,
                        scale_pcs,
                        radius=18,
                    )
                    if candidates:
                        best = min(
                            candidates,
                            key=lambda p: (
                                abs(p - previous_pitch),
                                abs(p - pitch),
                            ),
                        )
                        if abs(best - previous_pitch) < abs(pitch - previous_pitch):
                            old = pitch
                            pitch = best
                            self.corrections.append(
                                SafetyCorrection(
                                    role,
                                    note.start,
                                    old,
                                    pitch,
                                    "RESOLUTION_VOICE_LEADING",
                                    (
                                        "Large homecoming leap reduced "
                                        "while remaining in key."
                                    ),
                                )
                            )

            repaired.append(
                type(note)(
                    note.start,
                    note.duration,
                    int(pitch),
                    note.velocity,
                    note.channel,
                )
            )
            previous_pitch = int(pitch)

        return repaired

    # ------------------------------------------------------------------
    # FX Tonal Guard
    # ------------------------------------------------------------------

    @staticmethod
    def _midi_near_pc(pc: int, center: int) -> int:
        candidates = [
            p for p in range(max(0, center - 18), min(127, center + 18) + 1)
            if p % 12 == pc
        ]
        return min(candidates, key=lambda p: abs(p - center))

    def _repair_fx_role(
        self,
        role: str,
        notes: list,
    ) -> list:
        repaired = []

        for note in notes:
            section = self.section_for_tick(note.start)

            # Maximum dramatic impacts are forbidden during resolution.
            if role == "braam" and section.name == "homecoming":
                self.corrections.append(
                    SafetyCorrection(
                        role,
                        note.start,
                        note.pitch,
                        None,
                        "BRAAM_FORBIDDEN_IN_RESOLUTION",
                        "Braam removed from homecoming/resolution.",
                    )
                )
                continue

            root = self.chord_root_pc(note.start)
            chord = self.chord_pcs(note.start)

            if role == "braam":
                # Root in low cinematic register.
                target = self._midi_near_pc(root, 43)
            else:
                # Prefer fifth/chord tone in upper register. Select the
                # highest stable chord member near C6.
                chord_candidates = []
                for pc in chord:
                    chord_candidates.append(
                        self._midi_near_pc(pc, 84)
                    )
                target = min(
                    chord_candidates,
                    key=lambda p: (
                        abs(p - 84),
                        -p,
                    ),
                )

            if target != note.pitch:
                self.corrections.append(
                    SafetyCorrection(
                        role,
                        note.start,
                        note.pitch,
                        target,
                        "FX_RETUNED_TO_HARMONY",
                        (
                            f"{section.name}: FX retuned to current "
                            f"harmonic context."
                        ),
                    )
                )

            repaired.append(
                type(note)(
                    note.start,
                    note.duration,
                    target,
                    note.velocity,
                    note.channel,
                )
            )

        return repaired

    # ------------------------------------------------------------------
    # Accent Collision Guard
    # ------------------------------------------------------------------

    def _apply_accent_collision_guard(
        self,
        score: dict[str, list],
    ) -> dict[str, list]:
        result = {
            role: list(notes)
            for role, notes in score.items()
        }

        # Composer accents are bar/beat aligned. A half-beat displacement
        # clears the perceptual attack cluster without changing the form.
        shift_ticks = PPQ // 2

        # Work from a flattened event list and resolve clusters iteratively.
        for _ in range(4):
            accents = []
            for role in self.ACCENT_ROLES:
                for idx, note in enumerate(result.get(role, [])):
                    accents.append((note.start, role, idx, note))

            accents.sort(key=lambda x: x[0])
            changed = False

            for i, (tick, role, idx, note) in enumerate(accents):
                cluster = [
                    item for item in accents
                    if abs(item[0] - tick) <= PPQ // 8
                ]
                distinct = {
                    item[1] for item in cluster
                }

                if len(distinct) <= 2:
                    continue

                ranked_roles = sorted(
                    distinct,
                    key=lambda r: self.ACCENT_PRIORITY[r],
                    reverse=True,
                )
                protected = set(ranked_roles[:2])

                if role in protected:
                    continue

                old = result[role][idx]
                new_start = old.start + shift_ticks
                new_velocity = max(
                    1,
                    int(round(old.velocity * 0.84)),
                )

                result[role][idx] = type(old)(
                    new_start,
                    old.duration,
                    old.pitch,
                    new_velocity,
                    old.channel,
                )

                self.corrections.append(
                    SafetyCorrection(
                        role,
                        old.start,
                        old.pitch,
                        old.pitch,
                        "ACCENT_COLLISION",
                        (
                            f"Accent cluster >2 roles: shifted by "
                            f"{shift_ticks} ticks and reduced velocity."
                        ),
                    )
                )
                changed = True
                break

            if not changed:
                break

        return result

    def accent_cluster_max(self, score: dict[str, list]) -> int:
        accents = []
        for role in self.ACCENT_ROLES:
            for note in score.get(role, []):
                accents.append((note.start, role))

        max_roles = 0
        for tick, _ in accents:
            roles = {
                role for t, role in accents
                if abs(t - tick) <= PPQ // 8
            }
            max_roles = max(max_roles, len(roles))

        return max_roles

    # ------------------------------------------------------------------
    # Full score safety pass
    # ------------------------------------------------------------------

    def apply(self, score: dict[str, list]):
        self.corrections = []
        safe = {
            role: list(notes)
            for role, notes in score.items()
        }

        for role in ("theme", "countermelody"):
            safe[role] = self._repair_melodic_role(
                role,
                safe.get(role, []),
            )

        for role in ("braam", "ping"):
            safe[role] = self._repair_fx_role(
                role,
                safe.get(role, []),
            )

        safe = self._apply_accent_collision_guard(safe)

        report = {
            "correction_count": len(self.corrections),
            "corrections": [
                asdict(c) for c in self.corrections
            ],
            "max_accent_roles_after_guard":
                self.accent_cluster_max(safe),
        }
        return safe, report

    # ------------------------------------------------------------------
    # Validation metrics
    # ------------------------------------------------------------------

    def count_out_of_key_melodic_notes(
        self,
        score: dict[str, list],
    ) -> int:
        scale = self.scale_pcs()
        total = 0
        for role in ("theme", "countermelody"):
            for note in score.get(role, []):
                if note.pitch % 12 not in scale:
                    total += 1
        return total

    def count_homecoming_minor_second_collisions(
        self,
        score: dict[str, list],
    ) -> int:
        total = 0
        for role in ("theme", "countermelody"):
            for note in score.get(role, []):
                section = self.section_for_tick(note.start)
                if section.name != "homecoming":
                    continue
                chord = self.chord_pcs(note.start)
                pc = note.pitch % 12
                if (
                    pc not in chord
                    and any(
                        self._pc_distance(pc, c) == 1
                        for c in chord
                    )
                ):
                    total += 1
        return total

    def fx_tonal_mismatches(
        self,
        score: dict[str, list],
    ) -> int:
        mismatches = 0
        for role in ("braam", "ping"):
            for note in score.get(role, []):
                if note.pitch % 12 not in self.chord_pcs(note.start):
                    mismatches += 1
        return mismatches

    # ------------------------------------------------------------------
    # Render-time Dynamic Impact Guard
    # ------------------------------------------------------------------

    @staticmethod
    def _rms(x: np.ndarray) -> float:
        if x.size == 0:
            return 0.0
        return float(
            np.sqrt(
                np.mean(
                    x.astype(np.float64) ** 2
                )
            )
        )

    @staticmethod
    def _db(value: float) -> float:
        return 20.0 * math.log10(max(value, 1e-12))

    def allowed_impact_delta_db(
        self,
        section_name: str,
        role: str,
    ) -> float:
        base = {
            "awakening": 4.0,
            "departure": 5.5,
            "ascent": 6.5,
            "breakthrough": 8.0,
            "homecoming": 4.0,
        }[section_name]

        if role == "ping":
            base = min(base, 4.5)

        return base

    def guarded_place_fx_event(
        self,
        *,
        reference_mix: np.ndarray,
        event_audio: np.ndarray,
        event_note,
        role: str,
        sample_rate: int,
        bpm: float,
    ) -> tuple[np.ndarray, ImpactDiagnostic]:
        seconds_per_tick = 60.0 / (bpm * PPQ)
        start_seconds = event_note.start * seconds_per_tick
        start = int(round(start_seconds * sample_rate))

        total = reference_mix.shape[1]
        out = np.zeros_like(reference_mix)

        if start >= total:
            diag = ImpactDiagnostic(
                role,
                event_note.start,
                start_seconds,
                self.section_for_tick(event_note.start).name,
                -120.0,
                -120.0,
                -120.0,
                0.0,
                -120.0,
                -120.0,
            )
            return out, diag

        usable = min(event_audio.shape[1], total - start)
        event = event_audio[:, :usable].copy()

        pre_n = int(round(0.75 * sample_rate))
        post_n = int(round(0.25 * sample_rate))

        pre = reference_mix[
            :,
            max(0, start - pre_n):start,
        ]
        post_ref = reference_mix[
            :,
            start:min(total, start + post_n),
        ]
        fx_head = event[
            :,
            :min(usable, post_n),
        ]

        context_rms = self._rms(pre)
        post_ref_rms = self._rms(post_ref)
        raw_fx_rms = self._rms(fx_head)

        # Use whichever orchestral context is stronger, with a conservative
        # floor so a transition out of near-silence does not mute the FX.
        floor_rms = 10.0 ** (-42.0 / 20.0)
        base_rms = max(
            context_rms,
            post_ref_rms,
            floor_rms,
        )

        section = self.section_for_tick(event_note.start)
        allowed_delta = self.allowed_impact_delta_db(
            section.name,
            role,
        )
        max_fx_rms = base_rms * (
            10.0 ** (allowed_delta / 20.0)
        )

        gain = 1.0
        if raw_fx_rms > max_fx_rms and raw_fx_rms > 1e-12:
            gain = max_fx_rms / raw_fx_rms

        # Velocity remains expressive but cannot defeat the guard.
        velocity_gain = float(
            np.clip(event_note.velocity / 100.0, 0.35, 1.15)
        )
        final_gain = gain * velocity_gain
        event *= final_gain

        out[:, start:start + usable] += event

        final_fx_rms = self._rms(
            event[:, :min(usable, post_n)]
        )

        diag = ImpactDiagnostic(
            role=role,
            start_tick=event_note.start,
            start_seconds=round(start_seconds, 6),
            section=section.name,
            context_rms_db=round(self._db(context_rms), 3),
            orchestral_post_rms_db=round(
                self._db(post_ref_rms),
                3,
            ),
            raw_fx_rms_db=round(self._db(raw_fx_rms), 3),
            allowed_delta_db=allowed_delta,
            applied_gain_db=round(
                20.0 * math.log10(
                    max(final_gain, 1e-12)
                ),
                3,
            ),
            final_fx_rms_db=round(
                self._db(final_fx_rms),
                3,
            ),
        )

        return out, diag


def shared_scoring_stage(
    mix: np.ndarray,
    sample_rate: int,
    wet: float = 0.09,
) -> np.ndarray:
    """
    Small deterministic shared ambience bus.

    This is deliberately subtle: VSCO/Salamander already contain acoustic
    information. The purpose is not to create a large artificial reverb, but
    to give orchestral and native-FX material one common tail.
    """
    x = np.asarray(mix, dtype=np.float32)
    out = x.copy()

    taps = (
        (0.031, 0.16, True),
        (0.047, 0.12, False),
        (0.073, 0.09, True),
        (0.109, 0.065, False),
        (0.157, 0.045, True),
    )

    room = np.zeros_like(x)

    for seconds, gain, cross in taps:
        delay = int(round(seconds * sample_rate))
        if delay <= 0 or delay >= x.shape[1]:
            continue

        src = x[::-1] if cross else x
        room[:, delay:] += src[:, :-delay] * gain

    # Gentle damping via one-pole smoothing on the room bus.
    alpha = 0.22
    damp = np.zeros_like(room)
    if room.shape[1] > 0:
        damp[:, 0] = room[:, 0]
        for i in range(1, room.shape[1]):
            damp[:, i] = (
                alpha * room[:, i]
                + (1.0 - alpha) * damp[:, i - 1]
            )

    out += damp * float(wet)
    return out.astype(np.float32)


def light_glue_compressor(
    mix: np.ndarray,
    threshold_db: float = -17.0,
    ratio: float = 1.45,
    attack_ms: float = 22.0,
    release_ms: float = 180.0,
    sample_rate: int = 48000,
) -> np.ndarray:
    """
    Gentle stereo-linked bus glue. Not a mastering maximizer.
    """
    x = np.asarray(mix, dtype=np.float32)
    detector = np.max(np.abs(x), axis=0)

    threshold = 10.0 ** (threshold_db / 20.0)
    attack = math.exp(
        -1.0 / max(1.0, attack_ms * 0.001 * sample_rate)
    )
    release = math.exp(
        -1.0 / max(1.0, release_ms * 0.001 * sample_rate)
    )

    env = 0.0
    gain = np.ones(detector.shape[0], dtype=np.float32)

    for i, sample in enumerate(detector):
        coeff = attack if sample > env else release
        env = coeff * env + (1.0 - coeff) * float(sample)

        if env <= threshold:
            g = 1.0
        else:
            env_db = 20.0 * math.log10(max(env, 1e-12))
            over = env_db - threshold_db
            reduced_over = over / ratio
            gain_db = reduced_over - over
            g = 10.0 ** (gain_db / 20.0)

        gain[i] = g

    return (x * gain[None, :]).astype(np.float32)
