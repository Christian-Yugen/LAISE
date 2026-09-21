from pathlib import Path

import numpy as np

from pedalboard import load_plugin
from pedalboard.io import AudioFile


# ============================================================
# LAISE — T001-C
# Static Spatial Render Test
#
# Objective:
# Validate the complete static audio path:
#
# Python
#   -> deterministic test signal
#   -> dearVR PRO 2 via Pedalboard
#   -> stereo spatial render
#   -> WAV evidence file
#
# Technical baseline:
# - Sample rate: 48 kHz
# - Processing: float32
# - Source: deterministic 440 Hz sine wave
# - VST3 input: dual-mono stereo
# - Spatial system: Polar
# - Position: front / 0° azimuth / 0° elevation
# ============================================================


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

PLUGIN_PATH = Path(
    r"C:\Program Files\Common Files\VST3\dearVR PRO 2.vst3"
    r"\Contents\x86_64-win\dearVR PRO 2.vst3"
)

OUTPUT_DIR = Path("evidence") / "T001"

OUTPUT_FILE = (
    OUTPUT_DIR / "t001c_front_static.wav"
)

SAMPLE_RATE = 48_000
DURATION_SECONDS = 5.0
FREQUENCY_HZ = 440.0

# Conservative test amplitude.
AMPLITUDE = 0.20


# ------------------------------------------------------------
# Header
# ------------------------------------------------------------

print("=" * 72)
print("LAISE — T001-C")
print("dearVR PRO 2 — Static Spatial Render")
print("=" * 72)


# ------------------------------------------------------------
# Preliminary checks
# ------------------------------------------------------------

if not PLUGIN_PATH.exists():
    raise FileNotFoundError(
        f"dearVR PRO 2 was not found:\n{PLUGIN_PATH}"
    )

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ------------------------------------------------------------
# 1. Generate deterministic source
# ------------------------------------------------------------

print("\n[1/6] Generating deterministic test signal...")

sample_count = int(
    SAMPLE_RATE * DURATION_SECONDS
)

time = (
    np.arange(
        sample_count,
        dtype=np.float32,
    )
    / SAMPLE_RATE
)

signal = (
    AMPLITUDE
    * np.sin(
        2.0
        * np.pi
        * FREQUENCY_HZ
        * time
    )
).astype(np.float32)


# ------------------------------------------------------------
# dearVR PRO 2 exposes a 2-input / 2-output main bus
# through Pedalboard.
#
# The source itself remains conceptually mono.
#
# We duplicate the exact same mono signal into both input
# channels. This produces a dual-mono input:
#
# LEFT  = mono source
# RIGHT = identical mono source
#
# This satisfies the VST3 bus requirement while preserving
# the deterministic nature of the source.
# ------------------------------------------------------------

stereo_input = np.stack(
    [
        signal,
        signal,
    ],
    axis=0,
).astype(np.float32)


print(f"Sample rate: {SAMPLE_RATE} Hz")
print(
    f"Duration:    "
    f"{DURATION_SECONDS:.2f} s"
)
print(
    f"Frequency:   "
    f"{FREQUENCY_HZ:.1f} Hz"
)
print(
    f"Amplitude:   "
    f"{AMPLITUDE:.2f}"
)
print(
    f"Samples:     "
    f"{sample_count}"
)
print(
    "Source:      "
    "mono duplicated to dual-mono"
)
print(
    f"Input shape: "
    f"{stereo_input.shape}"
)
print(
    f"Data type:   "
    f"{stereo_input.dtype}"
)


# ------------------------------------------------------------
# 2. Load dearVR PRO 2
# ------------------------------------------------------------

print("\n[2/6] Loading dearVR PRO 2...")

plugin = load_plugin(
    str(PLUGIN_PATH)
)

print(
    f"Plugin:       "
    f"{plugin.name}"
)

print(
    f"Manufacturer: "
    f"{plugin.manufacturer_name}"
)

print(
    f"Identifier:   "
    f"{plugin.identifier}"
)

print(
    f"Latency:      "
    f"{plugin.reported_latency_samples} samples"
)

latency_ms = (
    plugin.reported_latency_samples
    / SAMPLE_RATE
    * 1000.0
)

print(
    f"Latency:      "
    f"{latency_ms:.3f} ms @ {SAMPLE_RATE} Hz"
)


# ------------------------------------------------------------
# 3. Configure spatial position
# ------------------------------------------------------------

print("\n[3/6] Configuring spatial position...")


# ------------------------------------------------------------
# Coordinate system
#
# T001-B established:
#
# 0.0 -> Cartesian
# 1.0 -> Polar
# ------------------------------------------------------------

plugin.parameters[
    "coordinate_system"
].raw_value = 1.0


# ------------------------------------------------------------
# AZIMUTH
#
# T001-B observed:
#
# raw 0.0 -> -180°
# raw 0.5 ->    0°
# raw 1.0 -> +180°
#
# For this test:
#
# azimuth = 0°
# source directly in front.
# ------------------------------------------------------------

plugin.parameters[
    "azimuth"
].raw_value = 0.5


