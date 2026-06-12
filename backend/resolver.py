"""
backend/resolver.py
Resolves table generation order using topological sort (Kahn's algorithm).
Ensures parent tables are generated before child tables.
"""

from collections import defaultdict, deque


def resolve_order(mapped_schema: dict) -> list[str]:
    """
    Topologically sort tables so parents are generated before children.
    Handles cycles by detecting and breaking them gracefully.

    Returns:
        Ordered list of table names (parents first).
    """
    tables = list(mapped_schema.keys())

    dependencies = defaultdict(set)   # table -> {parent_tables}
    dependents = defaultdict(set)     # table -> {child_tables}

    for table_name, table_info in mapped_schema.items():
        for col in table_info["columns"]:
            fk = col.get("foreign_key")
            if fk:
                parent = fk["table"]
                if parent in mapped_schema and parent != table_name:
                    dependencies[table_name].add(parent)
                    dependents[parent].add(table_name)

    in_degree = {t: len(dependencies[t]) for t in tables}
    queue = deque([t for t in tables if in_degree[t] == 0])
    ordered = []

    while queue:
        node = queue.popleft()
        ordered.append(node)
        for child in sorted(dependents[node]):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    # Handle cycles: append remaining tables at the end
    remaining = [t for t in tables if t not in ordered]
    if remaining:
        remaining.sort(key=lambda t: len(dependencies[t]))
        ordered.extend(remaining)

    return ordered


def get_dependency_graph(mapped_schema: dict) -> dict:
    """
    Returns a human-readable dependency graph for debugging.
    """
    graph = {}
    for table_name, table_info in mapped_schema.items():
        parents = set()
        for col in table_info["columns"]:
            fk = col.get("foreign_key")
            if fk and fk["table"] in mapped_schema:
                parents.add(fk["table"])
        graph[table_name] = sorted(parents)
    return graph
