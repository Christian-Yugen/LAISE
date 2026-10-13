from __future__ import annotations

from pathlib import Path
import json
import math

import numpy as np

from stem_importer import TARGET_RATE, iter_blocks


def _rms_envelope(path: str | Path, hop_frames: int) -> np.ndarray:
    values = []
    for block in iter_blocks(path, hop_frames):
        mono = np.mean(block, axis=1, dtype=np.float32)
        values.append(float(np.sqrt(np.mean(mono.astype(np.float64) ** 2))))
    return np.asarray(values, dtype=np.float64)


def _onset_envelope(path: str | Path, hop_frames: int = 1024) -> np.ndarray:
    energy = _rms_envelope(path, hop_frames)
    log_energy = np.log1p(1000.0 * energy)
    onset = np.maximum(np.diff(log_energy, prepend=log_energy[0]), 0.0)
    if len(onset) >= 3:
        onset = np.convolve(onset, np.array([0.2, 0.6, 0.2]), mode="same")
    return onset


def estimate_bpm(paths: list[str | Path], sample_rate: int = TARGET_RATE,
                 hop_frames: int = 1024, minimum: float = 70.0,
                 maximum: float = 170.0) -> dict:
    envelopes = [_onset_envelope(path, hop_frames) for path in paths]
    size = min(map(len, envelopes))
    onset = np.mean([env[:size] for env in envelopes], axis=0)
    onset -= np.mean(onset)
    frame_rate = sample_rate / hop_frames
    minimum_lag = max(1, math.floor(frame_rate * 60.0 / maximum))
    maximum_lag = math.ceil(frame_rate * 60.0 / minimum)
    scores = []
    for lag in range(minimum_lag, maximum_lag + 1):
        left, right = onset[:-lag], onset[lag:]
        denominator = math.sqrt(float(np.dot(left, left) * np.dot(right, right)))
        scores.append(float(np.dot(left, right) / denominator) if denominator else 0.0)
    best_index = int(np.argmax(scores))
    lag = minimum_lag + best_index
    bpm = 60.0 * frame_rate / lag
    period = max(1, round(frame_rate * 60.0 / bpm))
    phase_scores = [float(np.sum(np.maximum(onset[phase::period], 0.0))) for phase in range(period)]
    phase = int(np.argmax(phase_scores))
    confidence = max(0.0, min(1.0, (scores[best_index] - float(np.median(scores))) / 0.35))
    return {
        "bpm": bpm, "confidence": confidence, "method": "rhythmic-stem onset autocorrelation",
        "reference_stems": [str(Path(path)) for path in paths],
        "hop_frames": hop_frames, "beat_period_seconds": 60.0 / bpm,
        "first_beat_seconds": phase * hop_frames / sample_rate,
    }


def _transition_times(paths: list[str | Path], duration: float,
                      hop_frames: int = 4800) -> tuple[list[dict], np.ndarray]:
    envelopes = [_rms_envelope(path, hop_frames) for path in paths]
    size = min(map(len, envelopes))
    matrix = np.vstack([env[:size] for env in envelopes])
    normalized = matrix / np.maximum(np.max(matrix, axis=1, keepdims=True), 1e-12)
    aggregate = np.mean(normalized, axis=0)
    novelty = np.abs(np.diff(aggregate, prepend=aggregate[0]))
    novelty = np.convolve(novelty, np.ones(9) / 9.0, mode="same")
    threshold = float(np.quantile(novelty, 0.88))
    candidates = np.flatnonzero(novelty >= threshold)
    selected = []
    minimum_gap = round(4.0 * TARGET_RATE / hop_frames)
    for index in sorted(candidates, key=lambda i: novelty[i], reverse=True):
        if all(abs(int(index) - previous) >= minimum_gap for previous in selected):
            selected.append(int(index))
        if len(selected) >= max(3, round(duration / 30)):
            break
    selected.sort()
    maximum = max(float(np.max(novelty)), 1e-12)
    return ([{
        "time_seconds": index * hop_frames / TARGET_RATE,
        "confidence": float(novelty[index] / maximum),
        "reason": "ensemble energy/texture change",
    } for index in selected], aggregate)


def build_musical_map(import_manifest: dict, output_path: str | Path) -> dict:
    stems = import_manifest["stems"]
    duration = float(import_manifest["timeline_duration_seconds"])
    bpm = estimate_bpm([stems["drums"]["path"], stems["percussion"]["path"]])
    beat_period = bpm["beat_period_seconds"]
    beat_times = []
    time = bpm["first_beat_seconds"]
    while time <= duration:
        beat_times.append(time)
        time += beat_period
    bar_times = beat_times[::4]
    transitions, aggregate = _transition_times([record["path"] for record in stems.values()], duration)

    boundaries = [0.0] + [item["time_seconds"] for item in transitions] + [duration]
    boundaries = sorted(set(round(value, 6) for value in boundaries))
    sections = []
    for index, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
        start_frame = min(len(aggregate), round(start * 10))
        end_frame = min(len(aggregate), max(start_frame + 1, round(end * 10)))
        energy = float(np.mean(aggregate[start_frame:end_frame])) if end_frame > start_frame else 0.0
        if index == 0:
            label = "introduction"
        elif index == len(boundaries) - 2:
            label = "outro"
        elif energy >= float(np.quantile(aggregate, 0.75)):
            label = "climax" if start > duration * 0.55 else "chorus"
        else:
            label = "section_candidate"
        sections.append({"section_id": f"section_{index + 1:02d}", "label": label,
                         "start_seconds": start, "end_seconds": end,
                         "energy": energy, "confidence": 0.55,
                         "human_review_required": True})

    stem_events = {}
    for role, record in stems.items():
        regions = record["metrics"]["active_regions"]
        stem_events[role] = {
            "first_entry_seconds": regions[0]["start_seconds"] if regions else None,
            "last_activity_seconds": regions[-1]["end_seconds"] if regions else None,
            "active_regions": regions,
            "confidence": 0.9 if regions else 0.0,
            "source": "streaming RMS activity detector",
        }

    musical_map = {
        "schema": "LAISE Musical Map v1.0", "project": "tukana",
        "duration_seconds": duration, "bpm": bpm,
        "meter": {"numerator": 4, "denominator": 4, "confidence": 0.5,
                  "status": "INFERRED_PENDING_HUMAN_REVIEW"},
        "beat_grid_seconds": beat_times, "bar_grid_seconds": bar_times,
        "transitions": transitions, "sections": sections, "stem_events": stem_events,
        "manual_edits": [],
        "quality": {"objective_status": "PASS", "structural_labels": "PENDING_HUMAN_REVIEW"},
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(musical_map, indent=2, ensure_ascii=False), encoding="utf-8")
    return musical_map


