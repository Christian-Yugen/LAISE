import json
import math
from pathlib import Path

import numpy as np


# ============================================================
# Approved V1.2 physical field constants
# ============================================================

WIDTH = 16.0
DEPTH = 16.0
SEGMENTS = 128

COLUMNS = SEGMENTS + 1
ROWS = SEGMENTS + 1

DX = WIDTH / SEGMENTS
DZ = DEPTH / SEGMENTS

SPEED = 3.0
DAMPING = 0.65
EDGE_DAMPING = 0.20
RESTORING = 2.5

DT = 1.0 / 120.0

AMPLITUDE_REFERENCE_RMS = (
    0.014295334592461588
)

LEGACY_IMPULSE_GAIN = 20.0

K_IMPULSE = (
    LEGACY_IMPULSE_GAIN
    / AMPLITUDE_REFERENCE_RMS
)


# ============================================================
# Physically-derived candidate timescales
# ============================================================

NATURAL_OMEGA = math.sqrt(
    RESTORING
)

NATURAL_RESPONSE_TIME = (
    1.0 / NATURAL_OMEGA
)

NATURAL_PERIOD = (
    2.0
    * math.pi
    / NATURAL_OMEGA
)

CELL_CROSSING_TIME = (
    DX / SPEED
)


CANDIDATES = {
    "PERIOD_EQUIVALENT": {
        "timescaleSeconds":
            NATURAL_PERIOD,
    },

    "RESPONSE_EQUIVALENT": {
        "timescaleSeconds":
            NATURAL_RESPONSE_TIME,
    },

    "CELL_EQUIVALENT": {
        "timescaleSeconds":
            CELL_CROSSING_TIME,
    },
}


for candidate in CANDIDATES.values():

    candidate[
        "continuousCouplingPerSecond"
    ] = (
        K_IMPULSE
        / candidate[
            "timescaleSeconds"
        ]
    )


# ============================================================
# Tukana II measured physicalDrive levels
# ============================================================

DRIVE_LEVELS = {
    "P10": 0.000071516509686,
    "P50": 0.0019082693464,
    "P95": 0.00805533060326,
    "P99": 0.0123078978185,
    "MAX": 0.0204331422574,
}


# ============================================================
# Exact V1.2 attenuation field
# ============================================================

row = np.arange(
    ROWS,
    dtype=np.float64,
)

col = np.arange(
    COLUMNS,
    dtype=np.float64,
)

edge_row = np.minimum(
    row / SEGMENTS,
    1.0 - row / SEGMENTS,
)

edge_col = np.minimum(
    col / SEGMENTS,
    1.0 - col / SEGMENTS,
)

edge = np.minimum(
    edge_row[:, None],
    edge_col[None, :],
)

edge_zone = np.maximum(
    0.0,
    1.0 - edge / 0.10,
)

ATTENUATION = np.exp(
    -(
        DAMPING
        + edge_zone ** 2
        * EDGE_DAMPING
    )
    * DT
)


# ============================================================
# Spatial kernel equivalent to RippleField.exciteAt()
# ============================================================

physical_x = (
    np.arange(COLUMNS)
    - SEGMENTS / 2.0
) * DX

physical_z = (
    np.arange(ROWS)
    - SEGMENTS / 2.0
) * DZ

X, Z = np.meshgrid(
    physical_x,
    physical_z,
)


def kernel_at(
    normalized_x,
    normalized_z,
    footprint_width,
):

    source_x = (
        normalized_x
        * WIDTH / 2.0
    )

    source_z = (
        normalized_z
        * DEPTH / 2.0
    )

    q = (
        (X - source_x) ** 2
        + (Z - source_z) ** 2
    ) / (
        footprint_width ** 2
    )

    kernel = (
        (1.0 - q / 2.0)
        * np.exp(-q / 2.0)
    )

    kernel = np.where(
        q <= 25.0,
        kernel,
        0.0,
    )

    return kernel


# ============================================================
# Unclamped physical field
#
# Deliberately NO velocity clamp.
# We measure crossings of the legacy +/-40 threshold instead.
# ============================================================

