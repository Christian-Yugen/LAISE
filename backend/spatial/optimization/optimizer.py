from __future__ import annotations

import math
from collections import Counter

import numpy as np

from human_prior import prior_score


def acoustic_score(features, dry_reference):
    if not features["finite"] or not features["no_clipping"]:
        return -1e9

    balance = math.exp(-abs(features["ild_db"]) / 1.5)
    itd = math.exp(-abs(features["itd_us"]) / 120.0)
    spectral = math.exp(
        -abs(
            features["spectral_centroid_hz"]
            - dry_reference["spectral_centroid_hz"]
        )
        / 1800.0
    )
    decorrelation = min(
        abs(
            features["lr_correlation"]
            - dry_reference["lr_correlation"]
        )
        / 0.25,
        1.0,
    )

    return float(
        0.30 * balance
        + 0.20 * itd
        + 0.20 * spectral
        + 0.30 * decorrelation
    )


def score(candidate, features, dry_reference):
    acoustic = acoustic_score(features, dry_reference)
    human = prior_score(candidate)
    combined = 0.60 * acoustic + 0.40 * human
    return float(combined), float(acoustic), float(human)


def _gain_value(candidate):
    value = candidate.get("reflection_gain_db")
    return -30.0 if value is None else float(value)


def descriptor(record):
    """
    Descriptor used only for diversity.

    It combines parameter-space and acoustic-space information.
    The scales are deliberately engineering scales, not a claim that
    Euclidean distance equals human perceptual distance.
    """
    c = record["candidate"]
    f = record["features"]

    return np.array(
        [
            (float(c["distance_m"]) - 0.75) / 5.25,
            (_gain_value(c) + 24.0) / 24.0,
            float(f["ild_db"]) / 2.0,
            float(f["itd_us"]) / 250.0,
            float(f["lr_correlation"]),
            float(f["side_mid_ratio"]),
            float(f["spectral_centroid_hz"]) / 12000.0,
            float(f["hf_ratio_above_4khz"]),
        ],
        dtype=float,
    )


def descriptor_distance(a, b):
    return float(np.linalg.norm(descriptor(a) - descriptor(b)))


def cluster(records):
    """
    Backward-compatible deterministic reduction used by T001-N v1.0/v1.1.

    Keeps the highest-scoring representative in each coarse parameter /
    acoustic cell.
    """
    cells = {}

    for record in records:
        if record["candidate"]["family"] != "early_reflection":
            continue

        c = record["candidate"]
        f = record["features"]

        key = (
            round(float(c["distance_m"]) * 2.0) / 2.0,
            round(float(c["reflection_gain_db"]) / 4.0) * 4.0,
            round(float(f["lr_correlation"]) * 12.0) / 12.0,
            round(float(f["side_mid_ratio"]) * 12.0) / 12.0,
        )

        previous = cells.get(key)
        if (
            previous is None
            or record["combined_score"] > previous["combined_score"]
        ):
            cells[key] = record

    return list(cells.values())


def _normalized_score(record, lo, hi):
    if hi <= lo:
        return 1.0
    return (float(record["combined_score"]) - lo) / (hi - lo)


def _distance_bucket(distance_m):
    """
    Fine buckets around the known ~3 m region, while preserving exploration.
    """
    d = float(distance_m)
    if d < 2.4:
        return "explore_near"
    if d < 2.8:
        return "lower_frontal"
    if d < 3.0:
        return "near_3m_low"
    if d <= 3.0:
        return "3m_anchor"
    if d <= 3.3:
        return "near_3m_high"
    return "explore_far"


