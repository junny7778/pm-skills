#!/usr/bin/env python3
"""Deterministic, dependency-free calculations for experiment design."""

from __future__ import annotations

import argparse
import json
import math
from statistics import NormalDist


def probability(value: str) -> float:
    number = float(value)
    if not 0 < number < 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return number


def positive(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return number


def csv_numbers(value: str) -> list[float]:
    try:
        numbers = [float(item.strip()) for item in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be comma-separated numbers") from exc
    if len(numbers) < 2 or any(number < 0 for number in numbers):
        raise argparse.ArgumentTypeError("must contain at least two non-negative numbers")
    return numbers


def z_values(alpha: float, power: float) -> tuple[float, float]:
    normal = NormalDist()
    return normal.inv_cdf(1 - alpha / 2), normal.inv_cdf(power)


def sample_size_proportion(
    baseline: float, mde: float, mde_type: str, alpha: float, power: float
) -> dict[str, float | int | str]:
    delta = baseline * mde if mde_type == "relative" else mde
    treatment = baseline + delta
    if not 0 < treatment < 1:
        raise ValueError("baseline plus MDE must be between 0 and 1")
    z_alpha, z_power = z_values(alpha, power)
    per_group = math.ceil(
        (z_alpha + z_power) ** 2
        * (baseline * (1 - baseline) + treatment * (1 - treatment))
        / delta**2
    )
    return {
        "method": "two-sided-normal-approximation-unpooled",
        "baseline": baseline,
        "treatment": treatment,
        "absolute_delta": delta,
        "mde_type": mde_type,
        "alpha": alpha,
        "power": power,
        "per_group": per_group,
        "total_two_groups": per_group * 2,
    }


def sample_size_mean(
    stddev: float, delta: float, alpha: float, power: float
) -> dict[str, float | int | str]:
    z_alpha, z_power = z_values(alpha, power)
    per_group = math.ceil(2 * (z_alpha + z_power) ** 2 * stddev**2 / delta**2)
    return {
        "method": "two-sided-two-sample-normal-approximation",
        "stddev": stddev,
        "absolute_delta": delta,
        "alpha": alpha,
        "power": power,
        "per_group": per_group,
        "total_two_groups": per_group * 2,
    }


def regularized_gamma_q(shape: float, value: float) -> float:
    """Regularized upper incomplete gamma Q(shape, value)."""
    if value < 0 or shape <= 0:
        raise ValueError("invalid gamma inputs")
    if value == 0:
        return 1.0
    epsilon, tiny, max_iterations = 1e-14, 1e-300, 1000
    if value < shape + 1:
        term = total = 1 / shape
        current = shape
        for _ in range(max_iterations):
            current += 1
            term *= value / current
            total += term
            if abs(term) < abs(total) * epsilon:
                lower = total * math.exp(-value + shape * math.log(value) - math.lgamma(shape))
                return max(0.0, min(1.0, 1 - lower))
        raise ArithmeticError("gamma series did not converge")

    b = value + 1 - shape
    c = 1 / tiny
    d = 1 / b
    fraction = d
    for index in range(1, max_iterations + 1):
        coefficient = -index * (index - shape)
        b += 2
        d = coefficient * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + coefficient / c
        if abs(c) < tiny:
            c = tiny
        d = 1 / d
        change = d * c
        fraction *= change
        if abs(change - 1) < epsilon:
            result = math.exp(-value + shape * math.log(value) - math.lgamma(shape)) * fraction
            return max(0.0, min(1.0, result))
    raise ArithmeticError("gamma continued fraction did not converge")


def srm(observed: list[float], expected: list[float], threshold: float) -> dict[str, object]:
    if len(observed) != len(expected):
        raise ValueError("observed and expected must have the same number of groups")
    total_observed, total_weight = sum(observed), sum(expected)
    if total_observed <= 0 or total_weight <= 0 or any(weight <= 0 for weight in expected):
        raise ValueError("observed total and every expected weight must be greater than 0")
    expected_ratios = [weight / total_weight for weight in expected]
    expected_counts = [total_observed * ratio for ratio in expected_ratios]
    chi_square = sum((actual - target) ** 2 / target for actual, target in zip(observed, expected_counts))
    degrees_of_freedom = len(observed) - 1
    p_value = regularized_gamma_q(degrees_of_freedom / 2, chi_square / 2)
    return {
        "method": "chi-square-goodness-of-fit",
        "observed": observed,
        "expected_ratios": expected_ratios,
        "expected_counts": expected_counts,
        "chi_square": chi_square,
        "degrees_of_freedom": degrees_of_freedom,
        "p_value": p_value,
        "threshold": threshold,
        "srm_failed": p_value < threshold,
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    proportion = commands.add_parser("sample-size-proportion")
    proportion.add_argument("--baseline", type=probability, required=True)
    proportion.add_argument("--mde", type=positive, required=True)
    proportion.add_argument("--mde-type", choices=("relative", "absolute"), default="relative")
    proportion.add_argument("--alpha", type=probability, default=0.05)
    proportion.add_argument("--power", type=probability, default=0.8)

    mean = commands.add_parser("sample-size-mean")
    mean.add_argument("--stddev", type=positive, required=True)
    mean.add_argument("--delta", type=positive, required=True)
    mean.add_argument("--alpha", type=probability, default=0.05)
    mean.add_argument("--power", type=probability, default=0.8)

    srm_parser = commands.add_parser("srm")
    srm_parser.add_argument("--observed", type=csv_numbers, required=True)
    srm_parser.add_argument("--expected", type=csv_numbers, required=True)
    srm_parser.add_argument("--threshold", type=probability, default=0.01)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "sample-size-proportion":
            result = sample_size_proportion(args.baseline, args.mde, args.mde_type, args.alpha, args.power)
        elif args.command == "sample-size-mean":
            result = sample_size_mean(args.stddev, args.delta, args.alpha, args.power)
        else:
            result = srm(args.observed, args.expected, args.threshold)
    except (ValueError, ArithmeticError) as exc:
        parser().error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
