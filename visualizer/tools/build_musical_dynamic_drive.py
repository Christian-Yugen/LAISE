"""V1.3C lab: measured temporal physical-drive evidence."""
from __future__ import annotations
import argparse,bisect,hashlib,json,math,statistics
from collections import Counter
from pathlib import Path

V=Path(__file__).resolve().parents[1]
AUDIO=V/"public/audio"
FEATURES=V/"reports/v1_3a-musical-gesture-intelligence/features"
BEHAVIORS=AUDIO/"tukana-musical-behaviors-v1.json"
CUES=AUDIO/"tukana-stem-cues.json"
OUTPUT=AUDIO/"tukana-musical-dynamic-drive-v1.json"

EXPECTED_BEHAVIOR_SHA=(
    "80737ccf50a87afcfc04963a42a4d52d"
    "75697dec9b2b09788a1fa69e3dab65b4"
)

CONTINUOUS={
    "SUSTAINED_EXCITATION",
    "ROLL_RESONANCE",
}

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(
            lambda:f.read(1024*1024),
            b"",
        ):
            h.update(chunk)
    return h.hexdigest()

def load(path):
    return json.loads(
        path.read_text(encoding="utf-8")
    )

def finite(value,default=0.0):
    try:
        result=float(value)
    except (TypeError,ValueError):
        return default
    return (
        result
        if math.isfinite(result)
        else default
    )

def multiplier(behavior):
    d=behavior.get("drive") or {}

    return (
        max(
            0.0,
            finite(
                d.get("salienceFactor"),
                1.0,
            ),
        )
        *
        max(
            0.0,
            finite(
                d.get("localContextFactor"),
                1.0,
            ),
        )
        *
        max(
            0.0,
            finite(
                d.get("trackContextFactor"),
                1.0,
            ),
        )
    )

def series(feature):
    cols=feature["columns"]

    ti=cols.index("time")
    ei=cols.index("envelope")

    return (
        [
            finite(row[ti])
            for row in feature["rows"]
        ],
        [
            max(
                0.0,
                finite(row[ei]),
            )
            for row in feature["rows"]
        ],
    )

def measured_samples(
    feature,
    start,
    end,
    factor,
):
    times,envelope=series(feature)

    left=bisect.bisect_left(
        times,
        start-1e-9,
    )

    # Causal interval:
    # start inclusive / end exclusive.
    right=bisect.bisect_left(
        times,
        end,
    )

    return [
        [
            round(t,6),
            value,
            value*factor,
        ]
        for t,value in zip(
            times[left:right],
            envelope[left:right],
        )
    ]

def measure_trend(
    samples,
    start,
    end,
):
    selected=[
        row
        for row in samples
        if (
            start-1e-9
            <= row[0]
            < end
            and row[1]>1e-12
        )
    ]

    if len(selected)<5:
        return None

    db=[
        20*math.log10(row[1])
        for row in selected
    ]

    n=max(
        1,
        len(db)//5,
    )

    change=(
        statistics.median(db[-n:])
        -
        statistics.median(db[:n])
    )

    mean_x=(len(db)-1)/2
    mean_y=statistics.fmean(db)

    covariance=sum(
        (i-mean_x)*(value-mean_y)
        for i,value in enumerate(db)
    )

    variance_x=sum(
        (i-mean_x)**2
        for i in range(len(db))
    )

    variance_y=sum(
        (value-mean_y)**2
        for value in db
    )

    correlation=(
        covariance
        /
        math.sqrt(
            variance_x*variance_y
        )
        if (
            variance_x>0
            and variance_y>0
        )
        else 0.0
    )

    return {
        "measuredEnergyChangeDb":
            change,

        "measuredEnergyTimeCorrelation":
            correlation,

        "sampleCount":
            len(selected),
    }

