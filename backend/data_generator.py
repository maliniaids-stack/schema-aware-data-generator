import random
import ast
from faker import Faker


# ----------------------------
# TOPOLOGICAL SORT (SAFE)
# ----------------------------
def build_order(schema: dict) -> list:
    """
    Returns a safe generation order.
    If cycle exists, falls back to original order (no mutation).
    """
    graph = {}

    for table, meta in schema.items():
        deps = {
            fk["ref_table"]
            for fk in meta["foreign_keys"]
            if fk["ref_table"] != table
        }
        graph[table] = deps

    visited = set()
    order = []

    def visit(node, stack):
        if node in stack:
            return  # cycle detected → ignore path safely
        if node in visited:
            return

        stack.add(node)

        for dep in graph.get(node, []):
            visit(dep, stack)

        stack.remove(node)
        visited.add(node)
        order.append(node)

    for n in graph:
        visit(n, set())

    return order


# ----------------------------
# SAFE FAKER EVALUATOR
# ----------------------------
def safe_eval_faker(faker_instance: Faker, expr: str):
    """
    Safely evaluate faker expressions using AST (no eval risk).
    """

    try:
        tree = ast.parse(expr, mode='eval').body
    except Exception as e:
        raise ValueError(f"Invalid faker expression: {expr} -> {e}")

    def _eval(node):
        if isinstance(node, ast.Name):
            if node.id == "faker":
                return faker_instance
            if node.id in ("True", "true"):
                return True
            if node.id in ("False", "false"):
                return False
            if node.id in ("None", "null"):
                return None
            raise ValueError(f"Unknown identifier: {node.id}")

        elif isinstance(node, ast.Attribute):
            return getattr(_eval(node.value), node.attr)

        elif isinstance(node, ast.Call):
            func = _eval(node.func)
            args = [_eval(a) for a in node.args]
            kwargs = {k.arg: _eval(k.value) for k in node.keywords}
            return func(*args, **kwargs)

        elif isinstance(node, ast.Constant):
            return node.value

        else:
            raise ValueError(f"Unsupported AST node: {type(node)}")

    return _eval(tree)


# ----------------------------
# MAIN GENERATOR
# ----------------------------
def generate_data(schema: dict, column_map: dict, topo_order: list, num_rows: int = 20):
    faker = Faker()
    generated = {}

    # Pre-create tables
    for t in topo_order:
        generated[t] = []

    # Build quick FK lookup
    fk_map = {
        table: {
            col: fk_expr
            for col, fk_expr in column_map.get(table, {}).items()
            if isinstance(fk_expr, str) and fk_expr.startswith("FK:")
        }
        for table in column_map
    }

    # ----------------------------
    # GENERATION PHASE
    # ----------------------------
    for table in topo_order:

        for _ in range(num_rows):
            row = {}

            for col, expr in column_map.get(table, {}).items():

                # ---------------- FK HANDLING ----------------
                if isinstance(expr, str) and expr.startswith("FK:"):
                    try:
                        ref = expr.replace("FK:", "")
                        ref_table, ref_col = ref.split(".")

                        if generated.get(ref_table):
                            parent = random.choice(generated[ref_table])
                            row[col] = parent.get(ref_col)
                        else:
                            row[col] = None

                    except Exception:
                        row[col] = None

                # ---------------- NORMAL FAKER ----------------
                else:
                    try:
                        row[col] = safe_eval_faker(faker, expr)
                    except Exception:
                        row[col] = None

            generated[table].append(row)

    return generated