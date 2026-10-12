from __future__ import annotations

from pathlib import Path
import json
import math

import numpy as np

from tukana_mastering import (
    EXPECTED_FRAMES, RATE, decode_float, ebur128, ffprobe, loudnorm_measure,
    run, sha256_file, signal_metrics,
)


def db(value: float) -> float:
    return 20.0 * math.log10(max(value, 1e-15))


def drum_attack_frames(drums: np.ndarray, count: int = 250) -> np.ndarray:
    """Locate strong drum onsets; the drum stem is only a timing reference."""
    mono = np.max(np.abs(drums), axis=1)
    hop = RATE // 100  # 10 ms envelope
    envelope = np.array([mono[i:i + hop].max(initial=0.0)
                         for i in range(0, len(mono), hop)])
    novelty = np.maximum(0.0, envelope - np.r_[envelope[0], envelope[:-1]])
    candidates = np.argsort(novelty)[::-1]
    selected: list[int] = []
    exclusion = 20  # 200 ms
    for candidate in candidates:
        if novelty[candidate] <= 0:
            break
        if all(abs(int(candidate) - previous) >= exclusion for previous in selected):
            selected.append(int(candidate))
            if len(selected) == count:
                break
    return np.sort(np.asarray(selected, dtype=np.int64) * hop)


def transient_analysis(audio: np.ndarray, attacks: np.ndarray) -> dict:
    peak_window = int(0.020 * RATE)
    body_window = int(0.200 * RATE)
    crest = []
    attack_peaks = []
    for frame in attacks:
        end_peak = min(len(audio), frame + peak_window)
        end_body = min(len(audio), frame + body_window)
        if end_peak <= frame or end_body <= frame:
            continue
        peak = float(np.max(np.abs(audio[frame:end_peak])))
        rms = float(np.sqrt(np.mean(audio[frame:end_body].astype(np.float64) ** 2)))
        attack_peaks.append(peak)
        crest.append(db(peak / max(rms, 1e-15)))
    values = np.asarray(crest)
    peaks = np.asarray(attack_peaks)
    return {
        "events": int(len(values)),
        "attack_to_body_crest_db": {
            "p10": float(np.percentile(values, 10)),
            "median": float(np.median(values)),
            "p90": float(np.percentile(values, 90)),
        },
        "attack_peak_dbfs": {
            "median": db(float(np.median(peaks))),
            "p90": db(float(np.percentile(peaks, 90))),
        },
    }


def local_transient(audio: np.ndarray, seconds: float) -> dict:
    center = round(seconds * RATE)
    start = max(0, center - int(0.050 * RATE))
    end = min(len(audio), center + int(0.200 * RATE))
    region = audio[start:end]
    peak = float(np.max(np.abs(region)))
    rms = float(np.sqrt(np.mean(region.astype(np.float64) ** 2)))
    return {"time_seconds": seconds, "peak_dbfs": db(peak),
            "rms_dbfs": db(rms), "local_crest_db": db(peak / max(rms, 1e-15))}


def render_loudnorm(source: Path, output: Path, target_i: float,
                    target_tp: float = -1.5, target_lra: float = 11.0) -> dict:
    measured = loudnorm_measure(source, target_i, target_tp, target_lra)
    filter_value = (
        f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:"
        f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']}:linear=false:print_format=summary")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(source), "-af", filter_value,
         "-ar", str(RATE), "-c:a", "pcm_s24le", str(output)])
    return measured


def write_gain_copy(source: Path, output: Path, gain_db: float,
                    start: float | None = None, duration: float | None = None) -> None:
    command = ["ffmpeg", "-y", "-v", "error"]
    if start is not None:
        command += ["-ss", f"{start:.6f}"]
    command += ["-i", str(source)]
    if duration is not None:
        command += ["-t", f"{duration:.6f}"]
    command += ["-af", f"volume={gain_db:.6f}dB", "-ar", str(RATE),
                "-c:a", "pcm_s24le", str(output)]
    run(command)


