import hashlib
import json
import math
from pathlib import Path


PATH = Path(
    "visualizer/public/audio/"
    "tukana-musical-behavior-runtime-v1.json"
)


K_IMPULSE = 1399.0578444065711
K_CONTINUOUS = 2212.104683325114

ATTACK_SUPPORT_SECONDS = 0.040


OVERLAP_FACTOR = (
    K_CONTINUOUS
    * ATTACK_SUPPORT_SECONDS
    / K_IMPULSE
)


data = json.loads(
    PATH.read_text(
        encoding="utf-8"
    )
)


reinforcement_count = 0

old_zero = 0
new_zero = 0

old_retention = []
new_retention = []

strong_records = []


all_source_drives = []


# First gather common absolute attack scale.

for behavior in data["behaviors"]:

    for attack in behavior.get(
        "attacks",
        []
    ):

        all_source_drives.append(
            float(
                attack["drive"]
            )
        )


    for attack in behavior.get(
        "reinforcementAttacks",
        []
    ):

        all_source_drives.append(
            float(
                attack["sourceDrive"]
            )
        )


def percentile(values, q):

    values = sorted(values)

    p = (
        (len(values) - 1)
        * q
    )

    lo = int(
        math.floor(p)
    )

    hi = min(
        lo + 1,
        len(values) - 1
    )

    f = p - lo

    return (
        values[lo]
        * (1.0 - f)
        +
        values[hi]
        * f
    )


p90 = percentile(
    all_source_drives,
    0.90
)


for behavior in data["behaviors"]:

    for attack in behavior.get(
        "reinforcementAttacks",
        []
    ):

        reinforcement_count += 1


        source_drive = float(
            attack["sourceDrive"]
        )

        baseline_drive = float(
            attack["baselineDrive"]
        )

        legacy_residual = float(
            attack["residualDrive"]
        )


        continuous_overlap_equivalent = (
            baseline_drive
            * OVERLAP_FACTOR
        )


        physical_attack_drive = max(
            0.0,
            source_drive
            - continuous_overlap_equivalent
        )


        old_r = (
            legacy_residual
            / source_drive
            if source_drive > 0
            else 0.0
        )


        new_r = (
            physical_attack_drive
            / source_drive
            if source_drive > 0
            else 0.0
        )


        if legacy_residual <= 0:
            old_zero += 1

        if physical_attack_drive <= 0:
            new_zero += 1


        old_retention.append(
            old_r
        )

        new_retention.append(
            new_r
        )


        # Preserve R2 value for forensic comparison.
        attack[
            "legacyResidualDriveR2"
        ] = legacy_residual


        attack[
            "continuousOverlapEquivalentDrive"
        ] = continuous_overlap_equivalent


        attack[
            "physicalAttackDrive"
        ] = physical_attack_drive


        attack[
            "physicalAttackRetention"
        ] = new_r


        attack[
            "couplingContract"
        ] = (
            "IMPULSE_MINUS_40MS_"
            "CONTINUOUS_EQUIVALENT"
        )


        if source_drive >= p90:

            strong_records.append({
                "time":
                    float(
                        attack["time"]
                    ),

                "source":
                    behavior["source"],

                "primitive":
                    behavior["primitive"],

                "sourceDrive":
                    source_drive,

                "baseline":
                    baseline_drive,

                "r2Drive":
                    legacy_residual,

                "r4Drive":
                    physical_attack_drive,

                "r2Retention":
                    old_r,

                "r4Retention":
                    new_r,
            })


assert reinforcement_count == 8108


data["version"] = (
    "1.3C-VISIBLE-LAB-R4"
)


data.setdefault(
    "contracts",
    {}
)[
    "transientCoupling"
] = (
    "DIMENSIONALLY_CORRECT_"
    "IMPULSE_MINUS_CONTINUOUS_"
    "EQUIVALENT_OVER_40MS"
)


data["contracts"][
    "attackSupportSeconds"
] = ATTACK_SUPPORT_SECONDS


data["contracts"][
    "continuousOverlapFactor"
] = OVERLAP_FACTOR


data["contracts"][
    "roleCodeUsedAsGain"
] = False


data["contracts"][
    "visualEnergyCandidateUsedAsHeight"
] = False


data.setdefault(
    "counts",
    {}
)[
    "dimensionallyCorrectedReinforcementAttacks"
] = reinforcement_count


payload = (
    json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    + "\n"
)


PATH.write_text(
    payload,
    encoding="utf-8",
    newline="\n"
)


sha = hashlib.sha256(
    payload.encode(
        "utf-8"
    )
).hexdigest()


print(
    "K_IMPULSE=",
    K_IMPULSE
)

print(
    "K_CONTINUOUS=",
    K_CONTINUOUS
)

print(
    "ATTACK_SUPPORT_SECONDS=",
    ATTACK_SUPPORT_SECONDS
)

print(
    "CONTINUOUS_OVERLAP_FACTOR=",
    OVERLAP_FACTOR
)


print(
    "\nREINFORCEMENT_ATTACKS=",
    reinforcement_count
)

print(
    "R2_ZERO_ATTACKS=",
    old_zero
)

print(
    "R4_ZERO_ATTACKS=",
    new_zero
)


print(
    "\nALL_R2_RETENTION_P50=",
    percentile(
        old_retention,
        0.50
    )
)

print(
    "ALL_R4_RETENTION_P50=",
    percentile(
        new_retention,
        0.50
    )
)


strong_old = [
    r["r2Retention"]
    for r in strong_records
]

strong_new = [
    r["r4Retention"]
    for r in strong_records
]


print(
    "\nSTRONG_REINFORCEMENT_COUNT=",
    len(
        strong_records
    )
)

print(
    "STRONG_R2_RETENTION_P10=",
    percentile(
        strong_old,
        0.10
    )
)

print(
    "STRONG_R2_RETENTION_P50=",
    percentile(
        strong_old,
        0.50
    )
)

print(
    "STRONG_R4_RETENTION_P10=",
    percentile(
        strong_new,
        0.10
    )
)

print(
    "STRONG_R4_RETENTION_P50=",
    percentile(
        strong_new,
        0.50
    )
)

print(
    "STRONG_R4_RETENTION_P90=",
    percentile(
        strong_new,
        0.90
    )
)


print(
    "STRONG_R4_LT50=",
    sum(
        r < 0.50
        for r in strong_new
    )
)

print(
    "STRONG_R4_LT75=",
    sum(
        r < 0.75
        for r in strong_new
    )
)


print(
    "\nFORENSIC_EXAMPLES"
)


for record in sorted(
    strong_records,
    key=lambda x:
        x["r2Retention"]
)[:12]:

    print(
        f't={record["time"]:.3f}',
        f'source={record["source"]}',
        f'primitive={record["primitive"]}',
        f'sourceDrive={record["sourceDrive"]:.9f}',
        f'R2={record["r2Drive"]:.9f}',
        f'R2ret={record["r2Retention"]:.3f}',
        f'R4={record["r4Drive"]:.9f}',
        f'R4ret={record["r4Retention"]:.3f}'
    )


print(
    "\nRUNTIME_SHA256=",
    sha
)

print(
    "TRANSIENT_COUPLING_R4_BUILD=PASS"
)
