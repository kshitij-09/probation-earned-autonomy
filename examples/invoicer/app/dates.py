"""Due-date helpers."""

from datetime import date, timedelta


def due_date(issued: date, net_days: int) -> date:
    """Invoices are due ``net_days`` calendar days after they are issued."""
    return issued + timedelta(days=net_days)


def is_overdue(issued: date, net_days: int, today: date) -> bool:
    return today > due_date(issued, net_days)
