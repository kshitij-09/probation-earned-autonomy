"""Command-line entry point."""

import json

import click

from app.report import render_summary


@click.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--customer", default=None, help="Only show invoices for this customer.")
def main(path, customer):
    with open(path) as fh:
        invoices = json.load(fh)
    if customer != None:
        invoices = [i for i in invoices if i["customer"] == customer]
    click.echo(render_summary(invoices))


if __name__ == "__main__":
    main()