# ------------------------------------------------------------
# ELEVATION
#
# T001-B observed:
#
# raw 0.0 -> -90°
# raw 0.5 ->   0°
# raw 1.0 -> +90°
#
# For this test:
#
# elevation = 0°
# ------------------------------------------------------------

plugin.parameters[
    "elevation"
].raw_value = 0.5


# ------------------------------------------------------------
# Distance
#
# For T001-C we deliberately preserve the plugin's
# currently observed/default distance.
#
# Distance mapping will be formally validated in a later
# parameter-mapping test.
# ------------------------------------------------------------

distance_raw = plugin.parameters[
    "distance"
].raw_value


print("Coordinate system: Polar")
print("Azimuth target:    0°")
print("Elevation target:  0°")
print(
    f"Azimuth raw:       "
    f"{plugin.parameters['azimuth'].raw_value}"
)
print(
    f"Elevation raw:     "
    f"{plugin.parameters['elevation'].raw_value}"
)
print(
    f"Distance raw:      "
    f"{distance_raw}"
)


# ------------------------------------------------------------
# 4. Process through dearVR
# ------------------------------------------------------------

print(
    "\n[4/6] Processing audio "
    "through dearVR PRO 2..."
)

processed = plugin.process(
    stereo_input,
    sample_rate=SAMPLE_RATE,
    reset=True,
)

processed = np.asarray(
    processed,
    dtype=np.float32,
)


print(
    f"Input shape:  "
    f"{stereo_input.shape}"
)

print(
    f"Output shape: "
    f"{processed.shape}"
)

print(
    f"Output dtype: "
    f"{processed.dtype}"
)


# ------------------------------------------------------------
# 5. Validate render
# ------------------------------------------------------------

print("\n[5/6] Validating render...")


# Validate dimensionality.

if processed.ndim != 2:
    raise RuntimeError(
        "FAIL: dearVR returned an unexpected "
        f"audio array shape: {processed.shape}"
    )


# dearVR is expected to return stereo.

if processed.shape[0] != 2:
    raise RuntimeError(
        "FAIL: expected 2 output channels; "
        f"received {processed.shape[0]}."
    )


# Validate numerical integrity.

if not np.all(
    np.isfinite(processed)
):
    raise RuntimeError(
        "FAIL: output contains NaN or Infinity."
    )


# Validate that output is not silent.

peak = float(
    np.max(
        np.abs(processed)
    )
)

rms = float(
    np.sqrt(
        np.mean(
            np.square(processed)
        )
    )
)

if peak <= 0.0:
    raise RuntimeError(
        "FAIL: dearVR returned silence."
    )


# ------------------------------------------------------------
# Channel analysis
# ------------------------------------------------------------

left = processed[0]
right = processed[1]

left_peak = float(
    np.max(
        np.abs(left)
    )
)

right_peak = float(
    np.max(
        np.abs(right)
    )
)

left_rms = float(
    np.sqrt(
        np.mean(
            np.square(left)
        )
    )
)

right_rms = float(
    np.sqrt(
        np.mean(
            np.square(right)
        )
    )
)

mean_lr_difference = float(
    np.mean(
        np.abs(
            left - right
        )
    )
)


# ------------------------------------------------------------
# Compare processed output with original dual-mono input.
#
# This is useful evidence that the VST actually modified
# the audio rather than simply passing it through.
#
# We compare only the common number of samples.
# ------------------------------------------------------------

common_samples = min(
    stereo_input.shape[1],
    processed.shape[1],
)

input_common = stereo_input[
    :,
    :common_samples,
]

output_common = processed[
    :,
    :common_samples,
]

mean_input_output_difference = float(
    np.mean(
        np.abs(
            output_common
            - input_common
        )
    )
)


print(f"Peak overall:       {peak:.8f}")
print(f"RMS overall:        {rms:.8f}")

print(
    f"Left peak:          "
    f"{left_peak:.8f}"
)

print(
    f"Right peak:         "
    f"{right_peak:.8f}"
)

print(
    f"Left RMS:           "
    f"{left_rms:.8f}"
)

print(
    f"Right RMS:          "
    f"{right_rms:.8f}"
)

print(
    f"Mean |L-R|:         "
    f"{mean_lr_difference:.10f}"
)

print(
    f"Mean |OUT-IN|:      "
    f"{mean_input_output_difference:.10f}"
)


# ------------------------------------------------------------
# Clipping warning
# ------------------------------------------------------------

if peak >= 1.0:
    print(
        "\nWARNING: output reached or exceeded "
        "digital full scale."
    )
else:
    print(
        "\nClipping check:     PASS"
    )


# ------------------------------------------------------------
# 6. Write evidence WAV
# ------------------------------------------------------------

print("\n[6/6] Writing evidence WAV...")


with AudioFile(
    str(OUTPUT_FILE),
    "w",
    SAMPLE_RATE,
    processed.shape[0],
) as audio_file:

    audio_file.write(
        processed
    )


# ------------------------------------------------------------
# Final report
# ------------------------------------------------------------

print("\nEvidence file:")

print(
    OUTPUT_FILE.resolve()
)

print("\n" + "=" * 72)

print(
    "T001-C RESULT: PASS"
)

print("=" * 72)

print(
    "\nStatic render completed successfully."
)

print(
    "Listen with HEADPHONES for perceptual verification."
)