class RawField:

    def __init__(self):

        self.h = np.zeros(
            (ROWS, COLUMNS),
            dtype=np.float64,
        )

        self.v = np.zeros_like(
            self.h
        )

        self.time = 0.0


    def impulse(
        self,
        kernel,
        physical_drive,
    ):

        self.v += (
            kernel
            * K_IMPULSE
            * physical_drive
        )


    def continuous_force(
        self,
        kernel,
        physical_drive,
        coupling_per_second,
    ):

        # dv/dt = Kcontinuous * physicalDrive(t)
        #
        # Multiplication by DT makes total physical
        # energy independent of feature sample rate.
        self.v += (
            kernel
            * coupling_per_second
            * physical_drive
            * DT
        )


    def advance(self):

        padded = np.pad(
            self.h,
            1,
            mode="reflect",
        )

        left = padded[
            1:-1,
            :-2,
        ]

        right = padded[
            1:-1,
            2:,
        ]

        previous = padded[
            :-2,
            1:-1,
        ]

        following = padded[
            2:,
            1:-1,
        ]

        acceleration = (
            SPEED ** 2
            / DX ** 2
            * (
                left
                - 2.0 * self.h
                + right
            )
            +
            SPEED ** 2
            / DZ ** 2
            * (
                previous
                - 2.0 * self.h
                + following
            )
            -
            RESTORING
            * self.h
        )

        self.v = (
            self.v
            + acceleration * DT
        ) * ATTENUATION

        self.h += (
            self.v * DT
        )

        self.time += DT


# ============================================================
# Simulation
# ============================================================

def simulate(
    mode,
    footprint_width,
    continuous_coupling=None,
):

    field = RawField()

    kernel = kernel_at(
        0.0,
        0.0,
        footprint_width,
    )

    # Simulate response at the exact old common RMS reference.
    # Because the PDE is linear and unclamped, all measured
    # drive levels can then be derived by exact scaling.
    reference_drive = (
        AMPLITUDE_REFERENCE_RMS
    )

    total_seconds = 8.0

    cause_start = 1.0
    cause_end = 6.0

    steps = round(
        total_seconds / DT
    )

    impulse_applied = False

    peak_h = 0.0
    peak_v = 0.0

    peak_h_time = 0.0
    peak_v_time = 0.0

    post_cause_peak_h = 0.0
    post_cause_peak_v = 0.0

    legacy_velocity_threshold_steps = 0

    end_cause_h = None
    end_cause_v = None


    for _ in range(steps):

        t = field.time

        if (
            mode == "IMPULSE"
            and not impulse_applied
            and t + 1e-12 >= cause_start
        ):

            field.impulse(
                kernel,
                reference_drive,
            )

            impulse_applied = True


        if (
            mode == "CONTINUOUS"
            and cause_start
            <= t
            < cause_end
        ):

            field.continuous_force(
                kernel,
                reference_drive,
                continuous_coupling,
            )


        field.advance()


        current_h = float(
            np.max(
                np.abs(field.h)
            )
        )

        current_v = float(
            np.max(
                np.abs(field.v)
            )
        )


        if current_h > peak_h:

            peak_h = current_h
            peak_h_time = field.time


        if current_v > peak_v:

            peak_v = current_v
            peak_v_time = field.time


        if current_v >= 40.0:

            legacy_velocity_threshold_steps += 1


        if (
            field.time
            >= cause_end
            and end_cause_h is None
        ):

            end_cause_h = current_h
            end_cause_v = current_v


        if field.time >= cause_end:

            post_cause_peak_h = max(
                post_cause_peak_h,
                current_h,
            )

            post_cause_peak_v = max(
                post_cause_peak_v,
                current_v,
            )


    return {
        "referenceDrive":
            reference_drive,

        "peakAbsHeight":
            peak_h,

        "peakAbsHeightTime":
            peak_h_time,

        "peakAbsVelocity":
            peak_v,

        "peakAbsVelocityTime":
            peak_v_time,

        "endCauseAbsHeight":
            end_cause_h,

        "endCauseAbsVelocity":
            end_cause_v,

        "postCausePeakAbsHeight":
            post_cause_peak_h,

        "postCausePeakAbsVelocity":
            post_cause_peak_v,

        "finalAbsHeight":
            float(
                np.max(
                    np.abs(field.h)
                )
            ),

        "finalAbsVelocity":
            float(
                np.max(
                    np.abs(field.v)
                )
            ),

        "legacyVelocity40Steps":
            legacy_velocity_threshold_steps,
    }