def build(output):

    behavior_sha=sha(BEHAVIORS)

    if (
        behavior_sha
        != EXPECTED_BEHAVIOR_SHA
    ):
        raise RuntimeError(
            "Behavior foundation hash mismatch: "
            + behavior_sha
        )

    behavior_payload=load(
        BEHAVIORS
    )

    cue_payload=load(
        CUES
    )

    behaviors=(
        behavior_payload["behaviors"]
    )

    cues=(
        cue_payload["events"]
    )

    features={}
    feature_hashes={}

    for path in sorted(
        FEATURES.glob("*.json")
    ):
        payload=load(path)
        source=payload["source"]

        features[source]=payload
        feature_hashes[source]=sha(path)

    if len(features)!=12:
        raise RuntimeError(
            "Expected 12 feature datasets; "
            f"found {len(features)}"
        )

    rows=[]

    invalid=[]
    missing=[]
    empty_continuous=[]
    trends=[]

    total_samples=0
    total_attacks=0

    for behavior in behaviors:

        behavior_id=(
            behavior["behaviorId"]
        )

        source=behavior["source"]
        primitive=behavior["primitive"]

        start=finite(
            behavior["startTime"]
        )

        end=finite(
            behavior["endTime"],
            start,
        )

        factor=multiplier(
            behavior
        )

        feature=features.get(
            source
        )

        if feature is None:
            missing.append(
                behavior_id
            )

        samples=[]

        if (
            primitive in CONTINUOUS
            and feature is not None
        ):
            samples=measured_samples(
                feature,
                start,
                end,
                factor,
            )

            if not samples:
                empty_continuous.append(
                    behavior_id
                )

            total_samples+=len(
                samples
            )

        attack_drive=[]

        refs=(
            (
                behavior.get("evidence")
                or {}
            ).get("attackRefs")
            or []
        )

        for ref in refs:

            if (
                not isinstance(ref,int)
                or ref<0
                or ref>=len(cues)
            ):
                invalid.append(
                    (
                        behavior_id,
                        ref,
                    )
                )
                continue

            cue=cues[ref]

            amplitude=max(
                0.0,
                finite(
                    cue.get("amplitude")
                ),
            )

            attack_drive.append({
                "attackRef":
                    ref,

                "time":
                    finite(
                        cue.get("time")
                    ),

                "x":
                    finite(
                        cue.get("x")
                    ),

                "z":
                    finite(
                        cue.get("z")
                    ),

                "absoluteAmplitude":
                    amplitude,

                "physicalDrive":
                    amplitude*factor,
            })

        total_attacks+=len(
            attack_drive
        )

        trend_audit=[]

        trend_modifiers=(
            (
                behavior.get("modifiers")
                or {}
            ).get("trend")
            or []
        )

        for trend in trend_modifiers:

            trend_start=finite(
                trend.get("startTime")
            )

            trend_end=finite(
                trend.get("endTime")
            )

            # Trend validation and causal physical drive are
            # intentionally different domains.
            #
            # The V1.3A trend classification describes the complete
            # musical gesture. Validate it against the complete
            # measured V1.3A feature interval, never against a
            # behavior-clipped subset.
            #
            # This does NOT extend physical excitation beyond the
            # V1.3B causal behavior interval. `samples` above remains
            # strictly start-inclusive / end-exclusive for the
            # continuous physical drive.
            audit_samples=[]

            if feature is not None:
                audit_samples=(
                    measured_samples(
                        feature,
                        trend_start,
                        trend_end,
                        factor,
                    )
                )

            item={
                "gestureId":
                    trend.get("gestureId"),

                "type":
                    trend.get("type"),

                "expectedEnergyChangeDb":
                    finite(
                        trend.get(
                            "energyChangeDb"
                        )
                    ),

                "expectedEnergyTimeCorrelation":
                    finite(
                        trend.get(
                            "energyTimeCorrelation"
                        )
                    ),

                "measurement":
                    measure_trend(
                        audit_samples,
                        trend_start,
                        trend_end,
                    ),
            }

            trend_audit.append(
                item
            )

            trends.append(
                item
            )

        rows.append({

            "behaviorId":
                behavior_id,

            "intentId":
                behavior["intentId"],

            "source":
                source,

            "primitive":
                primitive,

            "startTime":
                start,

            "endTime":
                end,

            "contextMultiplier":
                factor,

            "scalarReferenceDrive":
                max(
                    0.0,
                    finite(
                        (
                            behavior.get("drive")
                            or {}
                        ).get(
                            "physicalDrive"
                        )
                    ),
                ),

            "continuousDrive":{

                "mode":
                    (
                        "MEASURED_V1_3A_ENVELOPE"
                        if primitive in CONTINUOUS
                        else "NOT_APPLICABLE"
                    ),

                "columns":[
                    "time",
                    "absoluteEnvelope",
                    "physicalDrive",
                ],

                "samples":
                    samples,

                "outsideCausalIntervalDrive":
                    0.0,
            },

            "attackDriveEvents":
                attack_drive,

            "trendAudit":
                trend_audit,

            "contracts":{
                "roleCodeUsedAsGain":
                    False,

                "visualEnergyCandidateUsedAsMeshHeight":
                    False,

                "inventedTrendRamp":
                    False,

                "elevationMappedToMeshY":
                    False,
            },
        })

    measured=[
        item
        for item in trends
        if item["measurement"]
        is not None
    ]

    energy_mismatch=0
    correlation_mismatch=0

    for item in measured:

        expected=(
            item[
                "expectedEnergyChangeDb"
            ]
        )

        actual=(
            item["measurement"][
                "measuredEnergyChangeDb"
            ]
        )

        expected_corr=(
            item[
                "expectedEnergyTimeCorrelation"
            ]
        )

        actual_corr=(
            item["measurement"][
                "measuredEnergyTimeCorrelation"
            ]
        )

        if (
            expected
            and actual
            and expected*actual<0
        ):
            energy_mismatch+=1

        if (
            expected_corr
            and actual_corr
            and expected_corr*actual_corr<0
        ):
            correlation_mismatch+=1

    summary={

        "behaviorCount":
            len(rows),

        "continuousBehaviorCount":
            sum(
                row["primitive"]
                in CONTINUOUS
                for row in rows
            ),

        "totalContinuousSamples":
            total_samples,

        "continuousWithoutSamplesCount":
            len(
                empty_continuous
            ),

        "totalAttackDriveEvents":
            total_attacks,

        "missingFeatureBehaviorCount":
            len(missing),

        "invalidAttackRefCount":
            len(invalid),

        "trendModifierCount":
            len(trends),

        "trendMeasuredCount":
            len(measured),

        "trendUnmeasuredCount":
            (
                len(trends)
                -
                len(measured)
            ),

        "trendEnergySignMismatchCount":
            energy_mismatch,

        "trendCorrelationSignMismatchCount":
            correlation_mismatch,

        "primitiveCounts":
            dict(
                sorted(
                    Counter(
                        row["primitive"]
                        for row in rows
                    ).items()
                )
            ),
    }

    if len(rows)!=505:
        raise RuntimeError(
            "behaviorCount="
            + str(len(rows))
        )

    if total_attacks!=10282:
        raise RuntimeError(
            "totalAttackDriveEvents="
            + str(total_attacks)
        )

    zero_required=(
        "continuousWithoutSamplesCount",
        "missingFeatureBehaviorCount",
        "invalidAttackRefCount",
        "trendUnmeasuredCount",
        "trendEnergySignMismatchCount",
        "trendCorrelationSignMismatchCount",
    )

    for key in zero_required:

        if summary[key]!=0:
            raise RuntimeError(
                f"{key}={summary[key]}"
            )

    payload={

        "schema":
            "laise-musical-dynamic-drive-v1",

        "version":
            "1.3C.1-lab",

        "duration":
            behavior_payload.get(
                "duration",
                cue_payload.get(
                    "duration",
                    330.0,
                ),
            ),

        "metadata":{

            "runtimeConsumer":
                None,

            "status":
                "LAB_ONLY_NOT_PRODUCTION",

            "method":
                (
                    "V1.3A measured absolute envelope "
                    "at 20 ms multiplied only by "
                    "existing bounded V1.3C "
                    "salience/local/track context "
                    "factors. Impulse and pulse drive "
                    "use absolute cue amplitude with "
                    "the same factors."
                ),

            "continuousEnvelope":
                (
                    "Centered 64 ms stereo-power RMS, "
                    "20 ms hop, 100 ms five-frame "
                    "smoothing inherited unchanged "
                    "from V1.3A."
                ),

            "contracts":{

                "roleCodeUsedAsGain":
                    False,

                "visualEnergyCandidateUsedAsMeshHeight":
                    False,

                "inventedTrendRamp":
                    False,

                "elevationMappedToMeshY":
                    False,

                "outsideCausalIntervalDrive":
                    0.0,

                "causalIntervalPolicy":
                    "START_INCLUSIVE_END_EXCLUSIVE",

                "headroomMappingImplemented":
                    False,
            },
        },

        "sourceHashes":{

            "behaviorArtifact":
                behavior_sha,

            "cueDataset":
                sha(CUES),

            "featureDatasets":
                dict(
                    sorted(
                        feature_hashes.items()
                    )
                ),
        },

        "summary":
            summary,

        "behaviors":
            rows,
    }

    encoded=(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")

    output.write_bytes(
        encoded
    )

    digest=hashlib.sha256(
        encoded
    ).hexdigest()

    print("STATUS=PASS")
    print(f"OUTPUT={output}")
    print(
        "OUTPUT_SHA256="
        + digest
    )

    for key,value in summary.items():
        if not isinstance(
            value,
            dict,
        ):
            print(
                f"{key}={value}"
            )

    print(
        "primitiveCounts="
        + json.dumps(
            summary[
                "primitiveCounts"
            ],
            sort_keys=True,
        )
    )

if __name__=="__main__":

    parser=argparse.ArgumentParser()

    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT,
    )

    args=parser.parse_args()

    build(
        args.output
    )
