from pathlib import Path
import hashlib
import json
import sys
from datetime import datetime, timezone

import mido
from mido import (
    Message,
    MetaMessage,
    MidiFile,
    MidiTrack,
    bpm2tempo,
)


# ============================================================
# LAISE — T002-A
# Deterministic Procedural MIDI Generation
#
# Objective:
# Validate the first stage of LAISE's musical generation
# pipeline:
#
#     Python -> procedural musical structure -> MIDI file
#
# This test intentionally does NOT use:
#
#   - FluidSynth
#   - SoundFonts
#   - dearVR
#   - Pedalboard
#   - mastering
#
# The goal is to isolate and prove MIDI generation first.
#
# Musical structure:
#
#   Tempo:       120 BPM
#   Meter:       4/4
#   Tonality:    C major
#   PPQ:         480 ticks/quarter note
#   Duration:    4 bars
#
# Notes:
#
#   Bar 1: C4
#   Bar 2: E4
#   Bar 3: G4
#   Bar 4: C5
#
# Each note lasts exactly one 4/4 bar.
#
# This is an infrastructure validation test.
# It is NOT yet the production LAISE composer.
# ============================================================


# ------------------------------------------------------------
# Test identification
# ------------------------------------------------------------

TEST_ID = "T002-A"
TEST_NAME = "Deterministic Procedural MIDI Generation"


# ------------------------------------------------------------
# Musical configuration
# ------------------------------------------------------------

BPM = 120
TIME_SIGNATURE_NUMERATOR = 4
TIME_SIGNATURE_DENOMINATOR = 4

TICKS_PER_BEAT = 480

BARS = 4

KEY_SIGNATURE = "C"

MIDI_CHANNEL = 0

PROGRAM_NUMBER = 0

VELOCITY = 90


# ------------------------------------------------------------
# Deterministic sequence
#
# MIDI note numbers:
#
# C4 = 60
# E4 = 64
# G4 = 67
# C5 = 72
# ------------------------------------------------------------

NOTE_SEQUENCE = [
    {
        "bar": 1,
        "name": "C4",
        "midi_note": 60,
    },
    {
        "bar": 2,
        "name": "E4",
        "midi_note": 64,
    },
    {
        "bar": 3,
        "name": "G4",
        "midi_note": 67,
    },
    {
        "bar": 4,
        "name": "C5",
        "midi_note": 72,
    },
]


# ------------------------------------------------------------
# Output paths
# ------------------------------------------------------------

OUTPUT_DIR = (
    Path("evidence")
    / "T002"
    / "T002-A"
)

MIDI_FILE = (
    OUTPUT_DIR
    / "t002a_procedural_midi.mid"
)

JSON_FILE = (
    OUTPUT_DIR
    / "t002a_procedural_midi_results.json"
)


# ------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------

def sha256_file(path: Path) -> str:

    digest = hashlib.sha256()

    with path.open("rb") as file:

        while True:

            block = file.read(
                1024 * 1024
            )

            if not block:
                break

            digest.update(block)

    return digest.hexdigest()


def expected_seconds(
    bars: int,
    bpm: int,
    beats_per_bar: int,
) -> float:

    total_beats = (
        bars
        * beats_per_bar
    )

    seconds_per_beat = (
        60.0
        / bpm
    )

    return (
        total_beats
        * seconds_per_beat
    )


def collect_absolute_events(
    midi: MidiFile,
):

    collected = []

    for track_index, track in enumerate(
        midi.tracks
    ):

        absolute_tick = 0

        for message_index, message in enumerate(
            track
        ):

            absolute_tick += message.time

            event = {
                "track_index": (
                    track_index
                ),
                "message_index": (
                    message_index
                ),
                "absolute_tick": (
                    absolute_tick
                ),
                "delta_ticks": (
                    message.time
                ),
                "type": (
                    message.type
                ),
            }

            if hasattr(
                message,
                "channel",
            ):

                event["channel"] = (
                    message.channel
                )

            if hasattr(
                message,
                "note",
            ):

                event["note"] = (
                    message.note
                )

            if hasattr(
                message,
                "velocity",
            ):

                event["velocity"] = (
                    message.velocity
                )

            if hasattr(
                message,
                "program",
            ):

                event["program"] = (
                    message.program
                )

            if message.type == "set_tempo":

                event["tempo"] = (
                    message.tempo
                )

            if message.type == "time_signature":

                event["numerator"] = (
                    message.numerator
                )

                event["denominator"] = (
                    message.denominator
                )

            if message.type == "key_signature":

                event["key"] = (
                    message.key
                )

            if message.type == "track_name":

                event["name"] = (
                    message.name
                )

            collected.append(
                event
            )

    return collected


