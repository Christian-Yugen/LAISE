import json
import math
from pathlib import Path


path = Path(
    "visualizer/public/audio/"
    "tukana-musical-behavior-runtime-v1.json"
)


data = json.loads(
    path.read_text(
        encoding="utf-8"
    )
)


events = []


for behavior in data["behaviors"]:

    source = behavior["source"]
    primitive = behavior["primitive"]
    behavior_id = behavior["behaviorId"]


    # -----------------------------------------
    # Direct physical attacks
    # IMPULSE / PULSE_SEQUENCE
    # -----------------------------------------

    for attack in behavior.get(
        "attacks",
        []
    ):

        drive = float(
            attack["drive"]
        )

        events.append({
            "time":
                float(
                    attack["time"]
                ),

            "source":
                source,

            "primitive":
                primitive,

            "behavior":
                behavior_id,

            "kind":
                "DIRECT",

            "sourceDrive":
                drive,

            "physicalDrive":
                drive,

            "baselineDrive":
                0.0,

            "retention":
                1.0,
        })


    # -----------------------------------------
    # R2 recovered attacks inside
    # SUSTAINED / ROLL.
    # -----------------------------------------

    for attack in behavior.get(
        "reinforcementAttacks",
        []
    ):

        source_drive = float(
            attack["sourceDrive"]
        )

        physical_drive = float(
            attack["residualDrive"]
        )

        baseline = float(
            attack["baselineDrive"]
        )


        retention = (
            physical_drive
            / source_drive
            if source_drive > 0
            else 0.0
        )


        events.append({
            "time":
                float(
                    attack["time"]
                ),

            "source":
                source,

            "primitive":
                primitive,

            "behavior":
                behavior_id,

            "kind":
                "REINFORCEMENT",

            "sourceDrive":
                source_drive,

            "physicalDrive":
                physical_drive,

            "baselineDrive":
                baseline,

            "retention":
                retention,
        })


events.sort(
    key=lambda e: (
        e["time"],
        e["source"]
    )
)


def percentile(values, q):

    values = sorted(values)

    if not values:
        return 0.0

    pos = (
        (len(values) - 1)
        * q
    )

    lo = int(
        math.floor(pos)
    )

    hi = min(
        lo + 1,
        len(values) - 1
    )

    f = pos - lo

    return (
        values[lo]
        * (1.0 - f)
        +
        values[hi]
        * f
    )


source_drives = [
    e["sourceDrive"]
    for e in events
]


p50 = percentile(
    source_drives,
    0.50
)

p75 = percentile(
    source_drives,
    0.75
)

p90 = percentile(
    source_drives,
    0.90
)

p95 = percentile(
    source_drives,
    0.95
)

p99 = percentile(
    source_drives,
    0.99
)


direct = [
    e
    for e in events
    if e["kind"] == "DIRECT"
]


reinforcement = [
    e
    for e in events
    if e["kind"] == "REINFORCEMENT"
]


print(
    "TOTAL_ATTACK_EVIDENCE=",
    len(events)
)

print(
    "DIRECT_ATTACKS=",
    len(direct)
)

print(
    "REINFORCEMENT_ATTACKS=",
    len(reinforcement)
)

print(
    "SOURCE_DRIVE_P50=",
    p50
)

print(
    "SOURCE_DRIVE_P75=",
    p75
)

print(
    "SOURCE_DRIVE_P90=",
    p90
)

print(
    "SOURCE_DRIVE_P95=",
    p95
)

print(
    "SOURCE_DRIVE_P99=",
    p99
)


# ==========================================
# Strong attacks
# ==========================================

strong = [
    e
    for e in events
    if e["sourceDrive"] >= p90
]


strong_reinforcement = [
    e
    for e in strong
    if e["kind"]
    == "REINFORCEMENT"
]


print(
    "\nSTRONG_ATTACKS_P90_PLUS=",
    len(strong)
)

print(
    "STRONG_DIRECT=",
    sum(
        e["kind"] == "DIRECT"
        for e in strong
    )
)

print(
    "STRONG_REINFORCEMENT=",
    len(
        strong_reinforcement
    )
)


