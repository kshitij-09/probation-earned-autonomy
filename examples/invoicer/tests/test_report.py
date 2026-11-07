from app.report import render_summary


def test_render_summary_contains_rows():
    out = render_summary([{"id": "INV-1", "customer": "Acme", "total": 12.5}])
    assert "INV-1" in out and "Acme" in out and "12.50" in out
