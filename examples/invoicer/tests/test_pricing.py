from decimal import Decimal

import pytest

from app.pricing import apply_discount, invoice_total, line_total


def test_line_total():
    assert line_total(Decimal("19.99"), 3) == Decimal("59.97")


def test_discount_rounds_half_up_to_cents():
    # 10.05 * 0.85 = 8.5425 -> 8.54; 0.99 * 0.5 = 0.495 -> 0.50
    assert apply_discount(Decimal("10.05"), Decimal(15)) == Decimal("8.54")
    assert apply_discount(Decimal("0.99"), Decimal(50)) == Decimal("0.50")


def test_discount_rejects_bad_percent():
    with pytest.raises(ValueError):
        apply_discount(Decimal(10), Decimal(101))


def test_invoice_total_with_discount():
    lines = [(Decimal("4.99"), 3), (Decimal("1.25"), 1)]
    assert invoice_total(lines, Decimal(10)) == Decimal("14.60")
