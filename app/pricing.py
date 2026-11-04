"""Line-item pricing helpers."""

from decimal import ROUND_HALF_UP, Decimal


def line_total(unit_price: Decimal, quantity: int) -> Decimal:
    """Price of one line before discounts."""
    return (unit_price * quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def apply_discount(amount: Decimal, percent: Decimal) -> Decimal:
    """Return ``amount`` reduced by ``percent`` (0-100), rounded to cents."""
    if percent < 0 or percent > 100:
        raise ValueError("percent must be between 0 and 100")
    discounted = amount * (Decimal(100) - percent) / Decimal(100)
    # BUG: truncates instead of rounding half-up to the nearest cent.
    return Decimal(int(discounted * 100)) / Decimal(100)


def invoice_total(
    lines: list[tuple[Decimal, int]], discount_percent: Decimal = Decimal(0)
) -> Decimal:
    subtotal = sum((line_total(p, q) for p, q in lines), Decimal(0))
    return apply_discount(subtotal, discount_percent)
