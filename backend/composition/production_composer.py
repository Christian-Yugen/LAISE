from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import json
import math
import random
import struct
from typing import Iterable

from generation_request import GenerationRequest


PPQ = 480
BEATS_PER_BAR = 4
BAR = PPQ * BEATS_PER_BAR


NOTE_PC = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8,
    "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11,
}

MAJOR_SCALE = (0, 2, 4, 5, 7, 9, 11)
MINOR_SCALE = (0, 2, 3, 5, 7, 8, 10)


@dataclass(frozen=True)
class NoteEvent:
    start: int
    duration: int
    pitch: int
    velocity: int
    channel: int = 0


@dataclass(frozen=True)
class Section:
    name: str
    start_bar: int
    bars: int
    energy: float
    harmonic_function: str


@dataclass(frozen=True)
class CompositionPlan:
    title: str
    request_seed: int
    key: str
    mode: str
    bpm: float
    total_bars: int
    requested_duration_seconds: float
    nominal_duration_seconds: float
    motif_degrees: tuple[int, ...]
    motif_rhythm_beats: tuple[float, ...]
    sections: tuple[Section, ...]
    progression_by_section: dict[str, tuple[int, ...]]
    score_fingerprint: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["sections"] = [asdict(s) for s in self.sections]
        return data


def _clamp_midi(v: int) -> int:
    return max(0, min(127, int(v)))


def _vel(v: float) -> int:
    return max(1, min(127, int(round(v))))


def _root_midi(key: str, octave: int) -> int:
    return 12 * (octave + 1) + NOTE_PC[key]


def _scale_pitch(root: int, degree: int, scale: tuple[int, ...]) -> int:
    octave, index = divmod(degree, 7)
    return root + scale[index] + 12 * octave


