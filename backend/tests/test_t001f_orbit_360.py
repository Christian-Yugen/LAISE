from pathlib import Path
import json
import hashlib

import numpy as np

from pedalboard import load_plugin
from pedalboard.io import AudioFile


# ============================================================
# LAISE — T001-F
# 360-Degree Spatial Orbit Test
#
# Objective:
# Validate a complete programmable spatial orbit around
# the listener using dearVR PRO 2.
#
# Trajectory:
#
#                 FRONT 0°
#                    |
#                    v
#
# FRONT -> RIGHT -> BACK -> LEFT -> FRONT
#
#   0°      +90°     180°   270°/−90°   360°/0°
#
# The source remains:
#   - elevation = 0°
#   - distance = constant
#
# Only azimuth changes.
#
# Processing is block-based and the same plugin instance
# remains alive for the entire render.
#
# IMPORTANT:
# This is still an experimental validation test.
# It does not yet replace the production dearvr_adapter.py.
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
    / "T001-F"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "t001f_orbit_360.wav"
)

JSON_FILE = (
    OUTPUT_DIR
    / "t001f_orbit_360_results.json"
)


SAMPLE_RATE = 48_000

# A slightly longer duration than T001-E makes the
# front/back/left/right transitions easier to perceive.
DURATION_SECONDS = 12.0

RANDOM_SEED = 20260920

AMPLITUDE = 0.10


# ------------------------------------------------------------
# Block processing
#
# 256 samples @ 48 kHz = 5.333 ms
#
# Spatial parameter update rate:
#
# 48000 / 256 = 187.5 updates/second
# ------------------------------------------------------------

BLOCK_SIZE = 256


# ------------------------------------------------------------
# Orbit configuration
#
# One complete revolution:
#
# 0°   -> FRONT
# 90°  -> RIGHT
# 180° -> BACK
# 270° -> LEFT
# 360° -> FRONT
# ------------------------------------------------------------

START_ORBIT_DEGREES = 0.0
END_ORBIT_DEGREES = 360.0


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


def orbit_to_signed_degrees(orbit_degrees):
    """
    Convert continuous orbit angle 0..360 to the signed
    dearVR representation -180..+180.

    Examples:

        0°   ->    0°
        90°  ->  +90°
        180° -> +180°
        270° ->  -90°
        360° ->    0°

    The 180° point is explicitly preserved as +180°.
    """

    normalized = (
        orbit_degrees % 360.0
    )

    if np.isclose(
        orbit_degrees,
        360.0,
    ):
        return 0.0

    if normalized <= 180.0:
        return normalized

    return normalized - 360.0


def degrees_to_raw(angle_degrees):
    """
    Experimental dearVR azimuth mapping established by
    T001-B, T001-D and T001-E:

        -180° -> 0.00
         -90° -> 0.25
           0° -> 0.50
         +90° -> 0.75
        +180° -> 1.00
    """

    raw_value = (
        angle_degrees + 180.0
    ) / 360.0

    return float(
        np.clip(
            raw_value,
            0.0,
            1.0,
        )
    )


def ild_db(left_audio, right_audio):

    left_rms = rms(
        left_audio
    )

    right_rms = rms(
        right_audio
    )

    epsilon = 1e-12

    value = float(
        20.0
        * np.log10(
            (left_rms + epsilon)
            / (right_rms + epsilon)
        )
    )

    return {
        "left_rms": left_rms,
        "right_rms": right_rms,
        "ild_db": value,
    }


# ------------------------------------------------------------
# Header
# ------------------------------------------------------------

print("=" * 78)
print("LAISE — T001-F")
print("dearVR PRO 2 — 360-Degree Spatial Orbit")
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
    "\n[1/8] Generating deterministic broadband source..."
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
# dearVR currently exposes a 2-in / 2-out main bus through
# Pedalboard, therefore the conceptual mono test source is
# duplicated to dual-mono.
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
    "\n[2/8] Loading dearVR PRO 2..."
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
# 3. Configure renderer
# ------------------------------------------------------------

print(
    "\n[3/8] Configuring spatial renderer..."
)


plugin.parameters[
    "coordinate_system"
].raw_value = 1.0


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
    "Orbit:             "
    "0° -> 360°"
)

print(
    "Direction:         "
    "FRONT -> RIGHT -> BACK -> LEFT -> FRONT"
)


# ------------------------------------------------------------
# 4. Process continuous orbit
# ------------------------------------------------------------

print(
    "\n[4/8] Processing 360-degree trajectory..."
)


total_blocks = int(
    np.ceil(
        sample_count
        / BLOCK_SIZE
    )
)


processed_blocks = []

