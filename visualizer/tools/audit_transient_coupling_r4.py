import json
from pathlib import Path


PATH = Path(
    "visualizer/public/audio/"
    "tukana-musical-behavior-runtime-v1.json"
)


data = json.loads(
    PATH.read_text(
        encoding="utf-8"
    )
)


K_I = 1399.0578444065711
K_C = 2212.104683325114
T = 0.040

factor = (
    K_C * T / K_I
)


count = 0
bad_formula = 0
negative = 0
greater_than_source = 0


for behavior in data["behaviors"]:

    for attack in behavior.get(
        "reinforcementAttacks",
        []
    ):

        count += 1

        source = float(
            attack["sourceDrive"]
        )

        baseline = float(
            attack["baselineDrive"]
        )

        actual = float(
            attack["physicalAttackDrive"]
        )


        expected = max(
            0.0,
            source
            - baseline * factor
        )


        if abs(
            actual - expected
        ) > 1e-15:

            bad_formula += 1


        if actual < 0:

            negative += 1


        if actual > source + 1e-15:

            greater_than_source += 1


print(
    "AUDITED_ATTACKS=",
    count
)

print(
    "BAD_FORMULA=",
    bad_formula
)

print(
    "NEGATIVE_ATTACK_DRIVE=",
    negative
)

print(
    "DRIVE_GREATER_THAN_SOURCE=",
    greater_than_source
)


assert count == 8108
assert bad_formula == 0
assert negative == 0
assert greater_than_source == 0


print(
    "R4_CONTRACT_GATE=PASS"
)
