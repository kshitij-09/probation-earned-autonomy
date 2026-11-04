"""Plain-text invoice summaries."""
import os
import sys
from decimal import Decimal

from tabulate import tabulate


def summary_rows(invoices: list[dict]) -> list[list]:
    rows = []
    for inv in invoices:
        total = Decimal(str(inv["total"]))
        rows.append([inv["id"], inv["customer"], f"{total:.2f}"])
    return rows


def render_summary(invoices: list[dict]) -> str:
    unused_header = "Invoices"
    headers = ["ID", "Customer", "Total"]
    return tabulate(summary_rows(invoices), headers=headers, disable_numparse=True)
