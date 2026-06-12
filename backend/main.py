import os
import click
from dotenv import load_dotenv

from backend.parser.ddl_parser import parse_ddl
from backend.mapper.llm_mapper import get_or_build_column_map
from backend.generator.data_generator import build_order, generate_data
from backend.exporter.exporter import export_data

load_dotenv()


@click.command()
@click.option("--ddl", required=True, type=click.Path(exists=True))
@click.option("--rows", default=20, type=int)
@click.option("--output", default="output/", type=click.Path())
def run(ddl, rows, output):

    try:
        click.echo("[*] Reading DDL...")
        with open(ddl, "r") as f:
            ddl_content = f.read()

        click.echo("[*] Parsing schema...")
        schema = parse_ddl(ddl_content)

        click.echo("[*] LLM mapping columns...")
        column_map, tokens_used = get_or_build_column_map(schema)

        click.echo("[*] Building table order...")
        topo_order = build_order(schema)

        click.echo(f"    Order: {' -> '.join(topo_order)}")

        click.echo(f"[*] Generating {rows} rows...")
        generated = generate_data(schema, column_map, topo_order, num_rows=rows)

        click.echo("[*] Exporting files...")
        export_data(generated, topo_order, output)

        click.echo(click.style(f"[+] Done! Output → {output}", fg="green"))

    except Exception as e:
        click.echo(click.style(f"[ERROR] {e}", fg="red"))


if __name__ == "__main__":
    run()