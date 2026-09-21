from pathlib import Path
import json
import hashlib

import numpy as np

from pedalboard import load_plugin
from pedalboard.io import AudioFile


# ============================================================
# LAISE — T001-D
# Cardinal Spatial Positions Diagnostic Test
#
# Objective:
# Validate whether different azimuth commands sent by LAISE
# produce measurably and perceptually different spatial
# renders through dearVR PRO 2.
#
# Positions:
#   FRONT  =    0°
#   RIGHT  =  +90°
#   BACK   = +180°
#   LEFT   =  -90°
#
# IMPORTANT:
# This test does NOT yet canonize the raw-value mapping.
# It tests the mapping inferred from T001-B.
# ============================================================


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

PLUGIN_PATH = Path(
    r"C:\Program Files\Common Files\VST3\dearVR PRO 2.vst3"
    r"\Contents\x86_64-win\dearVR PRO 2.vst3"
)

OUTPUT_DIR = Path("evidence") / "T001" / "T001-D"

SAMPLE_RATE = 48_000
DURATION_SECONDS = 5.0

# Deterministic seed.
RANDOM_SEED = 20260920

# Conservative output level.
AMPLITUDE = 0.12


# ------------------------------------------------------------
# Cardinal positions
#
# Inferred mapping from T001-B:
#
# -180° -> 0.00
#  -90° -> 0.25
#    0° -> 0.50
#  +90° -> 0.75
# +180° -> 1.00
# ------------------------------------------------------------

POSITIONS = [
    {
        "name": "front",
        "angle_degrees": 0.0,
        "azimuth_raw": 0.50,
        "filename": "t001d_front_000.wav",
    },
    {
        "name": "right",
        "angle_degrees": 90.0,
        "azimuth_raw": 0.75,
        "filename": "t001d_right_090.wav",
    },
    {
        "name": "back",
        "angle_degrees": 180.0,
        "azimuth_raw": 1.00,
        "filename": "t001d_back_180.wav",
    },
    {
        "name": "left",
        "angle_degrees": -90.0,
        "azimuth_raw": 0.25,
        "filename": "t001d_left_minus090.wav",
    },
]


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
            block = file.read(1024 * 1024)

            if not block:
                break

            digest.update(block)

    return digest.hexdigest()


def safe_correlation(left, right):
    """
    Calculate Pearson correlation between channels.

    +1 = highly similar
     0 = weak linear relationship
    -1 = inverse relationship
    """

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


# ------------------------------------------------------------
# Header
# ------------------------------------------------------------

print("=" * 78)
print("LAISE — T001-D")
print("dearVR PRO 2 — Cardinal Spatial Positions")
print("=" * 78)


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
# 1. Generate deterministic broadband test signal
# ------------------------------------------------------------

print("\n[1/6] Generating deterministic broadband source...")


sample_count = int(
    SAMPLE_RATE * DURATION_SECONDS
)

rng = np.random.default_rng(
    RANDOM_SEED
)


# ------------------------------------------------------------
# Broadband diagnostic signal
#
# White noise is intentionally used here instead of the
# previous pure 440 Hz sine.
#
# HRTF spatialization relies strongly on frequency-dependent
# cues. A broadband source gives the renderer substantially
# more spectral information than a single sine wave.
#
# Fade-in/out prevents abrupt edges.
# ------------------------------------------------------------

signal = rng.standard_normal(
    sample_count
).astype(np.float32)


# Normalize.
signal /= np.max(
    np.abs(signal)
)


signal *= AMPLITUDE


# ------------------------------------------------------------
# Fade in / fade out
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
# dearVR exposes a 2-in / 2-out main bus.
#
# We therefore duplicate the deterministic mono source
# identically into L and R.
# ------------------------------------------------------------

stereo_input = np.stack(
    [
        signal,
        signal,
    ],
    axis=0,
).astype(np.float32)


print(f"Sample rate:     {SAMPLE_RATE} Hz")
print(f"Duration:        {DURATION_SECONDS:.2f} s")
print(f"Samples:         {sample_count}")
print(f"Random seed:     {RANDOM_SEED}")
print(f"Amplitude:       {AMPLITUDE}")
print("Source:          deterministic broadband noise")
print("VST input:       dual-mono")
print(f"Input shape:     {stereo_input.shape}")
print(f"Input dtype:     {stereo_input.dtype}")


# ------------------------------------------------------------
# 2. Load plugin metadata
# ------------------------------------------------------------

print("\n[2/6] Loading dearVR PRO 2...")


reference_plugin = load_plugin(
    str(PLUGIN_PATH)
)


plugin_metadata = {
    "name": reference_plugin.name,
    "manufacturer": reference_plugin.manufacturer_name,
    "identifier": reference_plugin.identifier,
    "latency_samples": int(
        reference_plugin.reported_latency_samples
    ),
}


latency_ms = (
    reference_plugin.reported_latency_samples
    / SAMPLE_RATE
    * 1000.0
)