# ------------------------------------------------------------
# Header
# ------------------------------------------------------------

print("=" * 78)
print("LAISE — T002-A")
print("Deterministic Procedural MIDI Generation")
print("=" * 78)


# ------------------------------------------------------------
# Prepare evidence directory
# ------------------------------------------------------------

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ------------------------------------------------------------
# 1. Environment
# ------------------------------------------------------------

print(
    "\n[1/7] Checking MIDI environment..."
)


print(
    f"Python:             "
    f"{sys.version.split()[0]}"
)

print(
    "Mido:               installed"
)

print(
    f"Ticks per beat:      "
    f"{TICKS_PER_BEAT}"
)


# ------------------------------------------------------------
# 2. Define deterministic musical structure
# ------------------------------------------------------------

print(
    "\n[2/7] Defining deterministic musical structure..."
)


tempo_microseconds = bpm2tempo(
    BPM
)


ticks_per_bar = (
    TICKS_PER_BEAT
    * TIME_SIGNATURE_NUMERATOR
)


total_expected_ticks = (
    ticks_per_bar
    * BARS
)


duration_expected_seconds = expected_seconds(
    bars=BARS,
    bpm=BPM,
    beats_per_bar=TIME_SIGNATURE_NUMERATOR,
)


print(
    f"Tempo:              "
    f"{BPM} BPM"
)

print(
    f"Meter:              "
    f"{TIME_SIGNATURE_NUMERATOR}/"
    f"{TIME_SIGNATURE_DENOMINATOR}"
)

print(
    f"Key:                "
    f"{KEY_SIGNATURE} major"
)

print(
    f"Bars:               "
    f"{BARS}"
)

print(
    f"Ticks per bar:      "
    f"{ticks_per_bar}"
)

print(
    f"Expected ticks:     "
    f"{total_expected_ticks}"
)

print(
    f"Expected duration:  "
    f"{duration_expected_seconds:.3f} s"
)


# ------------------------------------------------------------
# 3. Create MIDI
# ------------------------------------------------------------

print(
    "\n[3/7] Creating MIDI events..."
)


midi = MidiFile(
    type=1,
    ticks_per_beat=TICKS_PER_BEAT,
)


track = MidiTrack()

midi.tracks.append(
    track
)


# ------------------------------------------------------------
# Metadata
# ------------------------------------------------------------

track.append(
    MetaMessage(
        "track_name",
        name="LAISE T002-A Procedural Test",
        time=0,
    )
)


track.append(
    MetaMessage(
        "set_tempo",
        tempo=tempo_microseconds,
        time=0,
    )
)


track.append(
    MetaMessage(
        "time_signature",
        numerator=TIME_SIGNATURE_NUMERATOR,
        denominator=TIME_SIGNATURE_DENOMINATOR,
        clocks_per_click=24,
        notated_32nd_notes_per_beat=8,
        time=0,
    )
)


track.append(
    MetaMessage(
        "key_signature",
        key=KEY_SIGNATURE,
        time=0,
    )
)


# ------------------------------------------------------------
# General MIDI program
#
# Program 0 = Acoustic Grand Piano in zero-based MIDI program
# numbering.
#
# The sound itself is irrelevant in T002-A because no
# synthesizer is used yet.
# ------------------------------------------------------------

track.append(
    Message(
        "program_change",
        program=PROGRAM_NUMBER,
        channel=MIDI_CHANNEL,
        time=0,
    )
)


# ------------------------------------------------------------
# Procedural note generation
#
# One note per bar.
#
# Each note:
#
# note_on  -> delta 0
# note_off -> delta ticks_per_bar
#
# This creates four consecutive whole-bar notes.
# ------------------------------------------------------------

generated_events = []