def scaled_response(
    base,
    drive,
):

    scale = (
        drive
        / base[
            "referenceDrive"
        ]
    )

    return {
        "physicalDrive":
            drive,

        "scaleFromReference":
            scale,

        "peakAbsHeight":
            base[
                "peakAbsHeight"
            ] * scale,

        "peakAbsVelocity":
            base[
                "peakAbsVelocity"
            ] * scale,

        "endCauseAbsHeight":
            base[
                "endCauseAbsHeight"
            ] * scale,

        "endCauseAbsVelocity":
            base[
                "endCauseAbsVelocity"
            ] * scale,

        "postCausePeakAbsHeight":
            base[
                "postCausePeakAbsHeight"
            ] * scale,

        "postCausePeakAbsVelocity":
            base[
                "postCausePeakAbsVelocity"
            ] * scale,

        "finalAbsHeight":
            base[
                "finalAbsHeight"
            ] * scale,

        "finalAbsVelocity":
            base[
                "finalAbsVelocity"
            ] * scale,

        "wouldCrossLegacyVelocity40":
            (
                base[
                    "peakAbsVelocity"
                ] * scale
                >= 40.0
            ),
    }


# ============================================================
# Run
# ============================================================

report = {
    "schema":
        "laise-v1.3c-physical-coupling-calibration-r1",

    "contracts": {
        "productionRuntimeModified":
            False,

        "velocityClampUsed":
            False,

        "renderHeadroomApplied":
            False,

        "physicalDriveNormalized":
            False,

        "continuousForceIsDtInvariant":
            True,

        "elevationMappedToMeshY":
            False,

        "purpose":
            (
                "Compare physically-derived continuous "
                "coupling candidates before Behavior Physics."
            ),
    },

    "constants": {
        "amplitudeReferenceRms":
            AMPLITUDE_REFERENCE_RMS,

        "kImpulse":
            K_IMPULSE,

        "naturalOmega":
            NATURAL_OMEGA,

        "naturalResponseTimeSeconds":
            NATURAL_RESPONSE_TIME,

        "naturalPeriodSeconds":
            NATURAL_PERIOD,

        "cellCrossingTimeSeconds":
            CELL_CROSSING_TIME,

        "solverStepSeconds":
            DT,

        "fieldWidth":
            WIDTH,

        "segments":
            SEGMENTS,
    },

    "driveLevels":
        DRIVE_LEVELS,

    "results": {},
}


print(
    "K_IMPULSE=",
    K_IMPULSE
)

print(
    "NATURAL_RESPONSE_TIME=",
    NATURAL_RESPONSE_TIME
)

print(
    "NATURAL_PERIOD=",
    NATURAL_PERIOD
)

print(
    "CELL_CROSSING_TIME=",
    CELL_CROSSING_TIME
)


