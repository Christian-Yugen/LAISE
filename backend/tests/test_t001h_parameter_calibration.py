"""
LAISE — T001-H
dearVR PRO 2 Parameter & Coordinate-System Calibration

Purpose
-------
Interrogate dearVR PRO 2 through Pedalboard and establish the real
normalized parameter mappings before modifying LAISE spatial geometry.

This test DOES NOT render audio.

It investigates:
- coordinate_system
- azimuth
- elevation
- distance
- x
- y
- z

For every parameter/value:
1. write raw normalized value;
2. read raw value back;
3. obtain Pedalboard's human-readable representation;
4. record available parameter values where exposed;
5. test coordinate-system state transitions.

Output
------
evidence/T001/T001-H/
    t001h_parameter_calibration_results.json
"""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import pedalboard
from pedalboard import load_plugin


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PLUGIN_PATH = Path(
    r"C:\Program Files\Common Files\VST3"
    r"\dearVR PRO 2.vst3"
    r"\Contents\x86_64-win"
    r"\dearVR PRO 2.vst3"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "evidence"
    / "T001"
    / "T001-H"
)

RESULTS_PATH = (
    OUTPUT_DIR
    / "t001h_parameter_calibration_results.json"
)


# ============================================================
# TEST VALUES
# ============================================================

TEST_VALUES = {
    "coordinate_system": [
        0.0,
        0.5,
        1.0,
    ],

    "azimuth": [
        0.0,
        0.125,
        0.25,
        0.375,
        0.5,
        0.625,
        0.75,
        0.875,
        1.0,
    ],

    "elevation": [
        0.0,
        0.125,
        0.25,
        0.375,
        0.5,
        0.625,
        0.75,
        0.875,
        1.0,
    ],

    "distance": [
        0.0,
        0.05,
        0.0969899744,
        0.125,
        0.25,
        0.5,
        0.75,
        1.0,
    ],

    "x": [
        0.0,
        0.25,
        0.5,
        0.75,
        1.0,
    ],

    "y": [
        0.0,
        0.25,
        0.5,
        0.75,
        1.0,
    ],

    "z": [
        0.0,
        0.25,
        0.5,
        0.75,
        1.0,
    ],
}


# ============================================================
# HELPERS
# ============================================================

def fail(message: str) -> None:
    print()
    print("FAIL:", message)
    print()
    print("T001-H RESULT: FAIL")
    raise SystemExit(1)


def safe_string(value) -> str | None:
    try:
        return str(value)
    except Exception:
        return None


def get_parameter_text(parameter) -> str | None:
    """
    Pedalboard versions may expose the displayed/human-readable
    parameter value through string conversion rather than a
    dedicated API.

    We therefore record all representations available to us
    without assuming which one is authoritative.
    """

    try:
        return str(parameter)
    except Exception:
        return None


def get_valid_values(parameter):
    try:
        values = parameter.valid_values

        if values is None:
            return None

        return [
            str(value)
            for value in values
        ]

    except Exception:
        return None


def snapshot(plugin, names):
    result = {}

    for name in names:
        parameter = plugin.parameters[name]

        result[name] = {
            "raw_value":
                float(parameter.raw_value),

            "representation":
                get_parameter_text(parameter),

            "valid_values":
                get_valid_values(parameter),
        }

    return result


# ============================================================
# HEADER
# ============================================================

print()
print("=" * 78)
print("LAISE — T001-H")
print("dearVR PRO 2 Parameter & Coordinate-System Calibration")
print("=" * 78)
print()

print("Python:")
print(platform.python_version())

print()
print("Pedalboard:")
print(pedalboard.__version__)

print()
print("Plugin:")
print(PLUGIN_PATH)


# ============================================================
# PRECHECK
# ============================================================

print()
print("-" * 78)
print("PRECHECK")
print("-" * 78)

if not PLUGIN_PATH.is_file():
    fail(
        f"Plugin not found:\n{PLUGIN_PATH}"
    )

plugin = load_plugin(
    str(PLUGIN_PATH)
)

print("Plugin loaded: PASS")

print()
print("Name:")
print(plugin.name)

print()
print("Manufacturer:")
print(plugin.manufacturer_name)

print()
print("Identifier:")
print(plugin.identifier)


# ============================================================
# REQUIRED PARAMETERS
# ============================================================

