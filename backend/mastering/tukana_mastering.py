from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import math
import re
import subprocess
import wave

import numpy as np


RATE = 48_000
EXPECTED_FRAMES = 12_844_801


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True)


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ffprobe(path: Path) -> dict:
    result = run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                  "-show_entries", "stream=codec_name,sample_fmt,sample_rate,channels,duration",
                  "-of", "json", str(path)])
    return json.loads(result.stdout)["streams"][0]


def ebur128(path: Path) -> dict:
    process = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-loglevel", "verbose", "-i", str(path), "-filter_complex",
         "ebur128=peak=true:framelog=verbose", "-f", "null", "-"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    text = process.stderr
    integrated = re.findall(r"I:\s*(-?\d+(?:\.\d+)?) LUFS", text)
    lra = re.findall(r"LRA:\s*(\d+(?:\.\d+)?) LU", text)
    peak = re.findall(r"Peak:\s*(-?\d+(?:\.\d+)?) dBFS", text)
    momentary = [float(v) for v in re.findall(r"M:\s*(-?\d+(?:\.\d+)?)", text)
                 if float(v) > -70.0]
    short_term = [float(v) for v in re.findall(r"S:\s*(-?\d+(?:\.\d+)?)", text)
                  if float(v) > -70.0]
    return {
        "method": "FFmpeg ebur128 peak=true",
        "integrated_lufs": float(integrated[-1]) if integrated else None,
        "loudness_range_lu": float(lra[-1]) if lra else None,
        "true_peak_dbtp": float(peak[-1]) if peak else None,
        "momentary_lufs": _distribution(momentary),
        "short_term_lufs": _distribution(short_term),
    }


def _distribution(values: list[float]) -> dict:
    if not values:
        return {"minimum": None, "median": None, "maximum": None}
    array = np.asarray(values)
    return {"minimum": float(array.min()), "median": float(np.median(array)),
            "maximum": float(array.max())}


def decode_float(path: Path) -> np.ndarray:
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-acodec",
         "pcm_f32le", "-ac", "2", "-ar", str(RATE), "-"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return np.frombuffer(result.stdout, dtype="<f4").reshape(-1, 2)


