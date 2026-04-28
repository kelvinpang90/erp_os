"""Costing service — pure functions for inventory cost computations.

All cost math lives here so it can be unit-tested without a DB session.
The Inventory service then composes these functions with persistence logic.

Reference: CLAUDE.md Part 7 — 加权平均成本.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# 4-decimal quantizer (matches Numeric(18,4) DB precision)
_FOUR = Decimal("0.0001")


def compute_weighted_average(
    current_qty: Decimal,
    current_avg_cost: Decimal,
    incoming_qty: Decimal,
    incoming_unit_cost: Decimal,
) -> Decimal:
    """Compute the new weighted-average cost after an inbound stock movement.

    Formula::

        new_avg = (current_qty * current_avg + incoming_qty * incoming_unit_cost)
                  / (current_qty + incoming_qty)

    Special cases:
    * current_qty == 0  → new_avg equals incoming_unit_cost (no prior stock).
    * incoming_qty == 0 → unchanged (returns current_avg_cost).
    * total qty == 0 after both → returns Decimal("0") (degenerate).

    All arithmetic uses Decimal to avoid float drift; result is quantized to
    4 decimal places using ROUND_HALF_UP.

    Args:
        current_qty: Current on-hand quantity (>= 0).
        current_avg_cost: Current weighted-average unit cost (>= 0).
        incoming_qty: Quantity being received (>= 0).
        incoming_unit_cost: Unit cost of the incoming batch (>= 0).

    Returns:
        New weighted-average unit cost, quantized to 4 decimals.

    Raises:
        ValueError: if any input is negative.
    """
    if current_qty < 0 or incoming_qty < 0:
        raise ValueError("Quantities must be non-negative.")
    if current_avg_cost < 0 or incoming_unit_cost < 0:
        raise ValueError("Costs must be non-negative.")

    if incoming_qty == 0:
        return current_avg_cost.quantize(_FOUR, rounding=ROUND_HALF_UP)

    total_qty = current_qty + incoming_qty
    if total_qty == 0:
        return Decimal("0").quantize(_FOUR, rounding=ROUND_HALF_UP)

    if current_qty == 0:
        return incoming_unit_cost.quantize(_FOUR, rounding=ROUND_HALF_UP)

    numerator = current_qty * current_avg_cost + incoming_qty * incoming_unit_cost
    new_avg = numerator / total_qty
    return new_avg.quantize(_FOUR, rounding=ROUND_HALF_UP)
