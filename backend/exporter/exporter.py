"""
backend/exporter/exporter.py
Exports generated data to SQL INSERT statements, CSV, and a combined seed_all.sql.
"""

import csv
import io
from datetime import datetime


def _sql_value(val) -> str:
    """Convert a Python value to a SQL literal string."""
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, (int, float)):
        return str(val)
    escaped = str(val).replace("'", "''")
    return f"'{escaped}'"


def export_sql(table_name: str, columns: list, data: list) -> str:
    """
    Generate SQL INSERT statements for a table.

    Returns:
        SQL string with one INSERT per row.
    """
    if not data:
        return f"-- No data generated for {table_name}\n"

    lines = [
        f"-- Generated test data for `{table_name}`",
        f"-- Generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"-- {len(data)} rows",
        ""
    ]

    col_list = ", ".join(f"`{c}`" for c in columns)

    for row in data:
        values = ", ".join(_sql_value(row.get(col)) for col in columns)
        lines.append(f"INSERT INTO `{table_name}` ({col_list}) VALUES ({values});")

    lines.append("")
    return "\n".join(lines)


def export_csv(table_name: str, columns: list, data: list) -> str:
    """
    Generate CSV content for a table.

    Returns:
        CSV string with header row.
    """
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=columns,
        extrasaction="ignore",
        lineterminator="\n"
    )
    writer.writeheader()
    for row in data:
        writer.writerow({col: row.get(col, "") for col in columns})
    return output.getvalue()


def export_seed_all(tables_output: list) -> str:
    """
    Combine all table SQL exports into a single seed_all.sql file.

    Args:
        tables_output: List of table result dicts (each has 'name' and 'sql').

    Returns:
        Combined SQL string.
    """
    header = [
        "-- ============================================================",
        "-- seed_all.sql — Combined test data seed file",
        f"-- Generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"-- Tables: {', '.join(t['name'] for t in tables_output)}",
        "-- ============================================================",
        "",
        "SET FOREIGN_KEY_CHECKS = 0;",
        ""
    ]

    sections = []
    for table in tables_output:
        sections.append(f"-- {'─' * 50}")
        sections.append(f"-- Table: {table['name']}")
        sections.append(f"-- {'─' * 50}")
        sections.append(table["sql"])

    footer = [
        "SET FOREIGN_KEY_CHECKS = 1;",
        ""
    ]

    return "\n".join(header + sections + footer)
