"""
LAISE — T001-I1
dearVR PRO 2 Front-Cue Parameter Discovery

Goal
----
Inventory every parameter exposed by dearVR PRO 2 and identify parameters
potentially useful for improving FRONT/BACK discrimination and externalization.

This test does NOT render audio and does NOT modify the T001-G blind key.

Evidence
--------
evidence/T001/T001-I1/
    t001i1_front_cue_parameter_discovery.json
"""

from __future__ import annotations

import json
import platform
import re
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
    / "T001-I1"
)

RESULTS_PATH = (
    OUTPUT_DIR
    / "t001i1_front_cue_parameter_discovery.json"
)


# ============================================================
# CANDIDATE KEYWORDS
# ============================================================

CUE_KEYWORDS = [
    "room",
    "reflection",
    "early",
    "reverb",
    "rev",
    "distance",
    "azimuth",
    "elevation",
    "hrtf",
    "binaural",
    "head",
    "width",
    "focus",
    "spread",
    "size",
    "occlusion",
    "absorption",
    "direct",
    "dry",
    "wet",
    "gain",
    "output",
    "input",
    "performance",
]


# ============================================================
# HELPERS
# ============================================================

def safe_str(value):
    try:
        return str(value)
    except Exception as exc:
        return f"<ERROR: {exc!r}>"


def safe_raw(parameter):
    try:
        return float(parameter.raw_value)
    except Exception:
        return None


def safe_valid_values(parameter):
    try:
        values = parameter.valid_values
        if values is None:
            return None
        return [safe_str(v) for v in values]
    except Exception:
        return None


def extract_display_name(representation: str):
    match = re.search(r'name="([^"]+)"', representation)
    return match.group(1) if match else None


def extract_display_value(representation: str):
    match = re.search(r'value="([^"]*)"', representation)
    return match.group(1) if match else None


def classify_candidate(
    internal_name: str,
    display_name: str | None,
    representation: str,
):
    searchable = " ".join(
        [
            internal_name or "",
            display_name or "",
            representation or "",
        ]
    ).lower()

    matches = [
        keyword
        for keyword in CUE_KEYWORDS
        if keyword in searchable
    ]

    return matches