retentions = [
    e["retention"]
    for e in strong_reinforcement
]


if retentions:

    print(
        "STRONG_RETENTION_P10=",
        percentile(
            retentions,
            0.10
        )
    )

    print(
        "STRONG_RETENTION_P50=",
        percentile(
            retentions,
            0.50
        )
    )

    print(
        "STRONG_RETENTION_P90=",
        percentile(
            retentions,
            0.90
        )
    )


    for threshold in (
        0.10,
        0.25,
        0.50,
        0.75
    ):

        count = sum(
            e["retention"]
            < threshold
            for e in strong_reinforcement
        )

        print(
            "STRONG_RETENTION_LT_"
            + str(
                int(
                    threshold * 100
                )
            )
            + "=",
            count
        )


# ==========================================
# Most suppressed strong attacks
# ==========================================

suppressed = [
    e
    for e in strong_reinforcement
    if e["retention"] < 0.50
]


print(
    "\nSTRONG_ATTACKS_RETAINED_LT50=",
    len(suppressed)
)


print(
    "\nMOST_SUPPRESSED_STRONG_ATTACKS"
)


for e in sorted(
    suppressed,
    key=lambda x: (
        x["retention"],
        -x["sourceDrive"]
    )
)[:20]:

    print(
        f't={e["time"]:.3f}',
        f'source={e["source"]}',
        f'primitive={e["primitive"]}',
        f'sourceDrive={e["sourceDrive"]:.9f}',
        f'baseline={e["baselineDrive"]:.9f}',
        f'physical={e["physicalDrive"]:.9f}',
        f'retention={e["retention"]:.3f}'
    )


# ==========================================
# Repeated "tum tum tmtum" structures
#
# Same source:
# >= 3 attacks
# consecutive gap <= 350 ms.
#
# AUDIT ONLY.
# ==========================================

by_source = {}


for e in events:

    by_source.setdefault(
        e["source"],
        []
    ).append(
        e
    )


clusters = []


for source, sequence in by_source.items():

    current = []


    for e in sequence:

        if not current:

            current = [e]
            continue


        gap = (
            e["time"]
            - current[-1]["time"]
        )


        if gap <= 0.350:

            current.append(
                e
            )

        else:

            if len(current) >= 3:
                clusters.append(
                    current
                )

            current = [e]


    if len(current) >= 3:

        clusters.append(
            current
        )


def max_drive(cluster):

    return max(
        e["sourceDrive"]
        for e in cluster
    )


strong_clusters = [
    c
    for c in clusters
    if max_drive(c) >= p90
]


print(
    "\nREPEATED_CLUSTERS_TOTAL=",
    len(clusters)
)

print(
    "REPEATED_CLUSTERS_WITH_P90_ATTACK=",
    len(strong_clusters)
)


print(
    "\nTOP_REPEATED_STRONG_CLUSTERS"
)


for cluster in sorted(
    strong_clusters,
    key=max_drive,
    reverse=True
)[:25]:

    intervals = [
        round(
            cluster[i]["time"]
            - cluster[i - 1]["time"],
            3
        )
        for i in range(
            1,
            len(cluster)
        )
    ]


    retained = [
        e["retention"]
        for e in cluster
        if e["kind"]
        == "REINFORCEMENT"
    ]


    mean_retention = (
        sum(retained)
        / len(retained)
        if retained
        else 1.0
    )


    below_half = sum(
        r < 0.50
        for r in retained
    )


    print(
        f'source={cluster[0]["source"]}',
        f'start={cluster[0]["time"]:.3f}',
        f'end={cluster[-1]["time"]:.3f}',
        f'count={len(cluster)}',
        f'maxDrive={max_drive(cluster):.9f}',
        f'meanRetention={mean_retention:.3f}',
        f'below50={below_half}',
        f'IOIs={intervals[:12]}'
    )


zero_physical = sum(
    e["physicalDrive"] <= 0
    for e in events
)


print(
    "\nZERO_PHYSICAL_ATTACKS=",
    zero_physical
)


assert len(events) == 10282
assert len(direct) == 2174
assert len(reinforcement) == 8108


print(
    "RHYTHMIC_ATTACK_AUDIT=PASS"
)
