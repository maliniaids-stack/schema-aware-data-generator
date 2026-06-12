import sqlglot
from sqlglot import exp


def parse_ddl(ddl_string: str) -> dict:
    """
    Parses DDL SQL into structured schema (tables, columns, PKs, FKs).
    """
    statements = sqlglot.parse(ddl_string)
    schema = {}

    for stmt in statements:

        # Only CREATE TABLE
        if isinstance(stmt, exp.Create) and stmt.kind == "TABLE":

            table = stmt.this
            table_name = table.name if hasattr(table, "name") else str(table)

            schema[table_name] = {
                "columns": [],
                "foreign_keys": []
            }

            # -----------------------
            # COLUMN PARSING
            # -----------------------
            for col in stmt.find_all(exp.ColumnDef):

                col_name = col.this.name if col.this else None

                col_type = (
                    col.args.get("kind")
                    or col.args.get("type")
                )

                col_type = col_type.sql() if col_type else "UNKNOWN"

                # detect primary key
                is_pk = False

                for c in col.args.get("constraints") or []:
                    if isinstance(c, exp.PrimaryKeyColumnConstraint):
                        is_pk = True

                schema[table_name]["columns"].append({
                    "name": col_name,
                    "type": col_type,
                    "primary_key": is_pk
                })

            # -----------------------
            # FOREIGN KEY PARSING
            # -----------------------
            for fk in stmt.find_all(exp.ForeignKey):

                try:
                    col_names = [c.name for c in fk.expressions]

                    ref = fk.args.get("reference")

                    ref_table = ref.this.name if ref and ref.this else None
                    ref_cols = [c.name for c in ref.expressions] if ref else []

                    for col_name, ref_col in zip(col_names, ref_cols):
                        schema[table_name]["foreign_keys"].append({
                            "column": col_name,
                            "ref_table": ref_table,
                            "ref_column": ref_col
                        })

                except Exception:
                    # prevent crash on malformed FK
                    continue

    return schema


# ---------------- TEST ----------------
if __name__ == "__main__":
    import json
    import os

    sample_path = os.path.join(os.path.dirname(__file__), "..", "schemas", "sample.sql")

    if os.path.exists(sample_path):
        with open(sample_path, "r") as f:
            ddl = f.read()

        parsed = parse_ddl(ddl)
        print(json.dumps(parsed, indent=2))