trajectory_log = []


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


    if total_blocks > 1:

        progress = (
            block_index
            / (total_blocks - 1)
        )

    else:

        progress = 0.0


    # --------------------------------------------------------
    # Continuous orbit angle.
    #
    # This variable never jumps:
    #
    # 0 -> 90 -> 180 -> 270 -> 360
    # --------------------------------------------------------

    orbit_degrees = (
        START_ORBIT_DEGREES
        +
        (
            END_ORBIT_DEGREES
            - START_ORBIT_DEGREES
        )
        * progress
    )


    # --------------------------------------------------------
    # Convert to dearVR signed azimuth.
    #
    # 270° becomes -90°, for example.
    # --------------------------------------------------------

    signed_degrees = (
        orbit_to_signed_degrees(
            orbit_degrees
        )
    )


    azimuth_raw = degrees_to_raw(
        signed_degrees
    )


    plugin.parameters[
        "azimuth"
    ].raw_value = azimuth_raw


    input_block = stereo_input[
        :,
        start_sample:end_sample,
    ]


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
            f"Unexpected output shape in block "
            f"{block_index}: "
            f"{processed_block.shape}"
        )


    if processed_block.shape[0] != 2:

        raise RuntimeError(
            "dearVR did not return stereo output."
        )


    if not np.all(
        np.isfinite(processed_block)
    ):

        raise RuntimeError(
            f"NaN or Infinity detected in block "
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
            "time_seconds": float(
                start_sample
                / SAMPLE_RATE
            ),
            "progress": float(
                progress
            ),
            "orbit_degrees": float(
                orbit_degrees
            ),
            "signed_azimuth_degrees": float(
                signed_degrees
            ),
            "azimuth_raw": float(
                azimuth_raw
            ),
        }
    )


    # --------------------------------------------------------
    # Console diagnostics near cardinal points.
    # --------------------------------------------------------

    quarter = max(
        1,
        (total_blocks - 1) // 4,
    )


    important_blocks = {
        0,
        quarter,
        quarter * 2,
        quarter * 3,
        total_blocks - 1,
    }


    if (
        block_index in important_blocks
        or block_index % 500 == 0
    ):

        print(
            f"Block "
            f"{block_index + 1:4d}"
            f"/{total_blocks} | "
            f"t="
            f"{start_sample / SAMPLE_RATE:6.2f}s | "
            f"orbit="
            f"{orbit_degrees:7.2f}° | "
            f"signed="
            f"{signed_degrees:+7.2f}° | "
            f"raw="
            f"{azimuth_raw:.6f}"
        )


# ------------------------------------------------------------
# Concatenate output
# ------------------------------------------------------------

processed = np.concatenate(
    processed_blocks,
    axis=1,
)


processed = processed[
    :,
    :sample_count,
]


print(
    f"\nFinal output shape: "
    f"{processed.shape}"
)


# ------------------------------------------------------------
# 5. General validation
# ------------------------------------------------------------