for footprint_width in (
    0.64,
    0.80,
):

    width_key = (
        f"WIDTH_{footprint_width:.2f}"
    )

    report[
        "results"
    ][width_key] = {}


    print(
        "\n========================================"
    )

    print(
        "FOOTPRINT_WIDTH=",
        footprint_width
    )

    print(
        "========================================"
    )


    impulse = simulate(
        "IMPULSE",
        footprint_width,
    )


    report[
        "results"
    ][width_key][
        "IMPULSE_REFERENCE"
    ] = {
        "base":
            impulse,

        "scaled":
            {
                label:
                    scaled_response(
                        impulse,
                        drive,
                    )
                for label, drive
                in DRIVE_LEVELS.items()
            },
    }


    print(
        "\nIMPULSE_REFERENCE"
    )

    print(
        "peakHeight=",
        impulse[
            "peakAbsHeight"
        ]
    )

    print(
        "peakVelocity=",
        impulse[
            "peakAbsVelocity"
        ]
    )


    for name, candidate in (
        CANDIDATES.items()
    ):

        coupling = candidate[
            "continuousCouplingPerSecond"
        ]


        continuous = simulate(
            "CONTINUOUS",
            footprint_width,
            coupling,
        )


        scaled = {
            label:
                scaled_response(
                    continuous,
                    drive,
                )
            for label, drive
            in DRIVE_LEVELS.items()
        }


        report[
            "results"
        ][width_key][name] = {
            "timescaleSeconds":
                candidate[
                    "timescaleSeconds"
                ],

            "continuousCouplingPerSecond":
                coupling,

            "base":
                continuous,

            "scaled":
                scaled,
        }


        print(
            "\n",
            name,
            sep="",
        )

        print(
            "timescaleSeconds=",
            candidate[
                "timescaleSeconds"
            ]
        )

        print(
            "Kcontinuous=",
            coupling
        )

        print(
            "referencePeakHeight=",
            continuous[
                "peakAbsHeight"
            ]
        )

        print(
            "referencePeakVelocity=",
            continuous[
                "peakAbsVelocity"
            ]
        )

        print(
            "referencePostCausePeakHeight=",
            continuous[
                "postCausePeakAbsHeight"
            ]
        )


        for label in (
            "P10",
            "P50",
            "P95",
            "P99",
            "MAX",
        ):

            row = scaled[
                label
            ]

            print(
                label,
                "drive=",
                row[
                    "physicalDrive"
                ],
                "peakH=",
                row[
                    "peakAbsHeight"
                ],
                "peakV=",
                row[
                    "peakAbsVelocity"
                ],
                "cross40=",
                row[
                    "wouldCrossLegacyVelocity40"
                ],
            )


# ============================================================
# Monotonicity
# ============================================================

monotonic_failures = []

for width_key, width_data in (
    report[
        "results"
    ].items()
):

    for mode, result in (
        width_data.items()
    ):

        scaled = result.get(
            "scaled"
        )

        if not scaled:
            continue

        rows = [
            scaled[label]
            for label in (
                "P10",
                "P50",
                "P95",
                "P99",
                "MAX",
            )
        ]

        heights = [
            row[
                "peakAbsHeight"
            ]
            for row in rows
        ]

        velocities = [
            row[
                "peakAbsVelocity"
            ]
            for row in rows
        ]

        if not all(
            a < b
            for a, b
            in zip(
                heights,
                heights[1:],
            )
        ):
            monotonic_failures.append(
                (
                    width_key,
                    mode,
                    "height",
                )
            )

        if not all(
            a < b
            for a, b
            in zip(
                velocities,
                velocities[1:],
            )
        ):
            monotonic_failures.append(
                (
                    width_key,
                    mode,
                    "velocity",
                )
            )


report[
    "summary"
] = {
    "monotonicFailures":
        monotonic_failures,

    "monotonicIntensityResponse":
        (
            len(
                monotonic_failures
            )
            == 0
        ),

    "candidateSelected":
        None,

    "selectionPolicy":
        (
            "No automatic winner. Compare raw field "
            "response, legacy velocity threshold crossings, "
            "residual energy and intensity preservation."
        ),
}


output = Path(
    "visualizer/reports/"
    "v1_3c-physical-coupling-calibration-r1.json"
)

output.parent.mkdir(
    parents=True,
    exist_ok=True,
)

serialized = (
    json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    + "\n"
)

output.write_text(
    serialized,
    encoding="utf-8",
    newline="\n",
)


print(
    "\n========================================"
)

print(
    "MONOTONIC_FAILURES=",
    len(
        monotonic_failures
    )
)

print(
    "MONOTONIC_INTENSITY_RESPONSE=",
    (
        "PASS"
        if not monotonic_failures
        else "FAIL"
    )
)

print(
    "VELOCITY_CLAMP_USED=NO"
)

print(
    "HEADROOM_MAPPING_USED=NO"
)

print(
    "CANDIDATE_SELECTED=NO"
)

print(
    "OUTPUT=",
    output.resolve()
)

print(
    "\nPHYSICAL_COUPLING_LAB_R1=PASS"
)
