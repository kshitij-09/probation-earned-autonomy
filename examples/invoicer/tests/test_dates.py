from datetime import date

from app.dates import due_date, is_overdue


def test_net_30_due_date():
    assert due_date(date(2026, 11, 1), 30) == date(2026, 12, 1)


def test_not_overdue_on_due_date():
    assert not is_overdue(date(2026, 11, 1), 30, today=date(2026, 12, 1))