for note_definition in NOTE_SEQUENCE:

    midi_note = (
        note_definition[
            "midi_note"
        ]
    )

    note_name = (
        note_definition[
            "name"
        ]
    )

    bar_number = (
        note_definition[
            "bar"
        ]
    )


    track.append(
        Message(
            "note_on",
            note=midi_note,
            velocity=VELOCITY,
            channel=MIDI_CHANNEL,
            time=0,
        )
    )


    track.append(
        Message(
            "note_off",
            note=midi_note,
            velocity=0,
            channel=MIDI_CHANNEL,
            time=ticks_per_bar,
        )
    )


    generated_events.append(
        {
            "bar": (
                bar_number
            ),
            "note_name": (
                note_name
            ),
            "midi_note": (
                midi_note
            ),
            "velocity": (
                VELOCITY
            ),
            "duration_ticks": (
                ticks_per_bar
            ),
        }
    )


    print(
        f"Bar {bar_number}: "
        f"{note_name:<3} | "
        f"MIDI {midi_note:<3} | "
        f"duration "
        f"{ticks_per_bar} ticks"
    )


track.append(
    MetaMessage(
        "end_of_track",
        time=0,
    )
)


# ------------------------------------------------------------
# 4. Save MIDI
# ------------------------------------------------------------

print(
    "\n[4/7] Writing MIDI evidence..."
)


midi.save(
    MIDI_FILE
)


if not MIDI_FILE.exists():

    raise RuntimeError(
        "MIDI file was not created."
    )


midi_size_bytes = (
    MIDI_FILE.stat().st_size
)


midi_sha256 = sha256_file(
    MIDI_FILE
)


print(
    f"MIDI:               "
    f"{MIDI_FILE.resolve()}"
)

print(
    f"Size:               "
    f"{midi_size_bytes} bytes"
)

print(
    f"SHA256:             "
    f"{midi_sha256}"
)


# ------------------------------------------------------------
# 5. Re-open and independently inspect generated MIDI
#
# Important:
# We do not validate only the in-memory object.
# The actual file written to disk is loaded again.
# ------------------------------------------------------------

print(
    "\n[5/7] Re-opening and validating MIDI file..."
)


validated_midi = MidiFile(
    MIDI_FILE
)


absolute_events = collect_absolute_events(
    validated_midi
)


note_on_events = []

note_off_events = []


for event in absolute_events:

    if (
        event["type"] == "note_on"
        and event.get(
            "velocity",
            0,
        ) > 0
    ):

        note_on_events.append(
            event
        )


    if (
        event["type"] == "note_off"
        or (
            event["type"] == "note_on"
            and event.get(
                "velocity",
                0,
            ) == 0
        )
    ):

        note_off_events.append(
            event
        )


# ------------------------------------------------------------
# Determine total MIDI ticks
# ------------------------------------------------------------

max_absolute_tick = max(
    event["absolute_tick"]
    for event in absolute_events
)


# ------------------------------------------------------------
# Mido calculates playback duration using MIDI tempo events.
# ------------------------------------------------------------

actual_duration_seconds = float(
    validated_midi.length
)


print(
    f"File type:          "
    f"{validated_midi.type}"
)

print(
    f"Tracks:             "
    f"{len(validated_midi.tracks)}"
)

print(
    f"Ticks per beat:     "
    f"{validated_midi.ticks_per_beat}"
)

print(
    f"Note ON events:     "
    f"{len(note_on_events)}"
)

print(
    f"Note OFF events:    "
    f"{len(note_off_events)}"
)

print(
    f"Total ticks:        "
    f"{max_absolute_tick}"
)

print(
    f"Actual duration:    "
    f"{actual_duration_seconds:.3f} s"
)


# ------------------------------------------------------------
# 6. Objective validation
# ------------------------------------------------------------

print(
    "\n[6/7] Running objective validation..."
)


