import os
import csv
import logging

logger = logging.getLogger(__name__)


# ----------------------------
# SQL SAFE FORMATTER
# ----------------------------
def format_sql_value(v):
    if v is None:
        return "NULL"
    elif isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    elif isinstance(v, (int, float)):
        return str(v)
    else:
        escaped = str(v).replace("'", "''")
        return f"'{escaped}'"


def escape_identifier(name: str) -> str:
    """
    Safely wrap SQL identifiers (table/column names).
    """
    return f'"{name}"'


# ----------------------------
# INSERT GENERATOR (OPTIMIZED)
# ----------------------------
def to_sql_inserts(table_name: str, rows: list) -> str:
    if not rows:
        return f"-- {table_name} (0 rows)\n"

    lines = [f"-- Data for {table_name}"]

    columns = list(rows[0].keys())
    col_str = ", ".join(escape_identifier(c) for c in columns)

    for row in rows:
        values = ", ".join(format_sql_value(row.get(c)) for c in columns)

        lines.append(
            f"INSERT INTO {escape_identifier(table_name)} ({col_str}) VALUES ({values});"
        )

    return "\n".join(lines)


# ----------------------------
# CSV SAFE WRITER
# ----------------------------
def write_csv(csv_path, rows):
    if not rows:
        return

    columns = list(rows[0].keys())

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=columns,
            quoting=csv.QUOTE_MINIMAL
        )

        writer.writeheader()

        for row in rows:
            clean_row = {
                k: ("" if v is None else v)
                for k, v in row.items()
            }
            writer.writerow(clean_row)


# ----------------------------
# MAIN EXPORT FUNCTION
# ----------------------------
def export_data(generated_data: dict, topo_order: list, output_dir: str):
    """
    Exports:
    - individual CSV files
    - individual SQL files
    - combined seed_all.sql
    """

    os.makedirs(output_dir, exist_ok=True)

    combined_sql = []

    for table_name in topo_order:
        rows = generated_data.get(table_name, [])

        if not rows:
            continue

        # ---------------- SQL ----------------
        sql_content = to_sql_inserts(table_name, rows)

        sql_path = os.path.join(output_dir, f"{table_name}.sql")
        with open(sql_path, "w", encoding="utf-8") as f:
            f.write(sql_content + "\n")

        combined_sql.append(sql_content)

        # ---------------- CSV ----------------
        csv_path = os.path.join(output_dir, f"{table_name}.csv")
        write_csv(csv_path, rows)

    # ---------------- COMBINED SQL ----------------
    combined_path = os.path.join(output_dir, "seed_all.sql")

    with open(combined_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(combined_sql))

    logger.info(f"Export completed. Files saved in: {output_dir}")
    print(f"Export completed. Files saved in: {output_dir}")