print(
    "\n[5/8] Analyzing complete orbit..."
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


print(
    f"Overall peak:       "
    f"{overall_peak:.8f}"
)

print(
    f"Overall RMS:        "
    f"{overall_rms:.8f}"
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
    f"L/R correlation:    "
    f"{correlation:.8f}"
)


# ------------------------------------------------------------
# 6. Cardinal-region diagnostics
#
# Orbit duration = 12 seconds.
#
# Approximate centers:
#
# FRONT start = 0.00 s
# RIGHT       = 3.00 s
# BACK        = 6.00 s
# LEFT        = 9.00 s
# FRONT end   = 12.00 s
#
# We analyze short windows around these positions.
# ------------------------------------------------------------

print(
    "\n[6/8] Analyzing cardinal regions..."
)


CARDINAL_WINDOW_SECONDS = 0.40

half_window_samples = int(
    SAMPLE_RATE
    * CARDINAL_WINDOW_SECONDS
    / 2.0
)


def extract_region(
    center_seconds,
    allow_edge=False,
):

    center_sample = int(
        center_seconds
        * SAMPLE_RATE
    )

    if allow_edge and center_seconds <= 0.0:

        start = 0

        end = min(
            half_window_samples * 2,
            sample_count,
        )

    elif (
        allow_edge
        and center_seconds
        >= DURATION_SECONDS
    ):

        start = max(
            0,
            sample_count
            - half_window_samples * 2,
        )

        end = sample_count

    else:

        start = max(
            0,
            center_sample
            - half_window_samples,
        )

        end = min(
            sample_count,
            center_sample
            + half_window_samples,
        )

    return (
        left[start:end],
        right[start:end],
        start,
        end,
    )


cardinal_points = [
    {
        "name": "front_start",
        "angle": 0.0,
        "time": 0.0,
        "edge": True,
    },
    {
        "name": "right",
        "angle": 90.0,
        "time": DURATION_SECONDS * 0.25,
        "edge": False,
    },
    {
        "name": "back",
        "angle": 180.0,
        "time": DURATION_SECONDS * 0.50,
        "edge": False,
    },
    {
        "name": "left",
        "angle": 270.0,
        "time": DURATION_SECONDS * 0.75,
        "edge": False,
    },
    {
        "name": "front_end",
        "angle": 360.0,
        "time": DURATION_SECONDS,
        "edge": True,
    },
]


cardinal_results = {}


print()

print(
    f"{'POSITION':<14}"
    f"{'TIME':>8}"
    f"{'L RMS':>14}"
    f"{'R RMS':>14}"
    f"{'ILD dB':>12}"
)


print("-" * 62)


for point in cardinal_points:

    (
        region_left,
        region_right,
        region_start,
        region_end,
    ) = extract_region(
        point["time"],
        point["edge"],
    )


    metrics = ild_db(
        region_left,
        region_right,
    )


    cardinal_results[
        point["name"]
    ] = {
        "orbit_degrees": (
            point["angle"]
        ),
        "center_time_seconds": (
            point["time"]
        ),
        "start_sample": (
            region_start
        ),
        "end_sample": (
            region_end
        ),
        "left_rms": (
            metrics["left_rms"]
        ),
        "right_rms": (
            metrics["right_rms"]
        ),
        "ild_db": (
            metrics["ild_db"]
        ),
    }


    print(
        f"{point['name'].upper():<14}"
        f"{point['time']:>7.2f}s"
        f"{metrics['left_rms']:>14.8f}"
        f"{metrics['right_rms']:>14.8f}"
        f"{metrics['ild_db']:>+12.4f}"
    )


# ------------------------------------------------------------
# Expected objective spatial signature:
#
# RIGHT:
#   R > L
#   ILD < 0
#
# LEFT:
#   L > R
#   ILD > 0
#
# FRONT/BACK:
#   no strict equality requirement because T001-D already
#   showed small asymmetries and different HRTF responses.
# ------------------------------------------------------------

right_valid = (
    cardinal_results[
        "right"
    ][
        "ild_db"
    ] < 0.0
)


left_valid = (
    cardinal_results[
        "left"
    ][
        "ild_db"
    ] > 0.0
)


if not right_valid:

    raise RuntimeError(
        "FAIL: +90° region does not favor "
        "the RIGHT channel."
    )


if not left_valid:

    raise RuntimeError(
        "FAIL: 270°/-90° region does not favor "
        "the LEFT channel."
    )


print(
    "\n+90° favors RIGHT:  PASS"
)

print(
    "270° favors LEFT:   PASS"
)


# ------------------------------------------------------------
# 7. Write evidence
# ------------------------------------------------------------

print(
    "\n[7/8] Writing WAV and JSON evidence..."
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
    "test_id": "T001-F",
    "test_name": (
        "360-Degree Spatial Orbit"
    ),
    "status": "PASS",
    "sample_rate_hz": (
        SAMPLE_RATE
    ),
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
        "name": (
            plugin.name
        ),
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
            "orbit_360"
        ),
        "direction": (
            "front_right_back_left_front"
        ),
        "start_orbit_degrees": (
            START_ORBIT_DEGREES
        ),
        "end_orbit_degrees": (
            END_ORBIT_DEGREES
        ),
        "coordinate_system": (
            "polar"
        ),
        "elevation_degrees": (
            0.0
        ),
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
    },
    "cardinal_regions": (
        cardinal_results
    ),
    "validation": {
        "right_region_favors_right": (
            right_valid
        ),
        "left_region_favors_left": (
            left_valid
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
    f"WAV:     "
    f"{OUTPUT_FILE.resolve()}"
)

print(
    f"JSON:    "
    f"{JSON_FILE.resolve()}"
)

print(
    f"SHA256:  "
    f"{wav_hash}"
)


# ------------------------------------------------------------
# 8. Final result
# ------------------------------------------------------------

print(
    "\n[8/8] Final validation..."
)


if overall_peak >= 1.0:

    print(
        "WARNING: output reached "
        "digital full scale."
    )

else:

    print(
        "Clipping check:       PASS"
    )


print(
    "Numerical integrity:   PASS"
)

print(
    "Right cardinal point:  PASS"
)

print(
    "Left cardinal point:   PASS"
)

print(
    "360 trajectory render: PASS"
)


print(
    "\n" + "=" * 78
)

print(
    "T001-F RESULT: PASS"
)

print(
    "=" * 78
)


print(
    "\nEvidence files:"
)

print(
    f"  {OUTPUT_FILE.resolve()}"
)

print(
    f"  {JSON_FILE.resolve()}"
)


print(
    "\nPERCEPTUAL VALIDATION"
)

print(
    "Listen with HEADPHONES."
)

print(
    "\nExpected sequence:"
)

print(
    "FRONT -> RIGHT -> BACK -> LEFT -> FRONT"
)

print(
    "\nApproximate times:"
)

print(
    "  0.0 s  = FRONT"
)

print(
    "  3.0 s  = RIGHT"
)

print(
    "  6.0 s  = BACK"
)

print(
    "  9.0 s  = LEFT"
)

print(
    " 12.0 s  = FRONT"
)

print(
    "\nReport:"
)

print(
    "1. whether you perceive a complete orbit,"
)

print(
    "2. whether the movement is continuous,"
)

print(
    "3. whether RIGHT and LEFT occur correctly,"
)

print(
    "4. whether FRONT/BACK are distinguishable,"
)

print(
    "5. whether there is any audible jump near 180°."
)