def summarize_values(values):
    """
    Avoid dumping hundreds/thousands of discrete values to terminal.
    Full values are still preserved in JSON.
    """

    if values is None:
        return {
            "count": None,
            "first": None,
            "middle": None,
            "last": None,
        }

    count = len(values)

    if count == 0:
        return {
            "count": 0,
            "first": None,
            "middle": None,
            "last": None,
        }

    return {
        "count": count,
        "first": values[0],
        "middle": values[count // 2],
        "last": values[-1],
    }


# ============================================================
# HEADER
# ============================================================

print()
print("=" * 78)
print("LAISE — T001-I1")
print("dearVR PRO 2 Front-Cue Parameter Discovery")
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
    print("Plugin path: FAIL")
    raise SystemExit(
        f"Plugin not found:\n{PLUGIN_PATH}"
    )

print("Plugin path: PASS")

plugin = load_plugin(str(PLUGIN_PATH))

print("Plugin load: PASS")

print()
print("Name:", plugin.name)
print("Manufacturer:", plugin.manufacturer_name)
print("Identifier:", plugin.identifier)


# ============================================================
# INVENTORY
# ============================================================

print()
print("-" * 78)
print("FULL PARAMETER INVENTORY")
print("-" * 78)

parameter_records = []

for index, (internal_name, parameter) in enumerate(
    plugin.parameters.items(),
    start=1,
):
    representation = safe_str(parameter)
    raw_value = safe_raw(parameter)
    valid_values = safe_valid_values(parameter)

    display_name = extract_display_name(
        representation
    )

    display_value = extract_display_value(
        representation
    )

    cue_matches = classify_candidate(
        internal_name,
        display_name,
        representation,
    )

    value_summary = summarize_values(
        valid_values
    )

    record = {
        "index": index,
        "internal_name": internal_name,
        "display_name": display_name,
        "display_value": display_value,
        "raw_value": raw_value,
        "representation": representation,
        "valid_values": valid_values,
        "valid_values_summary": value_summary,
        "front_cue_keyword_matches": cue_matches,
        "front_cue_candidate": bool(cue_matches),
    }

    parameter_records.append(record)

    print()
    print(
        f"[{index:02d}] "
        f"{internal_name}"
    )

    print(
        "     display name :",
        display_name,
    )

    print(
        "     display value:",
        display_value,
    )

    print(
        "     raw value    :",
        raw_value,
    )

    print(
        "     values count :",
        value_summary["count"],
    )

    if value_summary["count"]:
        print(
            "     first        :",
            value_summary["first"],
        )
        print(
            "     middle       :",
            value_summary["middle"],
        )
        print(
            "     last         :",
            value_summary["last"],
        )

    if cue_matches:
        print(
            "     FRONT CUE    :",
            ", ".join(cue_matches),
        )


# ============================================================
# FRONT-CUE CANDIDATES
# ============================================================

candidate_records = [
    record
    for record in parameter_records
    if record["front_cue_candidate"]
]

print()
print("-" * 78)
print("FRONT / EXTERNALIZATION CANDIDATES")
print("-" * 78)

if not candidate_records:
    print()
    print("No candidates found by keyword.")
else:
    for record in candidate_records:
        print()
        print(
            f"[{record['index']:02d}] "
            f"{record['internal_name']}"
        )
        print(
            "     display:",
            record["display_name"],
        )
        print(
            "     current:",
            record["display_value"],
        )
        print(
            "     raw:",
            record["raw_value"],
        )
        print(
            "     matched:",
            ", ".join(
                record[
                    "front_cue_keyword_matches"
                ]
            ),
        )


# ============================================================
# IMPORTANT SPATIAL PARAMETERS
# ============================================================

print()
print("-" * 78)
print("KNOWN SPATIAL BASELINE")
print("-" * 78)

baseline_names = [
    "coordinate_system",
    "azimuth",
    "elevation",
    "distance",
    "x",
    "y",
    "z",
]

baseline = {}

for name in baseline_names:

    if name not in plugin.parameters:
        baseline[name] = {
            "present": False
        }
        print(
            f"{name:<24} MISSING"
        )
        continue

    parameter = plugin.parameters[name]
    representation = safe_str(parameter)

    baseline[name] = {
        "present": True,
        "raw_value": safe_raw(parameter),
        "display_name":
            extract_display_name(
                representation
            ),
        "display_value":
            extract_display_value(
                representation
            ),
        "representation":
            representation,
    }

    print(
        f"{name:<24}"
        f"raw={baseline[name]['raw_value']!s:<16}"
        f"value={baseline[name]['display_value']}"
    )


# ============================================================
# VALIDATIONS
# ============================================================

print()
print("-" * 78)
print("VALIDATIONS")
print("-" * 78)

parameter_count = len(parameter_records)

validations = {
    "plugin_loaded":
        plugin is not None,

    "parameters_discovered":
        parameter_count > 0,

    "expected_spatial_parameters_present":
        all(
            name in plugin.parameters
            for name in baseline_names
        ),

    "parameter_representations_readable":
        all(
            bool(
                record["representation"]
            )
            for record in parameter_records
        ),

    "front_cue_candidate_scan_completed":
        True,
}

for name, result in validations.items():
    print(
        f"{name:<52}"
        f"{'PASS' if result else 'FAIL'}"
    )

print()
print("Total parameters discovered:")
print(parameter_count)

print()
print("Front-cue candidates:")
print(len(candidate_records))


# ============================================================
# WRITE EVIDENCE
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
        "T001-I1",

    "test_name":
        (
            "dearVR PRO 2 "
            "Front-Cue Parameter Discovery"
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

    "parameter_count":
        parameter_count,

    "parameters":
        parameter_records,

    "front_cue_candidates":
        candidate_records,

    "known_spatial_baseline":
        baseline,

    "candidate_keywords":
        CUE_KEYWORDS,

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
# FINAL
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
    print("T001-I1 RESULT: PASS")
    print("=" * 78)
else:
    print("=" * 78)
    print("T001-I1 RESULT: FAIL")
    print("=" * 78)
    raise SystemExit(1)
