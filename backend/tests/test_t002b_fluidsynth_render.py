"""
LAISE — T002-B
FluidSynth MIDI -> Dry WAV Validation

Purpose
-------
Validate the synthesis bridge:

    Procedural MIDI
        ->
    FluidSynth
        ->
    Approved-for-test SoundFont
        ->
    Dry stereo WAV

This test deliberately does NOT use:
- dearVR PRO 2
- Pedalboard
- spatial processing
- mastering
- FFmpeg

The objective is to isolate and validate the synthesis layer.

Expected input from T002-A:
    evidence/T002/T002-A/t002a_procedural_midi.mid

SoundFont:
    assets/soundfonts/GeneralUser GS v1.471.sf2

FluidSynth:
    tools/fluidsynth/bin/fluidsynth.exe

Output:
    evidence/T002/T002-B/t002b_fluidsynth_dry.wav
    evidence/T002/T002-B/t002b_fluidsynth_render_results.json
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import shutil
import struct
import subprocess
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path


# ============================================================
# LAISE PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

FLUIDSYNTH_EXE = (
    PROJECT_ROOT
    / "tools"
    / "fluidsynth"
    / "bin"
    / "fluidsynth.exe"
)

SOUNDFONT = (
    PROJECT_ROOT
    / "assets"
    / "soundfonts"
    / "GeneralUser GS v1.471.sf2"
)

INPUT_MIDI = (
    PROJECT_ROOT
    / "evidence"
    / "T002"
    / "T002-A"
    / "t002a_procedural_midi.mid"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "evidence"
    / "T002"
    / "T002-B"
)

OUTPUT_WAV = OUTPUT_DIR / "t002b_fluidsynth_dry.wav"

OUTPUT_JSON = (
    OUTPUT_DIR
    / "t002b_fluidsynth_render_results.json"
)


# ============================================================
# EXPECTED / GOVERNANCE VALUES
# ============================================================

EXPECTED_FLUIDSYNTH_VERSION = "2.6.1"

EXPECTED_SOUNDFONT_SHA256 = (
    "F45B6B4A68B6BF3D792FCBB6D7DE24DC701A0F89C5900A21EF3AAECE993B839A"
)

EXPECTED_SOUNDFONT_SIZE = 31_281_186

EXPECTED_MIDI_DURATION_SECONDS = 8.0

TARGET_SAMPLE_RATE = 48_000

SOUNDFONT_ASSET_ID = "LAISE-SF-TEST-0001"

SOUNDFONT_STATUS = "TEST_ONLY"

SOUNDFONT_PRODUCTION_ALLOWED = False


# ============================================================
# HELPERS
# ============================================================

def sha256_file(path: Path) -> str:
    sha = hashlib.sha256()

    with path.open("rb") as file:
        while True:
            block = file.read(1024 * 1024)

            if not block:
                break

            sha.update(block)

    return sha.hexdigest().upper()


def fail(message: str) -> None:
    print()
    print("FAIL:", message)
    print()
    print("T002-B RESULT: FAIL")
    raise SystemExit(1)


def pass_fail(value: bool) -> str:
    return "PASS" if value else "FAIL"


def rms(samples: list[float]) -> float:
    if not samples:
        return 0.0

    return math.sqrt(
        sum(sample * sample for sample in samples)
        / len(samples)
    )


def dbfs(value: float) -> float | None:
    if value <= 0:
        return None

    return 20.0 * math.log10(value)


# ============================================================
# WAV ANALYSIS
# ============================================================

def analyze_wav(path: Path) -> dict:
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frame_count = wav.getnframes()
        compression = wav.getcomptype()

        raw_audio = wav.readframes(frame_count)

    duration = (
        frame_count / sample_rate
        if sample_rate > 0
        else 0.0
    )

    if sample_width == 2:
        sample_count = len(raw_audio) // 2

        integer_samples = struct.unpack(
            "<" + ("h" * sample_count),
            raw_audio,
        )

        normalized = [
            sample / 32768.0
            for sample in integer_samples
        ]

    elif sample_width == 4:
        # FluidSynth commonly produces signed 32-bit PCM
        # when configured for s32 output.
        sample_count = len(raw_audio) // 4

        integer_samples = struct.unpack(
            "<" + ("i" * sample_count),
            raw_audio,
        )

        normalized = [
            sample / 2147483648.0
            for sample in integer_samples
        ]

    else:
        fail(
            f"Unsupported WAV sample width: "
            f"{sample_width} bytes"
        )

    if channels == 2:
        left = normalized[0::2]
        right = normalized[1::2]

    elif channels == 1:
        left = normalized
        right = normalized

    else:
        fail(
            f"Unexpected WAV channel count: {channels}"
        )

    peak = (
        max(abs(sample) for sample in normalized)
        if normalized
        else 0.0
    )

    overall_rms = rms(normalized)
    left_rms = rms(left)
    right_rms = rms(right)

    nonzero_samples = sum(
        1
        for sample in normalized
        if abs(sample) > 1e-8
    )

    nonzero_ratio = (
        nonzero_samples / len(normalized)
        if normalized
        else 0.0
    )

    finite = all(
        math.isfinite(sample)
        for sample in normalized
    )

    return {
        "channels": channels,
        "sample_width_bytes": sample_width,
        "sample_rate_hz": sample_rate,
        "frame_count": frame_count,
        "duration_seconds": duration,
        "compression": compression,
        "peak_linear": peak,
        "peak_dbfs": dbfs(peak),
        "rms_linear": overall_rms,
        "rms_dbfs": dbfs(overall_rms),
        "left_rms": left_rms,
        "right_rms": right_rms,
        "nonzero_samples": nonzero_samples,
        "nonzero_ratio": nonzero_ratio,
        "finite_samples": finite,
    }


# ============================================================
# HEADER
# ============================================================

print()
print("=" * 72)
print("LAISE — T002-B")
print("FluidSynth MIDI -> Dry WAV Validation")
print("=" * 72)
print()

print("Project root:")
print(PROJECT_ROOT)
print()

print("Python:")
print(platform.python_version())
print()


# ============================================================
# PRECHECK
# ============================================================

print("-" * 72)
print("PRECHECK")
print("-" * 72)

checks = {
    "fluidsynth_exists": FLUIDSYNTH_EXE.is_file(),
    "soundfont_exists": SOUNDFONT.is_file(),
    "input_midi_exists": INPUT_MIDI.is_file(),
}

for name, result in checks.items():
    print(f"{name:<30} {pass_fail(result)}")

if not checks["fluidsynth_exists"]:
    fail(f"FluidSynth not found: {FLUIDSYNTH_EXE}")

if not checks["soundfont_exists"]:
    fail(f"SoundFont not found: {SOUNDFONT}")

if not checks["input_midi_exists"]:
    fail(f"T002-A MIDI not found: {INPUT_MIDI}")


# ============================================================
# FLUIDSYNTH VERSION
# ============================================================

version_process = subprocess.run(
    [str(FLUIDSYNTH_EXE), "--version"],
    capture_output=True,
    text=True,
    check=False,
)

version_text = (
    (version_process.stdout or "")
    + "\n"
    + (version_process.stderr or "")
).strip()

fluidsynth_version_ok = (
    EXPECTED_FLUIDSYNTH_VERSION in version_text
)

print()
print("FluidSynth version check:")
print(version_text)
print(
    "Expected version:",
    EXPECTED_FLUIDSYNTH_VERSION,
)
print(
    "Version validation:",
    pass_fail(fluidsynth_version_ok),
)

if not fluidsynth_version_ok:
    fail(
        "Unexpected FluidSynth version."
    )


# ============================================================
# SOUNDFONT GOVERNANCE CHECK
# ============================================================

soundfont_size = SOUNDFONT.stat().st_size
soundfont_sha256 = sha256_file(SOUNDFONT)

soundfont_size_ok = (
    soundfont_size == EXPECTED_SOUNDFONT_SIZE
)

soundfont_hash_ok = (
    soundfont_sha256
    == EXPECTED_SOUNDFONT_SHA256
)

print()
print("-" * 72)
print("SOUNDFONT IDENTITY")
print("-" * 72)

print("Asset ID:       ", SOUNDFONT_ASSET_ID)
print("File:           ", SOUNDFONT.name)
print("Size:           ", soundfont_size, "bytes")
print("SHA-256:        ", soundfont_sha256)
print("Status:         ", SOUNDFONT_STATUS)
print(
    "Production use:",
    SOUNDFONT_PRODUCTION_ALLOWED,
)

print()
print(
    "Size validation:",
    pass_fail(soundfont_size_ok),
)

print(
    "Hash validation:",
    pass_fail(soundfont_hash_ok),
)

if not soundfont_size_ok:
    fail("SoundFont size mismatch.")

if not soundfont_hash_ok:
    fail("SoundFont SHA-256 mismatch.")


# ============================================================
# INPUT MIDI IDENTITY
# ============================================================

midi_size = INPUT_MIDI.stat().st_size
midi_sha256 = sha256_file(INPUT_MIDI)

print()
print("-" * 72)
print("INPUT MIDI")
print("-" * 72)

print("File:")
print(INPUT_MIDI)

print("Size:")
print(midi_size, "bytes")

print("SHA-256:")
print(midi_sha256)


# ============================================================
# PREPARE OUTPUT
# ============================================================

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

if OUTPUT_WAV.exists():
    OUTPUT_WAV.unlink()

if OUTPUT_JSON.exists():
    OUTPUT_JSON.unlink()


# ============================================================
# FLUIDSYNTH RENDER
# ============================================================

print()
print("-" * 72)
print("FLUIDSYNTH OFFLINE RENDER")
print("-" * 72)

command = [
    str(FLUIDSYNTH_EXE),

    # No interactive shell.
    "-i",

    # No MIDI input device.
    "-n",

    # Disable reverb for dry stem.
    "-R", "0",

    # Disable chorus for dry stem.
    "-C", "0",

    # Internal synthesis sample rate.
    "-r", str(TARGET_SAMPLE_RATE),

    # Output directly to WAV.
    "-F", str(OUTPUT_WAV),

    # WAV container.
    "-T", "wav",

    # 16-bit signed PCM for deterministic,
    # easily inspectable validation output.
    "-O", "s16",

    # SoundFont.
    str(SOUNDFONT),

    # MIDI generated by T002-A.
    str(INPUT_MIDI),
]

print("Command:")
print(
    subprocess.list2cmdline(command)
)
print()

render_process = subprocess.run(
    command,
    capture_output=True,
    text=True,
    check=False,
)

stdout = render_process.stdout or ""
stderr = render_process.stderr or ""

print("Return code:")
print(render_process.returncode)

if stdout.strip():
    print()
    print("FluidSynth stdout:")
    print(stdout.strip())

if stderr.strip():
    print()
    print("FluidSynth stderr:")
    print(stderr.strip())

render_return_code_ok = (
    render_process.returncode == 0
)

wav_created = OUTPUT_WAV.is_file()

wav_not_empty = (
    wav_created
    and OUTPUT_WAV.stat().st_size > 44
)

print()
print(
    "Render process:",
    pass_fail(render_return_code_ok),
)

print(
    "WAV created:",
    pass_fail(wav_created),
)

print(
    "WAV not empty:",
    pass_fail(wav_not_empty),
)

if not render_return_code_ok:
    fail(
        f"FluidSynth returned code "
        f"{render_process.returncode}"
    )

if not wav_created:
    fail("FluidSynth did not create WAV.")

if not wav_not_empty:
    fail("Generated WAV is empty.")


# ============================================================
# WAV ANALYSIS
# ============================================================

analysis = analyze_wav(OUTPUT_WAV)

wav_size = OUTPUT_WAV.stat().st_size
wav_sha256 = sha256_file(OUTPUT_WAV)

sample_rate_ok = (
    analysis["sample_rate_hz"]
    == TARGET_SAMPLE_RATE
)

stereo_ok = (
    analysis["channels"] == 2
)

pcm_ok = (
    analysis["compression"] == "NONE"
)

duration_ok = (
    analysis["duration_seconds"]
    >= EXPECTED_MIDI_DURATION_SECONDS
)

not_silent = (
    analysis["rms_linear"] > 1e-6
    and analysis["nonzero_ratio"] > 0.001
)

no_clipping = (
    analysis["peak_linear"] < 1.0
)

numerical_integrity = (
    analysis["finite_samples"]
)

print()
print("-" * 72)
print("WAV ANALYSIS")
print("-" * 72)

print("File:")
print(OUTPUT_WAV)

print()
print("Size:")
print(wav_size, "bytes")

print()
print("SHA-256:")
print(wav_sha256)

print()
print(
    f"Channels:          "
    f"{analysis['channels']}"
)

print(
    f"Sample width:      "
    f"{analysis['sample_width_bytes'] * 8} bit"
)

print(
    f"Sample rate:       "
    f"{analysis['sample_rate_hz']} Hz"
)

print(
    f"Frames:            "
    f"{analysis['frame_count']}"
)

print(
    f"Duration:          "
    f"{analysis['duration_seconds']:.6f} s"
)

print(
    f"Peak:              "
    f"{analysis['peak_linear']:.8f}"
)

if analysis["peak_dbfs"] is not None:
    print(
        f"Peak dBFS:         "
        f"{analysis['peak_dbfs']:.4f} dBFS"
    )

print(
    f"Overall RMS:       "
    f"{analysis['rms_linear']:.8f}"
)

if analysis["rms_dbfs"] is not None:
    print(
        f"RMS dBFS:          "
        f"{analysis['rms_dbfs']:.4f} dBFS"
    )

print(
    f"Left RMS:          "
    f"{analysis['left_rms']:.8f}"
)

print(
    f"Right RMS:         "
    f"{analysis['right_rms']:.8f}"
)

print(
    f"Non-zero ratio:    "
    f"{analysis['nonzero_ratio']:.8f}"
)


# ============================================================
# VALIDATIONS
# ============================================================

validations = {
    "fluidsynth_version_correct":
        fluidsynth_version_ok,

    "soundfont_size_correct":
        soundfont_size_ok,

    "soundfont_sha256_correct":
        soundfont_hash_ok,

    "render_return_code_zero":
        render_return_code_ok,

    "wav_created":
        wav_created,

    "wav_not_empty":
        wav_not_empty,

    "sample_rate_48000":
        sample_rate_ok,

    "stereo_output":
        stereo_ok,

    "pcm_output":
        pcm_ok,

    "duration_at_least_midi_duration":
        duration_ok,

    "audio_not_silent":
        not_silent,

    "no_clipping":
        no_clipping,

    "numerical_integrity":
        numerical_integrity,
}


print()
print("-" * 72)
print("VALIDATIONS")
print("-" * 72)

for name, result in validations.items():
    print(
        f"{name:<40} "
        f"{pass_fail(result)}"
    )


all_pass = all(validations.values())


# ============================================================
# EVIDENCE MANIFEST
# ============================================================

manifest = {
    "test_id": "T002-B",
    "test_name":
        "FluidSynth MIDI to Dry WAV Validation",

    "timestamp_utc":
        datetime.now(timezone.utc).isoformat(),

    "result":
        "PASS" if all_pass else "FAIL",

    "environment": {
        "python_version":
            platform.python_version(),

        "platform":
            platform.platform(),

        "fluidsynth_expected_version":
            EXPECTED_FLUIDSYNTH_VERSION,

        "fluidsynth_version_output":
            version_text,

        "target_sample_rate_hz":
            TARGET_SAMPLE_RATE,
    },

    "input_midi": {
        "path":
            str(INPUT_MIDI.relative_to(PROJECT_ROOT)),

        "size_bytes":
            midi_size,

        "sha256":
            midi_sha256,

        "expected_duration_seconds":
            EXPECTED_MIDI_DURATION_SECONDS,
    },

    "soundfont": {
        "asset_id":
            SOUNDFONT_ASSET_ID,

        "path":
            str(SOUNDFONT.relative_to(PROJECT_ROOT)),

        "filename":
            SOUNDFONT.name,

        "size_bytes":
            soundfont_size,

        "sha256":
            soundfont_sha256,

        "governance_status":
            SOUNDFONT_STATUS,

        "production_allowed":
            SOUNDFONT_PRODUCTION_ALLOWED,
    },

    "render": {
        "dry":
            True,

        "reverb":
            False,

        "chorus":
            False,

        "command":
            command,

        "return_code":
            render_process.returncode,

        "stdout":
            stdout.strip(),

        "stderr":
            stderr.strip(),
    },

    "output_wav": {
        "path":
            str(OUTPUT_WAV.relative_to(PROJECT_ROOT)),

        "size_bytes":
            wav_size,

        "sha256":
            wav_sha256,

        **analysis,
    },

    "validations":
        validations,
}


with OUTPUT_JSON.open(
    "w",
    encoding="utf-8",
) as file:
    json.dump(
        manifest,
        file,
        indent=2,
        ensure_ascii=False,
    )


# ============================================================
# FINAL RESULT
# ============================================================

print()
print("-" * 72)
print("EVIDENCE")
print("-" * 72)

print("WAV:")
print(OUTPUT_WAV)

print()
print("JSON:")
print(OUTPUT_JSON)

print()
print("WAV SHA-256:")
print(wav_sha256)

print()

if all_pass:
    print("=" * 72)
    print("T002-B RESULT: PASS")
    print("=" * 72)
    print()
    print(
        "LAISE synthesis bridge validated:"
    )
    print(
        "MIDI -> FluidSynth -> SoundFont -> Dry WAV"
    )
else:
    print("=" * 72)
    print("T002-B RESULT: FAIL")
    print("=" * 72)
    raise SystemExit(1)
