from pathlib import Path
import json
import hashlib

import numpy as np

from pedalboard import load_plugin
from pedalboard.io import AudioFile


# ============================================================
# LAISE — T001-E
# Linear Spatial Motion Test
#
# Objective:
# Validate dynamic spatial control of dearVR PRO 2.
#
# Motion:
#
# LEFT (-90°)
#      |
#      +-------------------------------> RIGHT (+90°)
#
# Duration: 6 seconds
#
# The audio is processed in sequential blocks.
# Before each block, LAISE updates the dearVR azimuth.
#
# IMPORTANT:
# The plugin instance is NOT recreated between blocks.
# DSP state must remain continuous throughout the movement.
# ============================================================


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

PLUGIN_PATH = Path(
    r"C:\Program Files\Common Files\VST3\dearVR PRO 2.vst3"
    r"\Contents\x86_64-win\dearVR PRO 2.vst3"
)

OUTPUT_DIR = (
    Path("evidence")
    / "T001"
    / "T001-E"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "t001e_left_to_right.wav"
)

JSON_FILE = (
    OUTPUT_DIR
    / "t001e_linear_motion_results.json"
)


SAMPLE_RATE = 48_000

DURATION_SECONDS = 6.0

RANDOM_SEED = 20260920

AMPLITUDE = 0.10


# ------------------------------------------------------------
# Processing block
#
# 256 samples @ 48 kHz:
#
# 256 / 48000 = 5.333 ms
#
# Parameter position will therefore be updated approximately
# 187.5 times per second.
# ------------------------------------------------------------

BLOCK_SIZE = 256


# ------------------------------------------------------------
# Spatial trajectory
#
# Based on the mapping experimentally supported by T001-B
# and T001-D:
#
# -90° -> raw 0.25
#   0° -> raw 0.50
# +90° -> raw 0.75
# ------------------------------------------------------------

START_AZIMUTH_DEGREES = -90.0
END_AZIMUTH_DEGREES = 90.0

START_AZIMUTH_RAW = 0.25
END_AZIMUTH_RAW = 0.75


# ------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------

def rms(audio):
    return float(
        np.sqrt(
            np.mean(
                np.square(audio)
            )
        )
    )


def peak(audio):
    return float(
        np.max(
            np.abs(audio)
        )
    )


def sha256_file(path):
    digest = hashlib.sha256()

    with open(path, "rb") as file:
        while True:
            block = file.read(
                1024 * 1024
            )

            if not block:
                break

            digest.update(block)

    return digest.hexdigest()


def safe_correlation(left, right):

    if np.std(left) == 0:
        return 0.0

    if np.std(right) == 0:
        return 0.0

    return float(
        np.corrcoef(
            left,
            right,
        )[0, 1]
    )


def raw_to_degrees(raw_value):
    """
    Experimental mapping established from T001-B/T001-D:

        raw 0.0 -> -180°
        raw 0.5 ->    0°
        raw 1.0 -> +180°

    This function is still part of the experimental
    validation layer and is not yet the production
    dearvr_adapter implementation.
    """

    return (
        raw_value * 360.0
    ) - 180.0


# ------------------------------------------------------------
# Header
# ------------------------------------------------------------

print("=" * 78)
print("LAISE — T001-E")
print("dearVR PRO 2 — Linear Spatial Motion")
print("=" * 78)


# ------------------------------------------------------------
# Preliminary checks
# ------------------------------------------------------------

if not PLUGIN_PATH.exists():

    raise FileNotFoundError(
        f"dearVR PRO 2 was not found:\n"
        f"{PLUGIN_PATH}"
    )


OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ------------------------------------------------------------
# 1. Generate deterministic broadband source
# ------------------------------------------------------------

print(
    "\n[1/7] Generating deterministic broadband source..."
)


sample_count = int(
    SAMPLE_RATE
    * DURATION_SECONDS
)


rng = np.random.default_rng(
    RANDOM_SEED
)


signal = rng.standard_normal(
    sample_count
).astype(np.float32)


# Normalize source.

signal /= np.max(
    np.abs(signal)
)


signal *= AMPLITUDE


# ------------------------------------------------------------
# Fade-in / fade-out
# ------------------------------------------------------------

fade_duration_seconds = 0.050

fade_samples = int(
    SAMPLE_RATE
    * fade_duration_seconds
)


fade_in = np.linspace(
    0.0,
    1.0,
    fade_samples,
    dtype=np.float32,
)


fade_out = np.linspace(
    1.0,
    0.0,
    fade_samples,
    dtype=np.float32,
)


signal[:fade_samples] *= fade_in

signal[-fade_samples:] *= fade_out


# ------------------------------------------------------------
# Dual-mono input required by current dearVR VST3 bus.
# ------------------------------------------------------------

