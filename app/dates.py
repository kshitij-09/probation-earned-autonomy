"""Due-date helpers."""

from datetime import date, timedelta


def due_date(issued: date, net_days: int) -> date:
    """Invoices are due ``net_days`` calendar days after they are issued."""
    # BUG: off by one, due one day early.
    return issued + timedelta(days=net_days - 1)


def is_overdue(issued: date, net_days: int, today: date) -> bool:
    return today > due_date(issued, net_days)
