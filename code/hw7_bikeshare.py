"""Deterministic bike-share cost recommendation over MRKL tool outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Recommendation:
    decision: str
    pay_per_use: float
    membership: float
    break_even_rides: float
    rationale: str
    assumptions: list[str]

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def recommend(
    ride_count: int,
    total_minutes: float,
    membership_price: float,
    unlock_fee: float,
    per_minute: float,
    included_minutes: float = 0,
) -> dict[str, Any]:
    pay = ride_count * unlock_fee + total_minutes * per_minute
    residual = max(0.0, total_minutes - included_minutes) * per_minute
    monthly = membership_price + residual
    break_even = (
        membership_price / (unlock_fee + (total_minutes / ride_count) * per_minute)
        if ride_count
        else 0.0
    )
    decision = "Buy Monthly Membership" if monthly <= pay else "Pay Per Ride/Minute"
    result = Recommendation(
        decision=decision,
        pay_per_use=round(pay, 2),
        membership=round(monthly, 2),
        break_even_rides=round(break_even, 2),
        rationale=(
            f"Pay-per-use costs ${pay:.2f}; membership plus residual charges costs ${monthly:.2f}. "
            f"The recommendation is {decision} based on the supplied trip totals "
            "and pricing inputs."
        ),
        assumptions=[
            "Trip durations and pricing fields are interpreted in minutes and USD.",
            "Missing fees are not invented.",
        ],
    )
    return result.as_dict()