stereo_input = np.stack(
    [
        signal,
        signal,
    ],
    axis=0,
).astype(np.float32)


print(
    f"Sample rate:       "
    f"{SAMPLE_RATE} Hz"
)

print(
    f"Duration:          "
    f"{DURATION_SECONDS:.2f} s"
)

print(
    f"Samples:           "
    f"{sample_count}"
)

print(
    f"Random seed:       "
    f"{RANDOM_SEED}"
)

print(
    f"Amplitude:         "
    f"{AMPLITUDE}"
)

print(
    f"Block size:        "
    f"{BLOCK_SIZE} samples"
)

print(
    f"Block duration:    "
    f"{BLOCK_SIZE / SAMPLE_RATE * 1000:.3f} ms"
)

print(
    "Source:            "
    "deterministic broadband noise"
)

print(
    "VST input:         "
    "dual-mono"
)


# ------------------------------------------------------------
# 2. Load dearVR
# ------------------------------------------------------------

print(
    "\n[2/7] Loading dearVR PRO 2..."
)


plugin = load_plugin(
    str(PLUGIN_PATH)
)


latency_samples = int(
    plugin.reported_latency_samples
)


latency_ms = (
    latency_samples
    / SAMPLE_RATE
    * 1000.0
)


print(
    f"Plugin:             "
    f"{plugin.name}"
)

print(
    f"Manufacturer:       "
    f"{plugin.manufacturer_name}"
)

print(
    f"Identifier:         "
    f"{plugin.identifier}"
)

print(
    f"Latency:            "
    f"{latency_samples} samples"
)

print(
    f"Latency:            "
    f"{latency_ms:.3f} ms"
)


# ------------------------------------------------------------
# 3. Configure static parameters
# ------------------------------------------------------------

print(
    "\n[3/7] Configuring spatial renderer..."
)


# Polar coordinate system.

plugin.parameters[
    "coordinate_system"
].raw_value = 1.0


# Zero elevation.

plugin.parameters[
    "elevation"
].raw_value = 0.5


distance_raw = float(
    plugin.parameters[
        "distance"
    ].raw_value
)


print(
    "Coordinate system: Polar"
)

print(
    "Elevation:         0°"
)

print(
    f"Distance raw:      "
    f"{distance_raw}"
)

print(
    f"Motion:            "
    f"{START_AZIMUTH_DEGREES:.0f}° "
    f"-> "
    f"{END_AZIMUTH_DEGREES:.0f}°"
)


# ------------------------------------------------------------
# 4. Dynamic block processing
# ------------------------------------------------------------

print(
    "\n[4/7] Processing dynamic spatial trajectory..."
)


processed_blocks = []

trajectory_log = []


total_blocks = int(
    np.ceil(
        sample_count
        / BLOCK_SIZE
    )
)


print(
    f"Total blocks:       "
    f"{total_blocks}"
)


for block_index in range(
    total_blocks
):

    start_sample = (
        block_index
        * BLOCK_SIZE
    )

    end_sample = min(
        start_sample
        + BLOCK_SIZE,
        sample_count,
    )


    # --------------------------------------------------------
    # Normalized trajectory progress:
    #
    # 0.0 -> beginning
    # 1.0 -> end
    # --------------------------------------------------------

    if total_blocks > 1:

        progress = (
            block_index
            / (total_blocks - 1)
        )

    else:

        progress = 0.0


    # --------------------------------------------------------
    # Linear interpolation of azimuth.
    # --------------------------------------------------------

    azimuth_raw = (
        START_AZIMUTH_RAW
        +
        (
            END_AZIMUTH_RAW
            - START_AZIMUTH_RAW
        )
        * progress
    )


    azimuth_degrees = raw_to_degrees(
        azimuth_raw
    )


    plugin.parameters[
        "azimuth"
    ].raw_value = float(
        azimuth_raw
    )


    input_block = stereo_input[
        :,
        start_sample:end_sample,
    ]


    # --------------------------------------------------------
    # CRITICAL:
    #
    # reset=False preserves dearVR's DSP state between
    # consecutive blocks.
    #
    # This is required for continuous processing.
    # --------------------------------------------------------

    processed_block = plugin.process(
        input_block,
        sample_rate=SAMPLE_RATE,
        reset=False,
    )


    processed_block = np.asarray(
        processed_block,
        dtype=np.float32,
    )


    if processed_block.ndim != 2:

        raise RuntimeError(
            "Unexpected processed block shape: "
            f"{processed_block.shape}"
        )


    if processed_block.shape[0] != 2:

        raise RuntimeError(
            "Expected stereo output from dearVR."
        )


    if not np.all(
        np.isfinite(processed_block)
    ):

        raise RuntimeError(
            f"NaN/Infinity detected in block "
            f"{block_index}."
        )


    processed_blocks.append(
        processed_block
    )


    trajectory_log.append(
        {
            "block": block_index,
            "start_sample": start_sample,
            "end_sample": end_sample,
            "time_seconds": (
                start_sample
                / SAMPLE_RATE
            ),
            "progress": float(
                progress
            ),
            "azimuth_raw": float(
                azimuth_raw
            ),
            "azimuth_degrees": float(
                azimuth_degrees
            ),
        }
    )


    # Periodic progress display.

    if (
        block_index == 0
        or block_index
        == total_blocks - 1
        or block_index
        % 200 == 0
    ):

        print(
            f"Block "
            f"{block_index + 1:4d}"
            f"/{total_blocks} | "
            f"t="
            f"{start_sample / SAMPLE_RATE:5.2f}s | "
            f"azimuth="
            f"{azimuth_degrees:+7.2f}° | "
            f"raw="
            f"{azimuth_raw:.6f}"
        )


