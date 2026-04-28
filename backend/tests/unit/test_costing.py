"""Unit tests for the costing pure functions (Window 8).

Validates the weighted-average cost formula against the four key scenarios
defined in CLAUDE.md Part 7.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.costing import compute_weighted_average


class TestWeightedAverageCost:
    """Coverage matrix for compute_weighted_average."""

    # ── Scenario 1: opening stock (current_qty == 0) ─────────────────────────

    def test_first_receipt_when_stock_is_empty(self) -> None:
        """When on_hand is 0, the new avg cost equals incoming unit cost."""
        result = compute_weighted_average(
            current_qty=Decimal("0"),
            current_avg_cost=Decimal("0"),
            incoming_qty=Decimal("100"),
            incoming_unit_cost=Decimal("12.50"),
        )
        assert result == Decimal("12.5000")

    def test_first_receipt_ignores_stale_avg_cost_when_qty_zero(self) -> None:
        """If qty is 0, any leftover avg_cost should be replaced (not blended)."""
        result = compute_weighted_average(
            current_qty=Decimal("0"),
            current_avg_cost=Decimal("99.9999"),  # stale
            incoming_qty=Decimal("50"),
            incoming_unit_cost=Decimal("10"),
        )
        assert result == Decimal("10.0000")

    # ── Scenario 2: incremental purchase (typical case) ──────────────────────

    def test_incremental_purchase_blends_costs(self) -> None:
        """Normal blend: 100 @ 10.00 + 50 @ 16.00 → (1000 + 800) / 150 = 12.0000."""
        result = compute_weighted_average(
            current_qty=Decimal("100"),
            current_avg_cost=Decimal("10.0000"),
            incoming_qty=Decimal("50"),
            incoming_unit_cost=Decimal("16.0000"),
        )
        assert result == Decimal("12.0000")

    def test_equal_blend(self) -> None:
        """Equal qty + same cost → avg unchanged."""
        result = compute_weighted_average(
            current_qty=Decimal("80"),
            current_avg_cost=Decimal("5.5000"),
            incoming_qty=Decimal("80"),
            incoming_unit_cost=Decimal("5.5000"),
        )
        assert result == Decimal("5.5000")

    # ── Scenario 3: zero-cost incoming (free sample / promotion) ─────────────

    def test_zero_unit_cost_dilutes_avg(self) -> None:
        """Receiving free goods dilutes the avg cost proportionally."""
        # 100 @ 10.00 + 100 @ 0.00 = 1000 / 200 = 5.0000
        result = compute_weighted_average(
            current_qty=Decimal("100"),
            current_avg_cost=Decimal("10"),
            incoming_qty=Decimal("100"),
            incoming_unit_cost=Decimal("0"),
        )
        assert result == Decimal("5.0000")

    def test_zero_qty_incoming_keeps_current_avg(self) -> None:
        """No actual receipt → avg unchanged (degenerate guard)."""
        result = compute_weighted_average(
            current_qty=Decimal("100"),
            current_avg_cost=Decimal("7.3500"),
            incoming_qty=Decimal("0"),
            incoming_unit_cost=Decimal("999"),
        )
        assert result == Decimal("7.3500")

    # ── Scenario 4: precision boundary (4-decimal rounding) ──────────────────

    def test_rounding_half_up_4_decimals(self) -> None:
        """Result should be quantized to 4 decimals using ROUND_HALF_UP."""
        # 3 @ 1.0000 + 1 @ 1.00009 = 4.00009 / 4 = 1.0000225 → 1.0000 (rounds down)
        result = compute_weighted_average(
            current_qty=Decimal("3"),
            current_avg_cost=Decimal("1.0000"),
            incoming_qty=Decimal("1"),
            incoming_unit_cost=Decimal("1.00009"),
        )
        assert result == Decimal("1.0000")

    def test_rounding_half_up_rounds_up_at_5(self) -> None:
        """Verify that half rounds up, not banker's rounding."""
        # 1 @ 1.00005 incoming, no prior stock
        result = compute_weighted_average(
            current_qty=Decimal("0"),
            current_avg_cost=Decimal("0"),
            incoming_qty=Decimal("1"),
            incoming_unit_cost=Decimal("1.00005"),
        )
        assert result == Decimal("1.0001")  # 1.00005 → 1.0001 with ROUND_HALF_UP

    # ── Validation guards ────────────────────────────────────────────────────

    @pytest.mark.parametrize(
        "current_qty,current_avg,inc_qty,inc_cost",
        [
            (Decimal("-1"), Decimal("0"), Decimal("0"), Decimal("0")),
            (Decimal("0"), Decimal("-1"), Decimal("0"), Decimal("0")),
            (Decimal("0"), Decimal("0"), Decimal("-1"), Decimal("0")),
            (Decimal("0"), Decimal("0"), Decimal("0"), Decimal("-1")),
        ],
    )
    def test_negative_inputs_raise(
        self,
        current_qty: Decimal,
        current_avg: Decimal,
        inc_qty: Decimal,
        inc_cost: Decimal,
    ) -> None:
        with pytest.raises(ValueError):
            compute_weighted_average(current_qty, current_avg, inc_qty, inc_cost)

    def test_both_quantities_zero_returns_zero(self) -> None:
        """Defensive: both current and incoming are 0 → result is 0."""
        result = compute_weighted_average(
            current_qty=Decimal("0"),
            current_avg_cost=Decimal("0"),
            incoming_qty=Decimal("0"),
            incoming_unit_cost=Decimal("0"),
        )
        assert result == Decimal("0.0000")