validation = {
    "file_exists": (
        MIDI_FILE.exists()
    ),
    "file_not_empty": (
        midi_size_bytes > 0
    ),
    "midi_type_is_1": (
        validated_midi.type == 1
    ),
    "track_count_is_1": (
        len(
            validated_midi.tracks
        ) == 1
    ),
    "ticks_per_beat_correct": (
        validated_midi.ticks_per_beat
        == TICKS_PER_BEAT
    ),
    "note_on_count_correct": (
        len(
            note_on_events
        )
        == len(
            NOTE_SEQUENCE
        )
    ),
    "note_off_count_correct": (
        len(
            note_off_events
        )
        == len(
            NOTE_SEQUENCE
        )
    ),
    "total_ticks_correct": (
        max_absolute_tick
        == total_expected_ticks
    ),
    "duration_correct": (
        abs(
            actual_duration_seconds
            - duration_expected_seconds
        )
        < 0.001
    ),
}


expected_notes = [
    item["midi_note"]
    for item in NOTE_SEQUENCE
]


actual_notes = [
    event["note"]
    for event in note_on_events
]


validation[
    "note_sequence_correct"
] = (
    actual_notes
    == expected_notes
)


all_passed = all(
    validation.values()
)


for check_name, passed in validation.items():

    print(
        f"{check_name:<30} "
        f"{'PASS' if passed else 'FAIL'}"
    )


if not all_passed:

    failed_checks = [
        key
        for key, value
        in validation.items()
        if not value
    ]

    raise RuntimeError(
        "T002-A validation failed: "
        + ", ".join(
            failed_checks
        )
    )


# ------------------------------------------------------------
# 7. Write JSON evidence
# ------------------------------------------------------------

print(
    "\n[7/7] Writing validation manifest..."
)


evidence = {
    "test_id": (
        TEST_ID
    ),
    "test_name": (
        TEST_NAME
    ),
    "status": (
        "PASS"
    ),
    "timestamp_utc": (
        datetime.now(
            timezone.utc
        ).isoformat()
    ),
    "environment": {
        "python_version": (
            sys.version.split()[0]
        ),
        "mido": (
            "installed"
        ),
    },
    "musical_configuration": {
        "bpm": (
            BPM
        ),
        "meter": {
            "numerator": (
                TIME_SIGNATURE_NUMERATOR
            ),
            "denominator": (
                TIME_SIGNATURE_DENOMINATOR
            ),
        },
        "key_signature": (
            KEY_SIGNATURE
        ),
        "mode": (
            "major"
        ),
        "bars": (
            BARS
        ),
        "ticks_per_beat": (
            TICKS_PER_BEAT
        ),
        "ticks_per_bar": (
            ticks_per_bar
        ),
        "expected_total_ticks": (
            total_expected_ticks
        ),
        "expected_duration_seconds": (
            duration_expected_seconds
        ),
        "channel": (
            MIDI_CHANNEL
        ),
        "program_number": (
            PROGRAM_NUMBER
        ),
        "velocity": (
            VELOCITY
        ),
    },
    "generated_notes": (
        generated_events
    ),
    "observed": {
        "midi_type": (
            validated_midi.type
        ),
        "track_count": (
            len(
                validated_midi.tracks
            )
        ),
        "ticks_per_beat": (
            validated_midi.ticks_per_beat
        ),
        "note_on_count": (
            len(
                note_on_events
            )
        ),
        "note_off_count": (
            len(
                note_off_events
            )
        ),
        "note_sequence": (
            actual_notes
        ),
        "total_ticks": (
            max_absolute_tick
        ),
        "duration_seconds": (
            actual_duration_seconds
        ),
    },
    "validation": (
        validation
    ),
    "midi_file": {
        "path": str(
            MIDI_FILE.resolve()
        ),
        "size_bytes": (
            midi_size_bytes
        ),
        "sha256": (
            midi_sha256
        ),
    },
    "events": (
        absolute_events
    ),
}


with JSON_FILE.open(
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
    f"JSON:               "
    f"{JSON_FILE.resolve()}"
)


print(
    "\n" + "=" * 78
)

print(
    "T002-A RESULT: PASS"
)

print(
    "=" * 78
)


print(
    "\nEvidence files:"
)

print(
    f"  {MIDI_FILE.resolve()}"
)

print(
    f"  {JSON_FILE.resolve()}"
)


print(
    "\nExpected musical sequence:"
)

print(
    "  C4 -> E4 -> G4 -> C5"
)

print(
    "\nExpected duration:"
)

print(
    f"  {duration_expected_seconds:.3f} seconds"
)