# ------------------------------------------------------------
# Concatenate processed blocks
# ------------------------------------------------------------

processed = np.concatenate(
    processed_blocks,
    axis=1,
)


# Ensure exact requested duration.

processed = processed[
    :,
    :sample_count,
]


print(
    f"\nFinal output shape: "
    f"{processed.shape}"
)


# ------------------------------------------------------------
# 5. Analyze motion
# ------------------------------------------------------------

print(
    "\n[5/7] Analyzing dynamic render..."
)


if processed.shape != stereo_input.shape:

    raise RuntimeError(
        "Output shape differs from input shape: "
        f"{processed.shape} vs "
        f"{stereo_input.shape}"
    )


if not np.all(
    np.isfinite(processed)
):

    raise RuntimeError(
        "Final output contains NaN or Infinity."
    )


overall_peak = peak(
    processed
)

overall_rms = rms(
    processed
)


left = processed[0]
right = processed[1]


left_rms = rms(
    left
)

right_rms = rms(
    right
)


correlation = safe_correlation(
    left,
    right,
)


# ------------------------------------------------------------
# Divide output into three temporal regions:
#
# START  -> should favor LEFT
# CENTER -> should approach central image
# END    -> should favor RIGHT
#
# Use 20% of total duration for each diagnostic region.
# ------------------------------------------------------------

region_size = int(
    sample_count
    * 0.20
)


start_left = left[
    :region_size
]

start_right = right[
    :region_size
]


center_start = (
    sample_count // 2
    - region_size // 2
)

center_end = (
    center_start
    + region_size
)


center_left = left[
    center_start:center_end
]

center_right = right[
    center_start:center_end
]


end_left = left[
    -region_size:
]

end_right = right[
    -region_size:
]


start_l_rms = rms(
    start_left
)

start_r_rms = rms(
    start_right
)


center_l_rms = rms(
    center_left
)

center_r_rms = rms(
    center_right
)


end_l_rms = rms(
    end_left
)

end_r_rms = rms(
    end_right
)


epsilon = 1e-12


start_ild = float(
    20.0
    * np.log10(
        (start_l_rms + epsilon)
        / (start_r_rms + epsilon)
    )
)


center_ild = float(
    20.0
    * np.log10(
        (center_l_rms + epsilon)
        / (center_r_rms + epsilon)
    )
)


end_ild = float(
    20.0
    * np.log10(
        (end_l_rms + epsilon)
        / (end_r_rms + epsilon)
    )
)


print(
    f"Overall peak:       "
    f"{overall_peak:.8f}"
)

print(
    f"Overall RMS:        "
    f"{overall_rms:.8f}"
)

print(
    f"L RMS:              "
    f"{left_rms:.8f}"
)

print(
    f"R RMS:              "
    f"{right_rms:.8f}"
)

print(
    f"L/R correlation:    "
    f"{correlation:.8f}"
)


print("\nTemporal spatial signature:")

print(
    f"START  (~LEFT)   "
    f"L={start_l_rms:.8f} "
    f"R={start_r_rms:.8f} "
    f"ILD={start_ild:+.4f} dB"
)

print(
    f"CENTER (~0°)     "
    f"L={center_l_rms:.8f} "
    f"R={center_r_rms:.8f} "
    f"ILD={center_ild:+.4f} dB"
)

print(
    f"END    (~RIGHT)  "
    f"L={end_l_rms:.8f} "
    f"R={end_r_rms:.8f} "
    f"ILD={end_ild:+.4f} dB"
)


# ------------------------------------------------------------
# Objective motion validation
#
# Start should favor LEFT:
# ILD > 0
#
# End should favor RIGHT:
# ILD < 0
#
# We deliberately do not require center ILD == 0.
# ------------------------------------------------------------