def _triad(root_pc_midi: int, degree: int, scale: tuple[int, ...]) -> tuple[int, int, int]:
    d0 = degree % 7
    pitches = []
    for offset in (0, 2, 4):
        d = d0 + offset
        pitches.append(
            root_pc_midi
            + scale[d % 7]
            + 12 * (d // 7)
        )
    return tuple(pitches)


def _varlen(value: int) -> bytes:
    value = int(value)
    buffer = value & 0x7F
    out = bytearray([buffer])
    while True:
        value >>= 7
        if not value:
            break
        buffer = (value & 0x7F) | 0x80
        out.insert(0, buffer)
    return bytes(out)


def write_midi(
    path: Path,
    notes: Iterable[NoteEvent],
    bpm: float,
    program: int = 0,
    channel: int = 0,
) -> None:
    """
    Minimal deterministic Standard MIDI File writer (format 0).
    No external MIDI package required.
    """
    events: list[tuple[int, int, bytes]] = []

    tempo_us = int(round(60_000_000 / bpm))
    tempo = b"\xFF\x51\x03" + tempo_us.to_bytes(3, "big")
    events.append((0, 0, tempo))
    events.append((0, 1, bytes([0xC0 | channel, program & 0x7F])))

    last_tick = 0
    for n in notes:
        start = max(0, int(n.start))
        end = max(start + 1, start + int(n.duration))
        pitch = _clamp_midi(n.pitch)
        velocity = _vel(n.velocity)
        ch = int(n.channel if n.channel is not None else channel) & 0x0F

        # Note-off sort order before note-on at the same tick.
        events.append((start, 3, bytes([0x90 | ch, pitch, velocity])))
        events.append((end, 2, bytes([0x80 | ch, pitch, 0])))
        last_tick = max(last_tick, end)

    events.sort(key=lambda x: (x[0], x[1], x[2]))

    track = bytearray()
    cursor = 0
    for tick, _, payload in events:
        track += _varlen(tick - cursor)
        track += payload
        cursor = tick

    track += _varlen(max(1, last_tick + PPQ // 4 - cursor))
    track += b"\xFF\x2F\x00"

    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, PPQ)
    chunk = b"MTrk" + struct.pack(">I", len(track)) + bytes(track)
    path.write_bytes(header + chunk)


class ProductionComposer:
    """
    T011.2 — creates a genuinely NEW deterministic score from GenerationRequest.

    This module intentionally imports no MUSIC-004...MUSIC-010 score generator.
    The musical form, motif, harmony and orchestration are derived from the
    request + seed.
    """

    def __init__(self, request: GenerationRequest):
        request.validate()
        self.req = request
        self.rng = random.Random(request.seed)

        self.mode = self._choose_mode()
        self.scale = MAJOR_SCALE if self.mode == "major" else MINOR_SCALE
        self.key = request.key or self._choose_key()
        self.bpm = float(request.bpm or self._choose_bpm())

        seconds_per_bar = 60.0 / self.bpm * BEATS_PER_BAR
        self.total_bars = max(
            16,
            int(round(request.duration_seconds / seconds_per_bar)),
        )
        self.sections = self._build_sections(self.total_bars)
        self.motif_degrees, self.motif_rhythm = self._build_motif()
        self.progressions = self._build_progressions()

    def _choose_mode(self) -> str:
        if self.req.emotion in {"dark", "melancholic", "tense"}:
            return "minor"
        return "major"

    def _choose_key(self) -> str:
        if self.mode == "major":
            pool = ["C", "D", "Eb", "F", "G", "A"]
        else:
            pool = ["C", "D", "E", "F", "G", "A"]
        return self.rng.choice(pool)

    def _choose_bpm(self) -> float:
        ranges = {
            "hopeful": (76, 94),
            "heroic": (84, 108),
            "triumphant": (88, 112),
            "dark": (58, 76),
            "melancholic": (60, 82),
            "tense": (68, 92),
        }
        lo, hi = ranges[self.req.emotion]
        base = self.rng.randint(lo, hi)
        # Keep an even tempo to simplify phrase architecture.
        return float(base if base % 2 == 0 else base + 1)

    def _build_sections(self, total: int) -> tuple[Section, ...]:
        names = [
            ("awakening", 0.24, "stability"),
            ("departure", 0.46, "preparation"),
            ("ascent", 0.66, "expectation"),
            ("breakthrough", 1.00, "climax"),
            ("homecoming", 0.38, "resolution"),
        ]
        ratios = [0.15, 0.20, 0.20, 0.27, 0.18]

        bars = [max(2, int(round(total * r))) for r in ratios]
        delta = total - sum(bars)
        i = 0
        while delta != 0:
            j = i % len(bars)
            if delta > 0:
                bars[j] += 1
                delta -= 1
            elif bars[j] > 2:
                bars[j] -= 1
                delta += 1
            i += 1

        start = 0
        result = []
        intensity = self.req.intensity
        for (name, energy_scale, function), count in zip(names, bars):
            energy = min(1.0, max(0.08, energy_scale * (0.65 + 0.55 * intensity)))
            result.append(
                Section(
                    name=name,
                    start_bar=start,
                    bars=count,
                    energy=round(energy, 4),
                    harmonic_function=function,
                )
            )
            start += count

        return tuple(result)

    def _build_motif(self) -> tuple[tuple[int, ...], tuple[float, ...]]:
        # Seed-generated contour with a deliberate recognizable identity.
        if self.mode == "major":
            starts = [0, 2, 4]
            moves = [-2, -1, 1, 2, 3]
        else:
            starts = [0, 2, 4, 5]
            moves = [-2, -1, 1, 2]

        length = self.rng.choice([4, 5, 5, 6])
        degrees = [self.rng.choice(starts)]

        for _ in range(length - 1):
            nxt = degrees[-1] + self.rng.choice(moves)
            while nxt < 0:
                nxt += 7
            while nxt > 8:
                nxt -= 7
            degrees.append(nxt)

        # Make the final cell feel intentional rather than random.
        if self.req.emotion in {"hopeful", "heroic", "triumphant"}:
            degrees[-1] = self.rng.choice([4, 7])
        else:
            degrees[-1] = self.rng.choice([0, 2, 5])

        rhythm_pool = [
            (1.0, 1.0, 1.0, 1.0),
            (0.5, 0.5, 1.0, 2.0),
            (1.0, 0.5, 0.5, 2.0),
            (0.75, 0.75, 0.5, 2.0),
        ]
        base = list(self.rng.choice(rhythm_pool))
        while len(base) < length:
            base.insert(-1, 0.5)
        rhythm = tuple(base[:length])

        return tuple(degrees), rhythm

    def _build_progressions(self) -> dict[str, tuple[int, ...]]:
        if self.mode == "major":
            pools = {
                "awakening": [(0, 5, 3, 4), (0, 3, 5, 4), (0, 4, 5, 3)],
                "departure": [(5, 3, 0, 4), (0, 5, 1, 4), (3, 0, 1, 4)],
                "ascent": [(5, 3, 0, 4), (1, 5, 3, 4), (3, 4, 5, 4)],
                "breakthrough": [(0, 4, 5, 3), (0, 3, 4, 0), (5, 3, 0, 4)],
                "homecoming": [(3, 4, 0, 0), (5, 3, 0, 0), (1, 4, 0, 0)],
            }
        else:
            pools = {
                "awakening": [(0, 5, 2, 6), (0, 3, 5, 4), (0, 6, 5, 6)],
                "departure": [(5, 2, 0, 6), (0, 5, 3, 6), (2, 5, 0, 6)],
                "ascent": [(5, 3, 0, 6), (2, 5, 6, 6), (3, 6, 5, 6)],
                "breakthrough": [(0, 5, 6, 0), (0, 3, 6, 0), (5, 3, 0, 6)],
                "homecoming": [(5, 6, 0, 0), (3, 6, 0, 0), (2, 6, 0, 0)],
            }

        return {
            section.name: tuple(self.rng.choice(pools[section.name]))
            for section in self.sections
        }

    def plan(self) -> CompositionPlan:
        seconds_per_bar = 60.0 / self.bpm * BEATS_PER_BAR
        plan = CompositionPlan(
            title=self.req.title,
            request_seed=self.req.seed,
            key=self.key,
            mode=self.mode,
            bpm=self.bpm,
            total_bars=self.total_bars,
            requested_duration_seconds=self.req.duration_seconds,
            nominal_duration_seconds=round(
                self.total_bars * seconds_per_bar,
                3,
            ),
            motif_degrees=self.motif_degrees,
            motif_rhythm_beats=self.motif_rhythm,
            sections=self.sections,
            progression_by_section=self.progressions,
        )
        return plan

    def _section_for_bar(self, bar: int) -> Section:
        for section in self.sections:
            if section.start_bar <= bar < section.start_bar + section.bars:
                return section
        return self.sections[-1]

    def _degree_for_bar(self, bar: int) -> int:
        section = self._section_for_bar(bar)
        local = bar - section.start_bar
        prog = self.progressions[section.name]
        return prog[local % len(prog)]

    def _humanize(self, tick: int, amount: int = 12) -> int:
        if amount <= 0:
            return tick
        return max(0, tick + self.rng.randint(-amount, amount))

    def _melody_pitch(
        self,
        degree: int,
        octave: int,
        transpose_degree: int = 0,
    ) -> int:
        root = _root_midi(self.key, octave)
        return _scale_pitch(
            root,
            degree + transpose_degree,
            self.scale,
        )

    def _generate_piano(self) -> list[NoteEvent]:
        notes = []
        root = _root_midi(self.key, 3)

        for bar in range(self.total_bars):
            section = self._section_for_bar(bar)
            degree = self._degree_for_bar(bar)
            chord = _triad(root, degree, self.scale)
            start = bar * BAR

            if section.name == "awakening":
                pattern = [0, 1, 2, 1]
                step = PPQ
            else:
                pattern = [0, 1, 2, 1, 0, 1, 2, 1]
                step = PPQ // 2

            for i, ci in enumerate(pattern):
                pitch = chord[ci] + (12 if i >= len(pattern) // 2 else 0)
                velocity = 42 + section.energy * 34 + self.rng.randint(-4, 4)
                notes.append(
                    NoteEvent(
                        self._humanize(start + i * step, 8),
                        int(step * 0.88),
                        pitch,
                        _vel(velocity),
                    )
                )

        return notes

    def _generate_strings(self) -> list[NoteEvent]:
        notes = []
        root = _root_midi(self.key, 3)

        for bar in range(self.total_bars):
            section = self._section_for_bar(bar)
            degree = self._degree_for_bar(bar)
            chord = _triad(root, degree, self.scale)
            start = bar * BAR

            for pitch in chord:
                notes.append(
                    NoteEvent(
                        start,
                        BAR + PPQ // 8,
                        pitch + 12,
                        _vel(38 + 38 * section.energy),
                    )
                )
        return notes

    def _generate_bass(self) -> list[NoteEvent]:
        notes = []
        root = _root_midi(self.key, 2)

        for bar in range(self.total_bars):
            section = self._section_for_bar(bar)
            degree = self._degree_for_bar(bar)
            pitch = _scale_pitch(root, degree, self.scale)
            start = bar * BAR

            notes.append(
                NoteEvent(
                    start,
                    BAR,
                    pitch,
                    _vel(44 + 35 * section.energy),
                )
            )

            if section.energy > 0.55:
                fifth = pitch + 7
                notes.append(
                    NoteEvent(
                        start + 2 * PPQ,
                        2 * PPQ,
                        fifth,
                        _vel(38 + 27 * section.energy),
                    )
                )
        return notes

    def _motif_events_for_bar(
        self,
        bar: int,
        octave: int,
        velocity: int,
        transform: str,
    ) -> list[NoteEvent]:
        degrees = list(self.motif_degrees)
        rhythms = list(self.motif_rhythm)

        if transform == "reverse":
            degrees.reverse()
        elif transform == "lift":
            degrees = [d + (1 if i % 2 else 0) for i, d in enumerate(degrees)]
        elif transform == "answer":
            degrees[-1] = 0 if self.mode == "major" else 2

        total_beats = sum(rhythms)
        scale_factor = 4.0 / total_beats if total_beats > 0 else 1.0

        tick = bar * BAR
        out = []
        for i, (degree, beat_len) in enumerate(zip(degrees, rhythms)):
            dur = max(PPQ // 4, int(PPQ * beat_len * scale_factor))
            pitch = self._melody_pitch(degree, octave)
            out.append(
                NoteEvent(
                    self._humanize(tick, 10),
                    int(dur * 0.92),
                    pitch,
                    _vel(velocity + self.rng.randint(-5, 5)),
                )
            )
            tick += dur
        return out

    def _generate_theme(self) -> list[NoteEvent]:
        notes = []

        for section in self.sections:
            if section.name == "awakening":
                start_offset = max(1, section.bars // 2)
            else:
                start_offset = 0

            for local in range(start_offset, section.bars, 2):
                bar = section.start_bar + local
                if section.name == "departure":
                    transform = "statement"
                elif section.name == "ascent":
                    transform = "lift" if (local // 2) % 2 == 0 else "answer"
                elif section.name == "breakthrough":
                    transform = "lift"
                elif section.name == "homecoming":
                    transform = "answer"
                else:
                    transform = "statement"

                vel = _vel(48 + section.energy * 42)
                notes.extend(
                    self._motif_events_for_bar(
                        bar,
                        octave=4,
                        velocity=vel,
                        transform=transform,
                    )
                )
        return notes

    def _generate_ostinato(self) -> list[NoteEvent]:
        notes = []
        root = _root_midi(self.key, 4)

        for bar in range(self.total_bars):
            section = self._section_for_bar(bar)
            if section.name not in {"ascent", "breakthrough"}:
                continue

            degree = self._degree_for_bar(bar)
            chord = _triad(root, degree, self.scale)
            pattern = [0, 1, 2, 1, 0, 2, 1, 2]
            step = PPQ // 2

            for i, ci in enumerate(pattern):
                notes.append(
                    NoteEvent(
                        self._humanize(bar * BAR + i * step, 6),
                        int(step * 0.68),
                        chord[ci],
                        _vel(44 + section.energy * 38 + self.rng.randint(-4, 4)),
                    )
                )
        return notes

    def _generate_brass(self) -> tuple[list[NoteEvent], list[NoteEvent]]:
        sustain = []
        attacks = []
        root = _root_midi(self.key, 3)

        for bar in range(self.total_bars):
            section = self._section_for_bar(bar)
            if section.name not in {"ascent", "breakthrough"}:
                continue

            degree = self._degree_for_bar(bar)
            chord = _triad(root, degree, self.scale)
            start = bar * BAR

            for pitch in chord[:2]:
                sustain.append(
                    NoteEvent(
                        start,
                        BAR,
                        pitch + 5,
                        _vel(48 + section.energy * 42),
                    )
                )

            if section.name == "breakthrough" and (bar - section.start_bar) % 2 == 0:
                for pitch in chord[:2]:
                    attacks.append(
                        NoteEvent(
                            start,
                            PPQ // 2,
                            pitch + 5,
                            _vel(70 + section.energy * 35),
                        )
                    )

        return sustain, attacks

    def _generate_countermelody(self) -> list[NoteEvent]:
        notes = []
        for section in self.sections:
            if section.name not in {"breakthrough", "homecoming"}:
                continue

            for local in range(1, section.bars, 2):
                bar = section.start_bar + local
                degree = self.motif_degrees[(local // 2) % len(self.motif_degrees)]
                pitch = self._melody_pitch(degree + 2, 5)
                notes.append(
                    NoteEvent(
                        bar * BAR,
                        2 * PPQ,
                        pitch,
                        _vel(50 + section.energy * 35),
                    )
                )
                notes.append(
                    NoteEvent(
                        bar * BAR + 2 * PPQ,
                        2 * PPQ,
                        pitch - 2,
                        _vel(46 + section.energy * 30),
                    )
                )
        return notes

    def _generate_percussion(self) -> dict[str, list[NoteEvent]]:
        low: list[NoteEvent] = []
        snare: list[NoteEvent] = []
        cymbal: list[NoteEvent] = []

        for bar in range(self.total_bars):
            section = self._section_for_bar(bar)
            start = bar * BAR

            if section.name in {"departure", "ascent", "breakthrough"}:
                low.append(
                    NoteEvent(
                        start,
                        PPQ // 2,
                        60,
                        _vel(55 + section.energy * 45),
                    )
                )

            if section.name in {"ascent", "breakthrough"}:
                snare.append(
                    NoteEvent(
                        start + 2 * PPQ,
                        PPQ // 3,
                        60,
                        _vel(45 + section.energy * 42),
                    )
                )

            if (
                bar == section.start_bar
                and section.name in {"ascent", "breakthrough", "homecoming"}
            ):
                cymbal.append(
                    NoteEvent(
                        start,
                        PPQ,
                        60,
                        _vel(62 + section.energy * 45),
                    )
                )

        return {
            "percussion_low": low,
            "percussion_snare": snare,
            "percussion_cymbal": cymbal,
        }

    def _generate_fx_triggers(self) -> dict[str, list[NoteEvent]]:
        braam = []
        ping = []

        breakthrough = next(s for s in self.sections if s.name == "breakthrough")
        homecoming = next(s for s in self.sections if s.name == "homecoming")

        braam.append(
            NoteEvent(
                breakthrough.start_bar * BAR,
                PPQ,
                48,
                _vel(72 + self.req.intensity * 38),
            )
        )

        if breakthrough.bars >= 5:
            braam.append(
                NoteEvent(
                    (breakthrough.start_bar + breakthrough.bars // 2) * BAR,
                    PPQ,
                    48,
                    _vel(66 + self.req.intensity * 32),
                )
            )

        ping.append(
            NoteEvent(
                homecoming.start_bar * BAR,
                PPQ // 2,
                84,
                78,
            )
        )

        return {"braam": braam, "ping": ping}

    def compose(self) -> tuple[CompositionPlan, dict[str, list[NoteEvent]]]:
        brass, brass_attack = self._generate_brass()
        percussion = self._generate_percussion()
        fx = self._generate_fx_triggers()

        score = {
            "piano": self._generate_piano(),
            "theme": self._generate_theme(),
            "strings": self._generate_strings(),
            "bass": self._generate_bass(),
            "ostinato": self._generate_ostinato(),
            "brass": brass,
            "countermelody": self._generate_countermelody(),
            "brass_attack": brass_attack,
            **percussion,
            **fx,
        }

        fingerprint = score_fingerprint(score)
        base_plan = self.plan()
        plan = CompositionPlan(
            **{
                **base_plan.to_dict(),
                "sections": base_plan.sections,
                "progression_by_section": base_plan.progression_by_section,
                "motif_degrees": base_plan.motif_degrees,
                "motif_rhythm_beats": base_plan.motif_rhythm_beats,
                "score_fingerprint": fingerprint,
            }
        )

        return plan, score


def score_fingerprint(score: dict[str, list[NoteEvent]]) -> str:
    serial = {
        role: [
            [n.start, n.duration, n.pitch, n.velocity, n.channel]
            for n in notes
        ]
        for role, notes in sorted(score.items())
    }
    raw = json.dumps(
        serial,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def score_note_count(score: dict[str, list[NoteEvent]]) -> int:
    return sum(len(v) for v in score.values())
