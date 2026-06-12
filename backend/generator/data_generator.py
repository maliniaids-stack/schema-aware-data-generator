"""
backend/generator/data_generator.py
Generates realistic fake data using Faker expressions.
Enforces referential integrity by resolving FK values from parent tables.
Uses safe dispatch instead of eval().
"""

import re
import random
from faker import Faker

faker = Faker()
Faker.seed(42)  # Reproducible results


# ─── Safe Faker dispatch ───────────────────────────────────────────────────────

def _call_faker(expr: str):
    """
    Safely evaluate a Faker expression without using eval().
    Parses method name and arguments from the expression string.
    """
    expr = expr.strip()

    # Handle chained calls like faker.X().isoformat()
    chain_match = re.match(r'^(faker\.\w+\(.*?\))\.(\w+)\(\)$', expr, re.DOTALL)
    if chain_match:
        base_result = _call_faker(chain_match.group(1))
        method = chain_match.group(2)
        return getattr(base_result, method)() if hasattr(base_result, method) else str(base_result)

    # Match: faker.method_name(args...)
    match = re.match(r'^faker\.(unique\.)?(\w+)\((.*)\)$', expr, re.DOTALL)
    if not match:
        return faker.word()

    use_unique = bool(match.group(1))
    method_name = match.group(2)
    raw_args = match.group(3).strip()

    faker_obj = faker.unique if use_unique else faker

    if not hasattr(faker_obj, method_name):
        return faker.word()

    method = getattr(faker_obj, method_name)

    if not raw_args:
        return method()

    # Parse keyword arguments
    kwargs = _parse_kwargs(raw_args)
    if kwargs is not None:
        try:
            return method(**kwargs)
        except Exception:
            try:
                return method()
            except Exception:
                return faker.word()

    # Parse positional arguments (e.g. random_element(['a', 'b']))
    try:
        args = _parse_positional(raw_args)
        return method(*args)
    except Exception:
        try:
            return method()
        except Exception:
            return faker.word()


def _parse_kwargs(raw: str) -> dict | None:
    """Parse key=value pairs from a kwargs string."""
    kwargs = {}
    parts = re.split(r',\s*(?![^\[]*\])', raw)
    for part in parts:
        kv = re.match(r"(\w+)\s*=\s*(.+)", part.strip())
        if not kv:
            return None
        key = kv.group(1)
        val_str = kv.group(2).strip()
        kwargs[key] = _parse_value(val_str)
    return kwargs if kwargs else None


def _parse_positional(raw: str):
    """Parse a single positional argument (list literal or string)."""
    raw = raw.strip()

    list_match = re.match(r'^\[(.+)\]$', raw, re.DOTALL)
    if list_match:
        items_raw = list_match.group(1)
        items = re.findall(r"'([^']*)'|\"([^\"]*)\"|(\d+(?:\.\d+)?)", items_raw)
        result = []
        for a, b, c in items:
            if a or b:
                result.append(a or b)
            elif c:
                result.append(float(c) if '.' in c else int(c))
        return [result]

    return [_parse_value(raw)]


def _parse_value(val_str: str):
    """Parse a primitive value from a string."""
    val_str = val_str.strip()

    if val_str == 'True':
        return True
    if val_str == 'False':
        return False
    if val_str == 'None':
        return None

    try:
        return int(val_str)
    except ValueError:
        pass

    try:
        return float(val_str)
    except ValueError:
        pass

    str_match = re.match(r"^['\"](.+)['\"]$", val_str)
    if str_match:
        return str_match.group(1)

    list_match = re.match(r'^\[(.+)\]$', val_str, re.DOTALL)
    if list_match:
        items = re.findall(r"'([^']*)'|\"([^\"]*)\"|(\d+(?:\.\d+)?)", list_match.group(1))
        result = []
        for a, b, c in items:
            if a or b:
                result.append(a or b)
            elif c:
                result.append(float(c) if '.' in c else int(c))
        return result

    return val_str


# ─── Main generator ────────────────────────────────────────────────────────────

def generate_data(ordered_tables: list, mapped_schema: dict, rows: int) -> dict:
    """
    Generate `rows` rows for each table in topological order.
    FK columns are resolved by sampling from already-generated parent rows.

    Returns:
        {table_name: [{"col": value, ...}, ...]}
    """
    generated = {}

    for table_name in ordered_tables:
        if table_name not in mapped_schema:
            continue

        table_info = mapped_schema[table_name]
        columns = table_info["columns"]

        # Reset unique tracker per table to avoid cross-table collisions
        faker.unique.clear()

        table_rows = []
        unique_pk_tracker = set()

        for row_idx in range(rows):
            row = {}
            for col in columns:
                col_name = col["name"]
                faker_expr = col.get("faker_expr", "faker.word()")

                # Foreign key: pick from parent table
                if faker_expr.startswith("FK:"):
                    fk_ref = faker_expr[3:]
                    parts = fk_ref.split(".", 1)
                    if len(parts) == 2:
                        parent_table, parent_col = parts
                        parent_rows = generated.get(parent_table, [])
                        if parent_rows:
                            chosen = random.choice(parent_rows)
                            row[col_name] = chosen.get(parent_col)
                        else:
                            row[col_name] = row_idx + 1
                    else:
                        row[col_name] = row_idx + 1
                    continue

                # Primary key: ensure uniqueness
                if col["primary_key"] and col["unique"]:
                    value = _generate_unique_pk(faker_expr, unique_pk_tracker)
                    unique_pk_tracker.add(value)
                    row[col_name] = value
                    continue

                # Normal column
                try:
                    value = _call_faker(faker_expr)
                    if col.get("max_length") and isinstance(value, str):
                        value = value[:col["max_length"]]
                    row[col_name] = value
                except Exception:
                    row[col_name] = None if col["nullable"] else f"{col_name}_{row_idx + 1}"

            table_rows.append(row)

        generated[table_name] = table_rows

    return generated


def _generate_unique_pk(faker_expr: str, existing: set, max_attempts: int = 10000):
    """Generate a unique primary key value."""
    for _ in range(max_attempts):
        value = _call_faker(faker_expr)
        if value not in existing:
            return value
    return max(existing) + 1 if existing and all(isinstance(v, int) for v in existing) else str(len(existing) + 1)