required_parameters = [
    "coordinate_system",
    "azimuth",
    "elevation",
    "distance",
    "x",
    "y",
    "z",
]

missing_parameters = [
    name
    for name in required_parameters
    if name not in plugin.parameters
]

if missing_parameters:
    fail(
        "Missing parameters: "
        + ", ".join(missing_parameters)
    )

print()
print("Required spatial parameters: PASS")


# ============================================================
# DEFAULT STATE
# ============================================================

print()
print("-" * 78)
print("DEFAULT PARAMETER STATE")
print("-" * 78)

default_state = snapshot(
    plugin,
    required_parameters,
)

for name, data in default_state.items():
    print()
    print(name)

    print(
        "  raw:",
        data["raw_value"],
    )

    print(
        "  representation:",
        data["representation"],
    )

    print(
        "  valid_values:",
        data["valid_values"],
    )


# ============================================================
# PARAMETER SWEEP
# ============================================================

print()
print("-" * 78)
print("NORMALIZED PARAMETER SWEEP")
print("-" * 78)

sweep_results = {}

for parameter_name, raw_values in TEST_VALUES.items():

    print()
    print("=" * 40)
    print(parameter_name.upper())
    print("=" * 40)

    sweep_results[
        parameter_name
    ] = []

    for requested_raw in raw_values:

        # Fresh instance avoids cross-test state leakage.
        test_plugin = load_plugin(
            str(PLUGIN_PATH)
        )

        parameter = test_plugin.parameters[
            parameter_name
        ]

        before_raw = float(
            parameter.raw_value
        )

        write_error = None

        try:
            parameter.raw_value = float(
                requested_raw
            )
        except Exception as exc:
            write_error = repr(exc)

        after_raw = float(
            parameter.raw_value
        )

        representation = (
            get_parameter_text(parameter)
        )

        valid_values = (
            get_valid_values(parameter)
        )

        record = {
            "requested_raw":
                requested_raw,

            "before_raw":
                before_raw,

            "after_raw":
                after_raw,

            "delta_requested_vs_readback":
                (
                    after_raw
                    - requested_raw
                ),

            "representation":
                representation,

            "valid_values":
                valid_values,

            "write_error":
                write_error,
        }

        sweep_results[
            parameter_name
        ].append(record)

        print()
        print(
            f"requested raw: "
            f"{requested_raw:.9f}"
        )

        print(
            f"readback raw:  "
            f"{after_raw:.9f}"
        )

        print(
            "representation:",
            representation,
        )

        if write_error:
            print(
                "write error:",
                write_error,
            )


# ============================================================
# COORDINATE SYSTEM TRANSITION TEST
# ============================================================

print()
print("-" * 78)
print("COORDINATE SYSTEM TRANSITION TEST")
print("-" * 78)

transition_plugin = load_plugin(
    str(PLUGIN_PATH)
)

transition_records = []

coordinate_sequence = [
    0.0,
    1.0,
    0.0,
    1.0,
]

for requested_coordinate_raw in coordinate_sequence:

    coordinate_parameter = (
        transition_plugin.parameters[
            "coordinate_system"
        ]
    )

    coordinate_parameter.raw_value = (
        requested_coordinate_raw
    )

    state = snapshot(
        transition_plugin,
        required_parameters,
    )

    transition_records.append(
        {
            "requested_coordinate_system_raw":
                requested_coordinate_raw,

            "state":
                state,
        }
    )

    print()
    print(
        "coordinate_system requested:",
        requested_coordinate_raw,
    )

    for name in required_parameters:
        print(
            f"  {name:<20}"
            f"{state[name]['raw_value']:.9f}"
            f"    "
            f"{state[name]['representation']}"
        )


# ============================================================
# CONTROLLED POLAR STATE
# ============================================================

print()
print("-" * 78)
print("CONTROLLED POLAR-STYLE STATE")
print("-" * 78)

polar_plugin = load_plugin(
    str(PLUGIN_PATH)
)

polar_plugin.parameters[
    "coordinate_system"
].raw_value = 1.0

polar_plugin.parameters[
    "azimuth"
].raw_value = 0.5

polar_plugin.parameters[
    "elevation"
].raw_value = 0.5

polar_plugin.parameters[
    "distance"
].raw_value = 0.0969899744