left_start_valid = (
    start_ild > 0.0
)

right_end_valid = (
    end_ild < 0.0
)


if not left_start_valid:

    raise RuntimeError(
        "FAIL: beginning of trajectory "
        "does not favor LEFT channel."
    )


if not right_end_valid:

    raise RuntimeError(
        "FAIL: end of trajectory "
        "does not favor RIGHT channel."
    )


print(
    "\nStart favors LEFT:  PASS"
)

print(
    "End favors RIGHT:  PASS"
)


# ------------------------------------------------------------
# 6. Write WAV and evidence JSON
# ------------------------------------------------------------

print(
    "\n[6/7] Writing evidence..."
)


with AudioFile(
    str(OUTPUT_FILE),
    "w",
    SAMPLE_RATE,
    2,
) as audio_file:

    audio_file.write(
        processed
    )


wav_hash = sha256_file(
    OUTPUT_FILE
)


evidence = {
    "test_id": "T001-E",
    "test_name": (
        "Linear Spatial Motion"
    ),
    "status": "PASS",
    "sample_rate_hz": SAMPLE_RATE,
    "duration_seconds": (
        DURATION_SECONDS
    ),
    "block_size_samples": (
        BLOCK_SIZE
    ),
    "block_duration_ms": (
        BLOCK_SIZE
        / SAMPLE_RATE
        * 1000.0
    ),
    "source": {
        "type": (
            "deterministic broadband noise"
        ),
        "random_seed": (
            RANDOM_SEED
        ),
        "amplitude": (
            AMPLITUDE
        ),
        "input_layout": (
            "dual-mono stereo"
        ),
    },
    "plugin": {
        "name": plugin.name,
        "manufacturer": (
            plugin.manufacturer_name
        ),
        "identifier": (
            plugin.identifier
        ),
        "latency_samples": (
            latency_samples
        ),
        "latency_ms": (
            latency_ms
        ),
    },
    "trajectory": {
        "type": (
            "linear_left_to_right"
        ),
        "start_degrees": (
            START_AZIMUTH_DEGREES
        ),
        "end_degrees": (
            END_AZIMUTH_DEGREES
        ),
        "start_raw": (
            START_AZIMUTH_RAW
        ),
        "end_raw": (
            END_AZIMUTH_RAW
        ),
        "coordinate_system": (
            "polar"
        ),
        "elevation_degrees": 0.0,
        "distance_raw": (
            distance_raw
        ),
    },
    "measurements": {
        "overall_peak": (
            overall_peak
        ),
        "overall_rms": (
            overall_rms
        ),
        "left_rms": (
            left_rms
        ),
        "right_rms": (
            right_rms
        ),
        "left_right_correlation": (
            correlation
        ),
        "start_ild_db": (
            start_ild
        ),
        "center_ild_db": (
            center_ild
        ),
        "end_ild_db": (
            end_ild
        ),
    },
    "validation": {
        "start_favors_left": (
            left_start_valid
        ),
        "end_favors_right": (
            right_end_valid
        ),
    },
    "output": {
        "wav": str(
            OUTPUT_FILE.resolve()
        ),
        "sha256": (
            wav_hash
        ),
    },
    "trajectory_log": (
        trajectory_log
    ),
}


with open(
    JSON_FILE,
    "w",
    encoding="utf-8",
) as file:

    json.dump(
        evidence,
        file,
        indent=2,
        ensure_ascii=False,
    )


print(
    f"WAV:  "
    f"{OUTPUT_FILE.resolve()}"
)

print(
    f"JSON: "
    f"{JSON_FILE.resolve()}"
)

print(
    f"SHA256: "
    f"{wav_hash}"
)


# ------------------------------------------------------------
# 7. Final result
# ------------------------------------------------------------

print(
    "\n[7/7] Final validation..."
)


if overall_peak >= 1.0:

    print(
        "WARNING: output reached "
        "digital full scale."
    )

else:

    print(
        "Clipping check:      PASS"
    )


print(
    "Numerical integrity:  PASS"
)

print(
    "Dynamic trajectory:   PASS"
)


print(
    "\n" + "=" * 78
)

print(
    "T001-E RESULT: PASS"
)

print(
    "=" * 78
)


print(
    "\nPerceptual test:"
)

print(
    "Listen with headphones."
)

print(
    "Expected trajectory:"
)

print(
    "LEFT  ->  CENTER  ->  RIGHT"
)

print(
    "\nReport whether you perceive:"
)

print(
    "1. clear continuous movement,"
)

print(
    "2. jumps or discontinuities,"
)

print(
    "3. movement in the expected direction,"
)

print(
    "4. sound inside or outside the head."
)