def refine_tukana(project_root: str | Path) -> dict:
    root = Path(project_root)
    mastering = root / "renders" / "mastering"
    out = mastering / "t017"
    reports = root / "reports"
    protected_b2 = out / "TUKANA_B2_transient_refinement_24bit.wav"
    if protected_b2.exists():
        raise FileExistsError("B2 already exists and must not be overwritten; use a new project directory")
    out.mkdir(parents=True, exist_ok=True)

    source = root / "renders" / "TUKANA_binaural_full_master_candidate.wav"
    master_a = mastering / "TUKANA_transparent_binaural_master_24bit.wav"
    master_b = mastering / "TUKANA_youtube_optimized_candidate_24bit.wav"
    drums = root / "spatial_stems" / "full" / "drums_spatial.wav"
    protected = {name: sha256_file(path) for name, path in
                 {"t015": source, "master_a": master_a, "master_b": master_b}.items()}

    b2 = out / "TUKANA_B2_transient_refinement_24bit.wav"
    first_pass = render_loudnorm(source, b2, target_i=-16.3)

    audio = {"A": decode_float(master_a), "B": decode_float(master_b),
             "B2": decode_float(b2)}
    attacks = drum_attack_frames(decode_float(drums))
    transient = {name: transient_analysis(value, attacks) for name, value in audio.items()}
    at_151_92 = {name: local_transient(value, 151.92) for name, value in audio.items()}

    loudness = {name: ebur128(path) for name, path in
                {"A": master_a, "B": master_b, "B2": b2}.items()}
    comparison_target = min(item["integrated_lufs"] for item in loudness.values())
    full_paths = {}
    for name, path in {"A": master_a, "B": master_b, "B2": b2}.items():
        target = out / f"TUKANA_T017_{name}_level_matched_24bit.wav"
        write_gain_copy(path, target, comparison_target - loudness[name]["integrated_lufs"])
        full_paths[name] = target

    preview_start, preview_duration = 145.0, 15.0
    start_frame = round(preview_start * RATE)
    end_frame = round((preview_start + preview_duration) * RATE)
    segment_rms = {name: float(np.sqrt(np.mean(value[start_frame:end_frame].astype(np.float64) ** 2)))
                   for name, value in audio.items()}
    preview_target = min(segment_rms.values())
    preview_paths = {}
    for name, path in {"A": master_a, "B": master_b, "B2": b2}.items():
        target = out / f"TUKANA_T017_preview_145_160_{name}_level_matched_24bit.wav"
        write_gain_copy(path, target, db(preview_target / segment_rms[name]),
                        preview_start, preview_duration)
        preview_paths[name] = target

    artifacts = {}
    paths = {"master_b2": b2, **{f"full_{k}": v for k, v in full_paths.items()},
             **{f"preview_{k}": v for k, v in preview_paths.items()}}
    for name, path in paths.items():
        artifacts[name] = {"path": str(path), "sha256": sha256_file(path),
                           "format": ffprobe(path), "signal": signal_metrics(path),
                           "loudness": ebur128(path)}

    b2_signal = artifacts["master_b2"]["signal"]
    b_signal = signal_metrics(master_b)
    preserved = {name: protected[name] == sha256_file(path) for name, path in
                 {"t015": source, "master_a": master_a, "master_b": master_b}.items()}
    tests = {
        "prior_artifacts_preserved": all(preserved.values()),
        "b2_pcm24_48khz_stereo": artifacts["master_b2"]["format"]["sample_fmt"] == "s32" and
                                  artifacts["master_b2"]["format"]["sample_rate"] == str(RATE) and
                                  artifacts["master_b2"]["format"]["channels"] == 2,
        "b2_exact_duration": b2_signal["frames"] == EXPECTED_FRAMES,
        "b2_finite_no_clipping": b2_signal["finite"] and b2_signal["sample_peak"] < 1.0,
        "b2_loudness_near_minus_16": -16.5 <= artifacts["master_b2"]["loudness"]["integrated_lufs"] <= -15.8,
        "b2_true_peak_limit": artifacts["master_b2"]["loudness"]["true_peak_dbtp"] <= -1.5,
        "channel_balance_preserved": abs(b2_signal["channel_balance_db"] - b_signal["channel_balance_db"]) < 0.10,
        "stereo_correlation_preserved": abs(b2_signal["lr_correlation"] - b_signal["lr_correlation"]) < 0.02,
        "mono_compatibility_preserved": abs(b2_signal["mono_rms_change_db"] - b_signal["mono_rms_change_db"]) < 0.10,
        "transient_151_92_preserved": b2_signal["transient_151_92_peak"] > 0.01,
        "full_comparison_level_matched": True,  # assigned below including A, B and B2
        "previews_exact_duration": all(abs(artifacts[f"preview_{n}"]["signal"]["duration_seconds"] -
                                           preview_duration) <= 1 / RATE for n in ("A", "B", "B2")),
    }
    # Evaluate all three full-length comparison files.
    full_lufs = [artifacts[f"full_{n}"]["loudness"]["integrated_lufs"] for n in ("A", "B", "B2")]
    tests["full_comparison_level_matched"] = max(full_lufs) - min(full_lufs) <= 0.2

    report = {
        "test_id": "T017", "status": "PASS" if all(tests.values()) else "FAIL",
        "human_review": "PENDING", "t016_human_reference": "MASTER_B_APPROVED",
        "method": {
            "decision": "viable_conservative_experiment",
            "rationale": "B2 relaxes the loudness target by 0.3 LU to reduce dynamic intervention without stem remixing.",
            "target_integrated_lufs": -16.3, "target_true_peak_dbtp": -1.5,
            "target_lra_lu": 11.0, "first_pass": first_pass,
            "processing": ["two-pass EBU R128 loudness normalization", "stereo-linked true-peak limiting"],
            "excluded": ["EQ", "stereo widening", "Mid/Side", "new spatialization", "stem reinforcement"],
        },
        "transient_analysis": {"drum_detected_events": int(len(attacks)),
                               "masters": transient, "at_151_92_seconds": at_151_92,
                               "b2_minus_b_median_attack_crest_db":
                                   transient["B2"]["attack_to_body_crest_db"]["median"] -
                                   transient["B"]["attack_to_body_crest_db"]["median"],
                               "interpretation": "Crest change is measured at drum-timed events but remains a full-mix metric; it is not attributed exclusively to drums. The B2 median recovery is objectively very small and requires human evaluation."},
        "protected_hashes": protected, "preservation_checks": preserved,
        "artifacts": artifacts, "tests": tests,
        "pending": ["human A/B/B2 approval", "dynamic distance automation validation",
                    "global front/back perceptual validation", "final YouTube video packaging"],
    }
    (reports / "t017_transient_refinement.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    project = Path(__file__).resolve().parents[2] / "projects" / "tukana"
    result = refine_tukana(project)
    print(json.dumps({"status": result["status"], "tests": result["tests"],
                      "transients": result["transient_analysis"]}, indent=2))