controlled_polar_state = snapshot(
    polar_plugin,
    required_parameters,
)

for name in required_parameters:
    data = controlled_polar_state[name]

    print()
    print(name)
    print(
        "  raw:",
        data["raw_value"],
    )
    print(
        "  representation:",
        data["representation"],
    )


# ============================================================
# CONTROLLED CARTESIAN-STYLE STATE
# ============================================================

print()
print("-" * 78)
print("CONTROLLED CARTESIAN-STYLE STATE")
print("-" * 78)

cartesian_plugin = load_plugin(
    str(PLUGIN_PATH)
)

cartesian_plugin.parameters[
    "coordinate_system"
].raw_value = 0.0

cartesian_plugin.parameters[
    "x"
].raw_value = 0.5

cartesian_plugin.parameters[
    "y"
].raw_value = 0.5

cartesian_plugin.parameters[
    "z"
].raw_value = 0.5

controlled_cartesian_state = snapshot(
    cartesian_plugin,
    required_parameters,
)

for name in required_parameters:
    data = controlled_cartesian_state[name]

    print()
    print(name)
    print(
        "  raw:",
        data["raw_value"],
    )
    print(
        "  representation:",
        data["representation"],
    )


# ============================================================
# BASIC VALIDATIONS
# ============================================================

print()
print("-" * 78)
print("VALIDATIONS")
print("-" * 78)

coordinate_valid_values = (
    default_state[
        "coordinate_system"
    ][
        "valid_values"
    ]
)

coordinate_discrete_exposed = (
    coordinate_valid_values is not None
    and len(coordinate_valid_values) >= 2
)

azimuth_changes = len(
    {
        round(
            record["after_raw"],
            6,
        )
        for record in sweep_results[
            "azimuth"
        ]
    }
) > 1

elevation_changes = len(
    {
        round(
            record["after_raw"],
            6,
        )
        for record in sweep_results[
            "elevation"
        ]
    }
) > 1

all_writes_without_exception = all(
    record["write_error"] is None
    for records in sweep_results.values()
    for record in records
)

validations = {
    "required_parameters_present":
        not missing_parameters,

    "coordinate_system_discrete_values_exposed":
        coordinate_discrete_exposed,

    "azimuth_accepts_multiple_values":
        azimuth_changes,

    "elevation_accepts_multiple_values":
        elevation_changes,

    "parameter_writes_without_exception":
        all_writes_without_exception,
}

for name, result in validations.items():
    print(
        f"{name:<50}"
        f"{'PASS' if result else 'FAIL'}"
    )


# ============================================================
# RESULTS
# ============================================================

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

objective_pass = all(
    validations.values()
)

results = {
    "test_id":
        "T001-H",

    "test_name":
        (
            "dearVR PRO 2 Parameter & "
            "Coordinate-System Calibration"
        ),

    "timestamp_utc":
        datetime.now(
            timezone.utc
        ).isoformat(),

    "result":
        (
            "PASS"
            if objective_pass
            else "FAIL"
        ),

    "environment": {
        "python_version":
            platform.python_version(),

        "pedalboard_version":
            pedalboard.__version__,
    },

    "plugin": {
        "path":
            str(PLUGIN_PATH),

        "name":
            plugin.name,

        "manufacturer":
            plugin.manufacturer_name,

        "identifier":
            plugin.identifier,
    },

    "default_state":
        default_state,

    "parameter_sweeps":
        sweep_results,

    "coordinate_system_transitions":
        transition_records,

    "controlled_polar_style_state":
        controlled_polar_state,

    "controlled_cartesian_style_state":
        controlled_cartesian_state,

    "validations":
        validations,
}

with RESULTS_PATH.open(
    "w",
    encoding="utf-8",
) as file:
    json.dump(
        results,
        file,
        indent=2,
        ensure_ascii=False,
    )


# ============================================================
# FINAL SUMMARY
# ============================================================

print()
print("-" * 78)
print("EVIDENCE")
print("-" * 78)

print()
print("JSON:")
print(RESULTS_PATH)

print()

if objective_pass:
    print("=" * 78)
    print("T001-H RESULT: PASS")
    print("=" * 78)
else:
    print("=" * 78)
    print("T001-H RESULT: FAIL")
    print("=" * 78)
    raise SystemExit(1)
