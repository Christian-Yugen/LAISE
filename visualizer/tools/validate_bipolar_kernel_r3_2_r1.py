import math


N = 400_000
QMAX = 25.0
STEP = QMAX / N

C = 0.7889649461827104
SIGMA = 0.22


def kernel(q):

    if q <= 2.0:

        return (
            (1.0 - q / 2.0)
            * math.exp(-q / 2.0)
        )

    r = math.sqrt(q)

    return (
        -C
        * (
            r - math.sqrt(2.0)
        )
        * math.exp(
            -(
                (
                    r - 2.0
                ) / SIGMA
            ) ** 2
        )
    )


values = [
    kernel(
        i * STEP
    )
    for i in range(
        N + 1
    )
]


crest = max(values)
trough = min(values)

ratio = (
    abs(trough)
    / crest
)


signed_integral = (
    STEP
    * (
        0.5 * values[0]
        + sum(
            values[1:-1]
        )
        + 0.5 * values[-1]
    )
)


print(
    "CREST=",
    crest
)

print(
    "TROUGH=",
    trough
)

print(
    "TROUGH_TO_CREST=",
    ratio
)

print(
    "SIGNED_RADIAL_INTEGRAL=",
    signed_integral
)


assert abs(
    crest - 1.0
) < 1e-12

assert (
    0.47
    < ratio
    < 0.49
)

assert abs(
    signed_integral
) < 1e-6


print(
    "R3_2_MORPHOLOGY_GATE=PASS"
)
