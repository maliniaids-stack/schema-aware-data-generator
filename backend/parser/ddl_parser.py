"""
backend/parser/ddl_parser.py
Parses SQL DDL into a structured schema dictionary using sqlglot.
Falls back to regex parsing for non-standard dialects.
"""

import re
import sqlglot
from sqlglot import exp


def parse_ddl(ddl: str) -> dict:
    """
    Parse SQL DDL string into a structured schema.

    Returns:
        {
          "table_name": {
            "columns": [
              {
                "name": str,
                "type": str,
                "nullable": bool,
                "primary_key": bool,
                "foreign_key": {"table": str, "column": str} | None,
                "unique": bool,
                "max_length": int | None
              }
            ]
          }
        }
    """
    schema = {}

    try:
        statements = sqlglot.parse(ddl, error_level=sqlglot.ErrorLevel.IGNORE)
    except Exception:
        return _regex_fallback_parse(ddl)

    for statement in statements:
        if statement is None:
            continue
        if not isinstance(statement, exp.Create):
            continue

        table_expr = statement.find(exp.Table)
        if not table_expr:
            continue

        table_name = table_expr.name.lower()
        if not table_name:
            continue

        schema[table_name] = {"columns": []}

        # Collect table-level FK constraints first
        table_fks = {}  # column_name -> {"table": ..., "column": ...}

        schema_expr = statement.find(exp.Schema)
        if schema_expr:
            for expr in schema_expr.expressions:
                if isinstance(expr, exp.ForeignKey):
                    fk_cols = [ident.name.lower() for ident in expr.args.get("expressions", [])]
                    refs = expr.args.get("reference")
                    if refs and fk_cols:
                        ref_schema = refs.args.get("this")
                        if ref_schema:
                            ref_table_node = ref_schema.args.get("this")
                            ref_table = ref_table_node.name.lower() if ref_table_node else ""
                            ref_col_nodes = ref_schema.args.get("expressions", [])
                            ref_col = ref_col_nodes[0].name.lower() if ref_col_nodes else "id"
                        else:
                            ref_table_node = refs.find(exp.Table)
                            ref_table = ref_table_node.name.lower() if ref_table_node else ""
                            ref_col = "id"
                        if ref_table:
                            for col in fk_cols:
                                table_fks[col] = {"table": ref_table, "column": ref_col}

        # Parse column definitions
        if schema_expr:
            for expr in schema_expr.expressions:
                if not isinstance(expr, exp.ColumnDef):
                    continue

                col_name = expr.name.lower()
                col_type = _extract_type(expr)
                max_length = _extract_max_length(expr)

                is_pk = bool(expr.find(exp.PrimaryKeyColumnConstraint))
                is_unique = bool(expr.find(exp.UniqueColumnConstraint))
                is_not_null = bool(expr.find(exp.NotNullColumnConstraint))
                is_nullable = not is_pk and not is_not_null

                # Column-level FK
                fk_info = None
                inline_fk = expr.find(exp.Reference)
                if inline_fk:
                    ref_table_e = inline_fk.find(exp.Table)
                    ref_col_e = inline_fk.find(exp.Column)
                    if ref_table_e:
                        fk_info = {
                            "table": ref_table_e.name.lower(),
                            "column": ref_col_e.name.lower() if ref_col_e else "id"
                        }

                # Table-level FK overrides if column-level not found
                if not fk_info and col_name in table_fks:
                    fk_info = table_fks[col_name]

                schema[table_name]["columns"].append({
                    "name": col_name,
                    "type": col_type,
                    "nullable": is_nullable,
                    "primary_key": is_pk,
                    "foreign_key": fk_info,
                    "unique": is_unique or is_pk,
                    "max_length": max_length
                })

    # If sqlglot didn't extract anything meaningful, try regex fallback
    if not schema:
        return _regex_fallback_parse(ddl)

    return schema


def _extract_type(col_def: exp.ColumnDef) -> str:
    """Extract the SQL type as a clean string."""
    dtype = col_def.args.get("kind")
    if dtype:
        return dtype.sql().upper()
    return "TEXT"


def _extract_max_length(col_def: exp.ColumnDef) -> int | None:
    """Extract VARCHAR/CHAR length if present."""
    dtype = col_def.args.get("kind")
    if dtype and isinstance(dtype, exp.DataType):
        for expr in dtype.expressions:
            if isinstance(expr, exp.DataTypeParam):
                try:
                    return int(expr.this.name)
                except Exception:
                    pass
    return None


def _regex_fallback_parse(ddl: str) -> dict:
    """
    Fallback regex-based parser for simpler DDL patterns.
    Handles basic CREATE TABLE statements.
    """
    schema = {}

    table_pattern = re.compile(
        r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"\[]?(\w+)[`"\]]?\s*\((.*?)\)\s*;',
        re.IGNORECASE | re.DOTALL
    )

    for match in table_pattern.finditer(ddl):
        table_name = match.group(1).lower()
        body = match.group(2)

        schema[table_name] = {"columns": []}
        table_fks = {}

        fk_pattern = re.compile(
            r'FOREIGN\s+KEY\s*\(([^)]+)\)\s+REFERENCES\s+[`"\[]?(\w+)[`"\]]?\s*\(([^)]+)\)',
            re.IGNORECASE
        )
        for fk_match in fk_pattern.finditer(body):
            local_cols = [c.strip().strip('`"[]').lower() for c in fk_match.group(1).split(',')]
            ref_table = fk_match.group(2).lower()
            ref_cols = [c.strip().strip('`"[]').lower() for c in fk_match.group(3).split(',')]
            for i, col in enumerate(local_cols):
                ref_col = ref_cols[i] if i < len(ref_cols) else ref_cols[0]
                table_fks[col] = {"table": ref_table, "column": ref_col}

        lines = body.split('\n')
        for line in lines:
            line = line.strip().rstrip(',')

            if re.match(r'(PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CHECK|CONSTRAINT|INDEX|KEY)\b', line, re.IGNORECASE):
                continue

            m = re.match(r'[`"\[]?(\w+)[`"\]]?\s+(\w+(?:\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\))?)(.*)', line, re.IGNORECASE)
            if not m:
                continue

            col_name = m.group(1).lower()
            col_type = m.group(2).upper()
            constraints = m.group(3).upper()

            max_length = None
            len_match = re.search(r'\((\d+)', col_type)
            if len_match:
                max_length = int(len_match.group(1))
                col_type = re.sub(r'\(.*\)', '', col_type).strip()

            is_pk = 'PRIMARY KEY' in constraints
            is_unique = 'UNIQUE' in constraints
            is_nullable = 'NOT NULL' not in constraints and not is_pk

            fk_info = table_fks.get(col_name)

            schema[table_name]["columns"].append({
                "name": col_name,
                "type": col_type,
                "nullable": is_nullable,
                "primary_key": is_pk,
                "foreign_key": fk_info,
                "unique": is_unique or is_pk,
                "max_length": max_length
            })

    return schema