print(
    f"Plugin:           "
    f"{reference_plugin.name}"
)

print(
    f"Manufacturer:     "
    f"{reference_plugin.manufacturer_name}"
)

print(
    f"Identifier:       "
    f"{reference_plugin.identifier}"
)

print(
    f"Latency:          "
    f"{reference_plugin.reported_latency_samples} samples"
)

print(
    f"Latency:          "
    f"{latency_ms:.3f} ms"
)


# ------------------------------------------------------------
# 3. Render cardinal positions
# ------------------------------------------------------------

print("\n[3/6] Rendering cardinal positions...")


results = []


for position in POSITIONS:

    print("\n" + "-" * 78)

    print(
        f"Rendering: "
        f"{position['name'].upper()}"
    )

    print(
        f"Target angle: "
        f"{position['angle_degrees']}°"
    )

    print(
        f"Azimuth raw: "
        f"{position['azimuth_raw']}"
    )


    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Load a fresh plugin instance for every position.
    #
    # This prevents internal DSP state from one render from
    # contaminating another position.
    # --------------------------------------------------------

    plugin = load_plugin(
        str(PLUGIN_PATH)
    )


    # Polar coordinate system.
    plugin.parameters[
        "coordinate_system"
    ].raw_value = 1.0


    # Cardinal azimuth.
    plugin.parameters[
        "azimuth"
    ].raw_value = position[
        "azimuth_raw"
    ]


    # Zero elevation.
    plugin.parameters[
        "elevation"
    ].raw_value = 0.5


    # Preserve current/default distance.
    distance_raw = float(
        plugin.parameters[
            "distance"
        ].raw_value
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


    # --------------------------------------------------------
    # Structural validation
    # --------------------------------------------------------

    if processed.ndim != 2:
        raise RuntimeError(
            f"{position['name']}: "
            f"unexpected output shape "
            f"{processed.shape}"
        )


    if processed.shape[0] != 2:
        raise RuntimeError(
            f"{position['name']}: "
            "expected stereo output."
        )


    if not np.all(
        np.isfinite(processed)
    ):
        raise RuntimeError(
            f"{position['name']}: "
            "NaN or Infinity detected."
        )


    output_peak = peak(
        processed
    )


    if output_peak <= 0.0:
        raise RuntimeError(
            f"{position['name']}: "
            "silent output."
        )


    left = processed[0]
    right = processed[1]


    # --------------------------------------------------------
    # Measurements
    # --------------------------------------------------------

    left_rms = rms(left)
    right_rms = rms(right)

    left_peak = peak(left)
    right_peak = peak(right)

    lr_difference = float(
        np.mean(
            np.abs(
                left - right
            )
        )
    )

    correlation = safe_correlation(
        left,
        right,
    )


    # Interaural level difference.
    #
    # Positive value:
    # left channel has greater RMS energy.
    #
    # Negative value:
    # right channel has greater RMS energy.
    # --------------------------------------------------------

    epsilon = 1e-12

    ild_db = float(
        20.0
        * np.log10(
            (left_rms + epsilon)
            / (right_rms + epsilon)
        )
    )


    # --------------------------------------------------------
    # Compare with input
    # --------------------------------------------------------

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

    output_input_difference = float(
        np.mean(
            np.abs(
                output_common
                - input_common
            )
        )
    )


    # --------------------------------------------------------
    # Write WAV
    # --------------------------------------------------------

    output_file = (
        OUTPUT_DIR
        / position["filename"]
    )


    with AudioFile(
        str(output_file),
        "w",
        SAMPLE_RATE,
        processed.shape[0],
    ) as audio_file:

        audio_file.write(
            processed
        )


    file_hash = sha256_file(
        output_file
    )


    result = {
        "position": position["name"],
        "angle_degrees": position[
            "angle_degrees"
        ],
        "azimuth_raw": position[
            "azimuth_raw"
        ],
        "elevation_raw": 0.5,
        "distance_raw": distance_raw,
        "output_file": str(
            output_file.resolve()
        ),
        "output_shape": list(
            processed.shape
        ),
        "peak_overall": output_peak,
        "left_peak": left_peak,
        "right_peak": right_peak,
        "left_rms": left_rms,
        "right_rms": right_rms,
        "ild_db_left_over_right": ild_db,
        "mean_abs_left_right_difference": (
            lr_difference
        ),
        "left_right_correlation": (
            correlation
        ),
        "mean_abs_output_input_difference": (
            output_input_difference
        ),
        "sha256": file_hash,
    }


    results.append(
        result
    )


    print(
        f"L RMS:             "
        f"{left_rms:.8f}"
    )

    print(
        f"R RMS:             "
        f"{right_rms:.8f}"
    )

    print(
        f"L Peak:            "
        f"{left_peak:.8f}"
    )

    print(
        f"R Peak:            "
        f"{right_peak:.8f}"
    )

    print(
        f"ILD L/R:           "
        f"{ild_db:+.4f} dB"
    )

    print(
        f"Mean |L-R|:        "
        f"{lr_difference:.10f}"
    )

    print(
        f"L/R correlation:   "
        f"{correlation:.8f}"
    )

    print(
        f"Mean |OUT-IN|:     "
        f"{output_input_difference:.10f}"
    )

    print(
        f"WAV:               "
        f"{output_file.resolve()}"
    )


# ------------------------------------------------------------
# 4. Comparative analysis
# ------------------------------------------------------------

print("\n[4/6] Comparing cardinal renders...")


print("\n")
print(
    f"{'POSITION':<10}"
    f"{'ANGLE':>10}"
    f"{'L RMS':>14}"
    f"{'R RMS':>14}"
    f"{'ILD dB':>12}"
    f"{'CORR':>12}"
)

print("-" * 72)


for result in results:

    print(
        f"{result['position'].upper():<10}"
        f"{result['angle_degrees']:>9.0f}°"
        f"{result['left_rms']:>14.8f}"
        f"{result['right_rms']:>14.8f}"
        f"{result['ild_db_left_over_right']:>+12.4f}"
        f"{result['left_right_correlation']:>12.6f}"
    )


# ------------------------------------------------------------
# Check whether cardinal renders are numerically distinct.
# ------------------------------------------------------------

print("\nPairwise render differences:")


render_cache = {}


for position in POSITIONS:

    wav_path = (
        OUTPUT_DIR
        / position["filename"]
    )

    with AudioFile(
        str(wav_path),
        "r",
    ) as audio_file:

        audio = audio_file.read(
            audio_file.frames
        )

    render_cache[
        position["name"]
    ] = np.asarray(
        audio,
        dtype=np.float32,
    )


names = [
    position["name"]
    for position in POSITIONS
]


pairwise_differences = {}


for i in range(
    len(names)
):

    for j in range(
        i + 1,
        len(names),
    ):

        name_a = names[i]
        name_b = names[j]

        audio_a = render_cache[
            name_a
        ]

        audio_b = render_cache[
            name_b
        ]

        common_samples = min(
            audio_a.shape[1],
            audio_b.shape[1],
        )

        difference = float(
            np.mean(
                np.abs(
                    audio_a[
                        :,
                        :common_samples,
                    ]
                    -
                    audio_b[
                        :,
                        :common_samples,
                    ]
                )
            )
        )

        key = (
            f"{name_a}_vs_{name_b}"
        )

        pairwise_differences[
            key
        ] = difference

        print(
            f"{name_a.upper():>6}"
            f" vs "
            f"{name_b.upper():<6}"
            f" = "
            f"{difference:.10f}"
        )


# ------------------------------------------------------------
# 5. Write JSON evidence
# ------------------------------------------------------------

print("\n[5/6] Writing diagnostic evidence...")


evidence = {
    "test_id": "T001-D",
    "test_name": (
        "Cardinal Spatial Positions"
    ),
    "status": "PASS",
    "sample_rate_hz": SAMPLE_RATE,
    "duration_seconds": (
        DURATION_SECONDS
    ),
    "source": {
        "type": (
            "deterministic broadband noise"
        ),
        "random_seed": (
            RANDOM_SEED
        ),
        "amplitude": AMPLITUDE,
        "input_layout": (
            "dual-mono stereo"
        ),
    },
    "plugin": plugin_metadata,
    "mapping_status": (
        "experimental_not_canonical"
    ),
    "results": results,
    "pairwise_differences": (
        pairwise_differences
    ),
}


json_file = (
    OUTPUT_DIR
    / "t001d_cardinal_results.json"
)


with open(
    json_file,
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
    f"JSON evidence: "
    f"{json_file.resolve()}"
)


# ------------------------------------------------------------
# 6. Final validation
# ------------------------------------------------------------

print("\n[6/6] Final validation...")


all_distinct = all(
    value > 0.0
    for value
    in pairwise_differences.values()
)


if not all_distinct:
    raise RuntimeError(
        "FAIL: one or more cardinal renders "
        "are numerically identical."
    )


max_peak = max(
    result["peak_overall"]
    for result in results
)


if max_peak >= 1.0:

    print(
        "WARNING: at least one render "
        "reached digital full scale."
    )

else:

    print(
        "Clipping check:      PASS"
    )


print(
    "Distinct renders:     PASS"
)

print(
    f"Maximum peak:         "
    f"{max_peak:.8f}"
)


print("\n" + "=" * 78)

print(
    "T001-D RESULT: PASS"
)

print("=" * 78)


print("\nGenerated files:")


for result in results:

    print(
        f"  {result['output_file']}"
    )


print(
    f"  {json_file.resolve()}"
)


print(
    "\nIMPORTANT:"
)

print(
    "Listen to the four WAV files with headphones."
)

print(
    "Do not force a front/back interpretation."
)

print(
    "Report only what you actually perceive:"
)

print(
    "LEFT / RIGHT / CENTER / FRONT / BACK / "
    "INSIDE HEAD / OUTSIDE HEAD / UNCERTAIN."
)