def signal_metrics(path: Path) -> dict:
    audio = decode_float(path).astype(np.float64)
    left, right = audio[:, 0], audio[:, 1]
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio * audio)))
    channel_rms = np.sqrt(np.mean(audio * audio, axis=0))
    correlation = float(np.corrcoef(left, right)[0, 1])
    mono = (left + right) * 0.5
    mono_rms = float(np.sqrt(np.mean(mono * mono)))
    crest = 20 * math.log10(max(peak, 1e-15) / max(rms, 1e-15))
    max_delta = float(np.max(np.abs(np.diff(audio, axis=0))))
    center = round(151.92 * RATE)
    transient = audio[max(0, center - RATE // 20):center + RATE // 20]
    transient_peak = float(np.max(np.abs(transient))) if transient.size else 0.0
    bands = [(20, 60), (60, 250), (250, 2000), (2000, 6000), (6000, 20000)]
    band_energy = np.zeros(len(bands), dtype=np.float64)
    total_energy = 0.0
    window_size = 8192
    window = np.hanning(window_size)
    for start in range(0, len(mono) - window_size + 1, window_size):
        spectrum = np.abs(np.fft.rfft(mono[start:start + window_size] * window)) ** 2
        frequencies = np.fft.rfftfreq(window_size, 1 / RATE)
        total_energy += float(spectrum.sum())
        for index, (low, high) in enumerate(bands):
            band_energy[index] += float(spectrum[(frequencies >= low) & (frequencies < high)].sum())
    spectral = {f"{low}-{high}_hz_db": 10 * math.log10(max(value, 1e-30) /
                                                        max(total_energy, 1e-30))
                for (low, high), value in zip(bands, band_energy)}
    return {
        "frames": int(len(audio)), "duration_seconds": len(audio) / RATE,
        "finite": bool(np.isfinite(audio).all()), "sample_peak": peak,
        "sample_peak_dbfs": 20 * math.log10(max(peak, 1e-15)),
        "rms_dbfs": 20 * math.log10(max(rms, 1e-15)), "crest_factor_db": crest,
        "left_rms_dbfs": 20 * math.log10(max(float(channel_rms[0]), 1e-15)),
        "right_rms_dbfs": 20 * math.log10(max(float(channel_rms[1]), 1e-15)),
        "channel_balance_db": 20 * math.log10(max(float(channel_rms[0]), 1e-15) /
                                               max(float(channel_rms[1]), 1e-15)),
        "lr_correlation": correlation,
        "mono_rms_change_db": 20 * math.log10(max(mono_rms, 1e-15) / max(rms, 1e-15)),
        "max_adjacent_sample_delta": max_delta,
        "transient_151_92_peak": transient_peak,
        "spectral_distribution": spectral,
    }


def loudnorm_measure(path: Path, target_i: float, target_tp: float, target_lra: float) -> dict:
    process = run(["ffmpeg", "-hide_banner", "-i", str(path), "-af",
                   f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:print_format=json",
                   "-f", "null", "-"])
    match = re.search(r"\{\s*\"input_i\".*?\}", process.stderr, re.S)
    if not match:
        raise RuntimeError("FFmpeg loudnorm did not return measurement JSON")
    return json.loads(match.group(0))


def master_tukana(project_root: str | Path) -> dict:
    root = Path(project_root)
    source = root / "renders" / "TUKANA_binaural_full_master_candidate.wav"
    renders = root / "renders" / "mastering"
    reports = root / "reports"
    renders.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    source_hash_before = sha256_file(source)

    transparent = renders / "TUKANA_transparent_binaural_master_24bit.wav"
    youtube = renders / "TUKANA_youtube_optimized_candidate_24bit.wav"
    ab_a = renders / "TUKANA_AB_A_transparent_level_matched_24bit.wav"
    ab_b = renders / "TUKANA_AB_B_youtube_level_matched_24bit.wav"
    aac = renders / "TUKANA_youtube_candidate_aac_256k.m4a"
    aac_decode = renders / "TUKANA_youtube_candidate_aac_roundtrip_24bit.wav"

    # A: one linked gain for both channels. Source TP -3 dBTP leaves room for +1.4 dB.
    run(["ffmpeg", "-y", "-v", "error", "-i", str(source), "-af", "volume=1.4dB",
         "-ar", str(RATE), "-c:a", "pcm_s24le", str(transparent)])

    # B: EBU R128 two-pass normalization. No channel-independent or spatial processing.
    target_i, target_tp, target_lra = -16.0, -1.5, 11.0
    measured = loudnorm_measure(source, target_i, target_tp, target_lra)
    loudnorm = (f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:"
                f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
                f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
                f"offset={measured['target_offset']}:linear=false:print_format=summary")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(source), "-af", loudnorm,
         "-ar", str(RATE), "-c:a", "pcm_s24le", str(youtube)])

    a_ebu, b_ebu = ebur128(transparent), ebur128(youtube)
    comparison_target = min(a_ebu["integrated_lufs"], b_ebu["integrated_lufs"])
    for input_path, output_path, metrics in ((transparent, ab_a, a_ebu), (youtube, ab_b, b_ebu)):
        gain = comparison_target - metrics["integrated_lufs"]
        run(["ffmpeg", "-y", "-v", "error", "-i", str(input_path), "-af",
             f"volume={gain:.3f}dB", "-ar", str(RATE), "-c:a", "pcm_s24le", str(output_path)])

    run(["ffmpeg", "-y", "-v", "error", "-i", str(youtube), "-c:a", "aac", "-b:a",
         "256k", str(aac)])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(aac), "-ar", str(RATE),
         "-c:a", "pcm_s24le", str(aac_decode)])

    artifacts = {}
    for name, path in {"source": source, "transparent": transparent, "youtube": youtube,
                       "ab_a": ab_a, "ab_b": ab_b, "aac": aac,
                       "aac_roundtrip": aac_decode}.items():
        artifacts[name] = {"path": str(path), "sha256": sha256_file(path),
                           "format": ffprobe(path), "signal": signal_metrics(path),
                           "loudness": ebur128(path)}

    source_signal = artifacts["source"]["signal"]
    tests = {
        "source_unchanged": source_hash_before == sha256_file(source),
        "pcm_masters_24bit_48khz_stereo": all(
            artifacts[name]["format"]["sample_fmt"] == "s32" and
            artifacts[name]["format"]["sample_rate"] == str(RATE) and
            artifacts[name]["format"]["channels"] == 2
            for name in ("transparent", "youtube", "ab_a", "ab_b")),
        "duration_preserved": all(artifacts[name]["signal"]["frames"] == EXPECTED_FRAMES
                                  for name in ("transparent", "youtube", "ab_a", "ab_b")),
        "finite_and_no_sample_clipping": all(
            artifacts[name]["signal"]["finite"] and artifacts[name]["signal"]["sample_peak"] < 1.0
            for name in artifacts),
        "true_peak_conservative": all(artifacts[name]["loudness"]["true_peak_dbtp"] <= -1.0
                                      for name in ("transparent", "youtube", "aac_roundtrip")),
        "channel_balance_preserved": all(
            abs(artifacts[name]["signal"]["channel_balance_db"] - source_signal["channel_balance_db"]) < 0.15
            for name in ("transparent", "youtube")),
        "stereo_correlation_preserved": all(
            abs(artifacts[name]["signal"]["lr_correlation"] - source_signal["lr_correlation"]) < 0.03
            for name in ("transparent", "youtube")),
        "mono_compatibility_preserved": all(
            abs(artifacts[name]["signal"]["mono_rms_change_db"] - source_signal["mono_rms_change_db"]) < 0.15
            for name in ("transparent", "youtube")),
        "ab_loudness_matched": abs(artifacts["ab_a"]["loudness"]["integrated_lufs"] -
                                   artifacts["ab_b"]["loudness"]["integrated_lufs"]) <= 0.2,
        "transient_151_92_present": all(artifacts[name]["signal"]["transient_151_92_peak"] > 0.01
                                        for name in ("transparent", "youtube", "aac_roundtrip")),
        "lossy_encode_no_clipping": artifacts["aac_roundtrip"]["signal"]["sample_peak"] < 1.0 and
                                    artifacts["aac_roundtrip"]["loudness"]["true_peak_dbtp"] <= -1.0,
    }
    report = {
        "test_id": "T016", "phase": "F", "status": "PASS" if all(tests.values()) else "FAIL",
        "human_review": "PENDING", "t015_human_spatial_approval": "PASS",
        "source_integrity": {"sha256_before": source_hash_before,
                             "sha256_after": sha256_file(source)},
        "mastering_manifest": {
            "transparent": {"processing": ["stereo-linked gain +1.4 dB", "PCM24 quantization"],
                            "excluded": ["EQ", "compression", "widening", "Mid/Side", "limiting"]},
            "youtube": {"processing": ["EBU R128 two-pass loudnorm", "true-peak limiting"],
                        "targets": {"integrated_lufs": target_i, "true_peak_dbtp": target_tp,
                                    "loudness_range_lu": target_lra}, "first_pass": measured,
                        "excluded": ["EQ", "widening", "Mid/Side", "new spatialization"]},
            "justification": "No documented spectral defect required EQ. Linked processing preserves binaural inter-channel cues.",
            "comparison_target_lufs": comparison_target,
            "lossy_test": "AAC-LC 256 kb/s encode and PCM24 round-trip analysis",
        },
        "artifacts": artifacts, "tests": tests,
        "pending": ["human A/B mastering approval", "dynamic distance automation validation",
                    "global front/back perceptual validation", "final YouTube video packaging"],
    }
    report_path = reports / "t016_mastering_validation.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2] / "projects" / "tukana"
    result = master_tukana(root)
    print(json.dumps({"status": result["status"], "tests": result["tests"]}, indent=2))


