from __future__ import annotations
import math

def _closeness(value, target, scale):
    return math.exp(-abs(value - target) / scale)

def score_candidate(features, reference_features):
    """
    ACOUSTIC CANDIDATE SCORE — not a perceptual externalization prediction.

    It rewards:
      - numerical validity / no clipping
      - approximate L/R balance
      - low ITD for a central FRONT target
      - reflection-induced departure from the dry FRONT control
      - spectral preservation relative to the dry control
    """
    if (
        not features["finite"]
        or not features["no_clipping"]
        or features["rms"] <= 1e-7
    ):
        return -1e9, {"rejected": True}

    balance = _closeness(features["ild_db"], 0.0, 1.5)
    itd_center = _closeness(features["itd_us"], 0.0, 120.0)
    spectral_preservation = _closeness(
        features["spectral_centroid_hz"],
        reference_features["spectral_centroid_hz"],
        1800.0,
    )

    decorrelation_delta = abs(
        features["lr_correlation"] - reference_features["lr_correlation"]
    )
    decorrelation_signal = min(decorrelation_delta / 0.25, 1.0)

    score = (
        0.30 * balance
        + 0.20 * itd_center
        + 0.20 * spectral_preservation
        + 0.30 * decorrelation_signal
    )

    return float(score), {
        "rejected": False,
        "balance": balance,
        "itd_center": itd_center,
        "spectral_preservation": spectral_preservation,
        "decorrelation_signal": decorrelation_signal,
    }


def _best(records):
    return max(records, key=lambda r: r["acoustic_candidate_score"]) if records else None


def select_exploration_exploitation(records, top_n=8):
    """
    T001-M v0.2 selection policy.

    EXPLOITATION:
      Select the best candidate at 3 m, because T001-L independently
      identified the 3 m reflection family as promising.

    EXPLORATION:
      Select the best candidate at each other tested reflected distance
      (0.75, 1, 1.5, 2, 4 m), so human listening teaches us whether the
      apparent 3 m optimum is real or only an artifact of the heuristic.

    CONTROLS:
      Include dry FRONT controls at 1 m and 3 m.

    Result = 8 candidates:
      6 reflected distance representatives + 2 dry controls.

    This intentionally sacrifices raw top-score ranking in exchange for
    experimental information gain and parameter-space coverage.
    """
    reflected = [r for r in records if r["candidate"]["family"] == "early_reflection"]
    dry = [r for r in records if r["candidate"]["family"] == "dry_control"]

    selected = []

    # One best reflected representative for every tested distance.
    for distance in [0.75, 1.0, 1.5, 2.0, 3.0, 4.0]:
        pool = [
            r for r in reflected
            if abs(r["candidate"]["distance_m"] - distance) < 1e-9
        ]
        winner = _best(pool)
        if winner is not None:
            selected.append(winner)

    # Two anchors already known from T001-L.
    for distance in [1.0, 3.0]:
        pool = [
            r for r in dry
            if abs(r["candidate"]["distance_m"] - distance) < 1e-9
        ]
        winner = _best(pool)
        if winner is not None:
            selected.append(winner)

    # Defensive fallback only if the search space changes in the future.
    if len(selected) < top_n:
        used = {r["candidate"]["candidate_id"] for r in selected}
        remaining = sorted(
            [r for r in records if r["candidate"]["candidate_id"] not in used],
            key=lambda r: r["acoustic_candidate_score"],
            reverse=True,
        )
        selected.extend(remaining[: top_n - len(selected)])

    return selected[:top_n]


def shortlist_diagnostics(shortlist):
    distances = [r["candidate"]["distance_m"] for r in shortlist]
    families = [r["candidate"]["family"] for r in shortlist]
    reflected = [
        r for r in shortlist
        if r["candidate"]["family"] == "early_reflection"
    ]

    reflected_distances = sorted({
        r["candidate"]["distance_m"] for r in reflected
    })

    return {
        "count": len(shortlist),
        "unique_distances": sorted(set(distances)),
        "unique_distance_count": len(set(distances)),
        "families": sorted(set(families)),
        "has_reflected_candidates": any(f == "early_reflection" for f in families),
        "has_dry_controls": any(f == "dry_control" for f in families),
        "reflected_distance_coverage": reflected_distances,
        "reflected_distance_coverage_count": len(reflected_distances),
        "passes_diversity_gate": (
            len(shortlist) == 8
            and len(reflected_distances) >= 6
            and any(f == "dry_control" for f in families)
        ),
    }