def select_v11(
    records,
    n=8,
    pool_size=56,
    max_per_exact_distance=2,
    min_same_distance_gain_gap_db=6.0,
    min_descriptor_distance=0.035,
    min_unique_distances=4,
    min_distance_span_m=0.6,
):
    """
    T001-N v1.1 selection.

    Goals:
      * preserve strong exploitation near the discovered ~3 m region;
      * prevent five nearly identical 3.0 m candidates;
      * require actual parameter/acoustic separation;
      * preserve exploration outside the single best distance.

    Returns:
        (selected, diagnostics)
    """
    eligible = [
        r
        for r in records
        if r["candidate"]["family"] == "early_reflection"
        and r["features"]["finite"]
        and r["features"]["no_clipping"]
    ]

    eligible = sorted(
        eligible,
        key=lambda r: r["combined_score"],
        reverse=True,
    )[:pool_size]

    if len(eligible) < n:
        raise RuntimeError(
            f"Not enough eligible candidates: {len(eligible)} < {n}"
        )

    values = [float(r["combined_score"]) for r in eligible]
    lo, hi = min(values), max(values)

    selected = []
    rejected_reasons = Counter()

    def compatible(candidate, current, strict=True):
        c = candidate["candidate"]
        same_distance = [
            s for s in current
            if abs(
                float(s["candidate"]["distance_m"])
                - float(c["distance_m"])
            ) < 1e-9
        ]

        if len(same_distance) >= max_per_exact_distance:
            return False, "max_per_exact_distance"

        for other in same_distance:
            gap = abs(
                _gain_value(c)
                - _gain_value(other["candidate"])
            )
            if gap < min_same_distance_gain_gap_db:
                return False, "same_distance_gain_gap"

        if strict and current:
            minimum = min(
                descriptor_distance(candidate, other)
                for other in current
            )
            if minimum < min_descriptor_distance:
                return False, "descriptor_distance"

        return True, None

    def utility(candidate, current):
        score_term = _normalized_score(candidate, lo, hi)

        if not current:
            diversity_term = 1.0
        else:
            minimum = min(
                descriptor_distance(candidate, other)
                for other in current
            )
            diversity_term = min(minimum / 0.25, 1.0)

        distance_novelty = (
            1.0
            if all(
                abs(
                    float(candidate["candidate"]["distance_m"])
                    - float(s["candidate"]["distance_m"])
                ) > 1e-9
                for s in current
            )
            else 0.0
        )

        bucket = _distance_bucket(candidate["candidate"]["distance_m"])
        bucket_novelty = (
            1.0
            if all(
                _distance_bucket(s["candidate"]["distance_m"]) != bucket
                for s in current
            )
            else 0.0
        )

        return (
            0.55 * score_term
            + 0.25 * diversity_term
            + 0.10 * distance_novelty
            + 0.10 * bucket_novelty
        )

    # 1) Anchor: strongest candidate.
    selected.append(eligible[0])

    # 2) Coverage pass: favor previously unused distance buckets.
    buckets = [
        "near_3m_low",
        "3m_anchor",
        "near_3m_high",
        "lower_frontal",
        "explore_near",
        "explore_far",
    ]

    for bucket in buckets:
        if len(selected) >= n:
            break
        if any(
            _distance_bucket(s["candidate"]["distance_m"]) == bucket
            for s in selected
        ):
            continue

        options = [
            r for r in eligible
            if r not in selected
            and _distance_bucket(r["candidate"]["distance_m"]) == bucket
        ]
        options.sort(
            key=lambda r: utility(r, selected),
            reverse=True,
        )

        for candidate in options:
            ok, reason = compatible(candidate, selected, strict=True)
            if ok:
                selected.append(candidate)
                break
            rejected_reasons[reason] += 1

    # 3) Fill with strict diversity.
    remaining = [r for r in eligible if r not in selected]
    while remaining and len(selected) < n:
        ranked = sorted(
            remaining,
            key=lambda r: utility(r, selected),
            reverse=True,
        )

        added = False
        for candidate in ranked:
            ok, reason = compatible(candidate, selected, strict=True)
            if ok:
                selected.append(candidate)
                remaining.remove(candidate)
                added = True
                break
            rejected_reasons[reason] += 1
            remaining.remove(candidate)

        if not added and not remaining:
            break

    # 4) Controlled fallback: keep hard distance/gain caps, relax only
    # descriptor threshold if the strict pass cannot reach 8.
    if len(selected) < n:
        remaining = [r for r in eligible if r not in selected]
        while remaining and len(selected) < n:
            ranked = sorted(
                remaining,
                key=lambda r: utility(r, selected),
                reverse=True,
            )
            added = False
            for candidate in ranked:
                ok, reason = compatible(candidate, selected, strict=False)
                if ok:
                    selected.append(candidate)
                    remaining.remove(candidate)
                    added = True
                    break
                rejected_reasons[reason] += 1
                remaining.remove(candidate)
            if not added and not remaining:
                break

    distances = [
        float(r["candidate"]["distance_m"])
        for r in selected
    ]
    counts = Counter(distances)

    pairwise = []
    for i in range(len(selected)):
        for j in range(i + 1, len(selected)):
            pairwise.append(
                descriptor_distance(selected[i], selected[j])
            )

    diagnostics = {
        "selected_count": len(selected),
        "unique_distances": len(set(distances)),
        "distance_span_m": (
            max(distances) - min(distances)
            if distances else 0.0
        ),
        "max_candidates_same_distance": (
            max(counts.values()) if counts else 0
        ),
        "minimum_pairwise_descriptor_distance": (
            min(pairwise) if pairwise else None
        ),
        "distance_counts": {
            str(k): v for k, v in sorted(counts.items())
        },
        "rejected_reasons": dict(rejected_reasons),
        "gates": {
            "eight_finalists": len(selected) == n,
            "max_two_per_exact_distance": (
                max(counts.values(), default=0)
                <= max_per_exact_distance
            ),
            "at_least_four_unique_distances": (
                len(set(distances)) >= min_unique_distances
            ),
            "distance_span_at_least_0_6m": (
                (max(distances) - min(distances))
                >= min_distance_span_m
                if distances else False
            ),
            "unique_parameter_pairs": (
                len({
                    (
                        r["candidate"]["distance_m"],
                        r["candidate"]["reflection_gain_db"],
                    )
                    for r in selected
                })
                == len(selected)
            ),
        },
    }

    return selected, diagnostics


# Backward-compatible name for any existing code importing select().
def select(records, n=8, pool=56):
    selected, _ = select_v11(
        records,
        n=n,
        pool_size=pool,
    )
    return selected
