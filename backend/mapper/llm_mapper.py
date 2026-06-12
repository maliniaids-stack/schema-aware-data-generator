"""
backend/mapper/llm_mapper.py
Maps each column to a Faker expression using Groq API (llama-3.1-8b-instant).
Uses a SHA-256 JSON cache (mapper_cache.json) to avoid redundant API calls.
"""

import os
import json
import hashlib
import re
from groq import Groq
from backend.utils.cache import load_cache, save_cache

_client = None


def _get_client() -> Groq:
    """Lazy Groq client — only initialise when first needed."""
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY environment variable is not set. "
                "Add it to backend/.env: GROQ_API_KEY=gsk_..."
            )
        _client = Groq(api_key=api_key)
    return _client


# ─── Safe Faker expression whitelist ──────────────────────────────────────────
ALLOWED_FAKER_METHODS = {
    # Identity
    "faker.uuid4()",
    "faker.unique.random_int(min=1, max=99999)",
    "faker.unique.random_int(min=1, max=999999)",
    "faker.random_int(min=1, max=100)",
    "faker.random_int(min=0, max=1)",
    "faker.boolean()",
    # Person
    "faker.name()",
    "faker.first_name()",
    "faker.last_name()",
    "faker.prefix()",
    "faker.suffix()",
    "faker.user_name()",
    # Contact
    "faker.email()",
    "faker.free_email()",
    "faker.company_email()",
    "faker.phone_number()",
    "faker.url()",
    # Address
    "faker.address()",
    "faker.street_address()",
    "faker.city()",
    "faker.state()",
    "faker.state_abbr()",
    "faker.country()",
    "faker.country_code()",
    "faker.zipcode()",
    "faker.postcode()",
    "faker.latitude()",
    "faker.longitude()",
    # Company
    "faker.company()",
    "faker.catch_phrase()",
    "faker.bs()",
    "faker.ein()",
    # Finance
    "faker.credit_card_number()",
    "faker.iban()",
    "faker.currency_code()",
    "faker.pricetag()",
    "faker.random_int(min=1, max=10000)",
    "faker.pyfloat(min_value=0, max_value=10000, right_digits=2)",
    "faker.pyfloat(min_value=0, max_value=1000000, right_digits=2)",
    # Dates/Times
    "faker.date_of_birth(minimum_age=18, maximum_age=80).isoformat()",
    "faker.date_this_decade().isoformat()",
    "faker.date_this_year().isoformat()",
    "faker.date_time_this_year().isoformat()",
    "faker.date_between(start_date='-5y', end_date='today').isoformat()",
    "faker.iso8601()",
    "faker.time()",
    # Text
    "faker.text(max_nb_chars=100)",
    "faker.text(max_nb_chars=200)",
    "faker.text(max_nb_chars=500)",
    "faker.sentence()",
    "faker.paragraph()",
    "faker.word()",
    "faker.slug()",
    "faker.md5()",
    "faker.sha256()",
    # Status / Enum patterns
    "faker.random_element(['active', 'inactive', 'pending'])",
    "faker.random_element(['admin', 'user', 'moderator'])",
    "faker.random_element(['male', 'female', 'other'])",
    "faker.random_element(['USD', 'EUR', 'GBP', 'JPY'])",
    "faker.random_element(['yes', 'no'])",
    "faker.random_element(['draft', 'published', 'archived'])",
    # Misc
    "faker.color_name()",
    "faker.hex_color()",
    "faker.mime_type()",
    "faker.file_name()",
    "faker.image_url()",
    "faker.ipv4()",
    "faker.ipv4_public()",
    "faker.ipv6()",
    "faker.mac_address()",
    "faker.user_agent()",
    "faker.locale()",
    "faker.language_code()",
    "faker.numerify('###-###-####')",
    "faker.numerify('PROD-#####')",
    "faker.numerify('ORD-#####')",
}


def _hash_schema(table_name: str, columns: list) -> str:
    """Create a stable SHA-256 hash for a table's column definitions."""
    key = json.dumps({
        "table": table_name,
        "columns": [
            {"name": c["name"], "type": c["type"], "pk": c["primary_key"],
             "fk": c["foreign_key"], "unique": c["unique"]}
            for c in columns
        ]
    }, sort_keys=True)
    return hashlib.sha256(key.encode()).hexdigest()


def _sanitize_expression(expr: str) -> str:
    """
    Validate a Faker expression against the whitelist.
    Falls back to faker.word() for unknown/unsafe expressions.
    """
    expr = expr.strip()

    if expr in ALLOWED_FAKER_METHODS:
        return expr

    # Pattern matches for parameterised expressions
    patterns = [
        r"^faker\.random_element\(\[.*\]\)$",
        r"^faker\.random_int\(min=\d+,\s*max=\d+\)$",
        r"^faker\.pyfloat\(min_value=[\d.]+,\s*max_value=[\d.]+,\s*right_digits=\d+\)$",
        r"^faker\.text\(max_nb_chars=\d+\)$",
        r"^faker\.numerify\('[^']+'\)$",
        r"^faker\.date_between\(start_date='[^']+',\s*end_date='[^']+'\)\.isoformat\(\)$",
        r"^faker\.date_of_birth\(minimum_age=\d+,\s*maximum_age=\d+\)\.isoformat\(\)$",
    ]

    for pattern in patterns:
        if re.match(pattern, expr):
            return expr

    return "faker.word()"


def _call_groq(table_name: str, columns: list) -> tuple[dict, int]:
    """
    Call Groq API (llama-3.1-8b-instant) to map columns to Faker expressions.
    Returns ({column_name: faker_expression}, tokens_used).
    """
    col_descriptions = []
    for col in columns:
        fk_note = (
            f" (FK → {col['foreign_key']['table']}.{col['foreign_key']['column']})"
            if col["foreign_key"] else ""
        )
        pk_note = " (PRIMARY KEY)" if col["primary_key"] else ""
        col_descriptions.append(
            f"  - {col['name']}: {col['type']}{pk_note}{fk_note}"
        )

    prompt = f"""You are a test data mapping expert. Map each column of the SQL table '{table_name}' to a Python Faker expression.

Table: {table_name}
Columns:
{chr(10).join(col_descriptions)}

Rules:
1. For PRIMARY KEY integer columns: use faker.unique.random_int(min=1, max=99999)
2. For PRIMARY KEY UUID columns: use faker.uuid4()
3. For FOREIGN KEY columns: respond with FK:{{table}}.{{column}} exactly (no Faker call)
4. For email columns: faker.email()
5. For name/fullname: faker.name() | first_name: faker.first_name() | last_name: faker.last_name()
6. For phone: faker.phone_number()
7. For address: faker.street_address() or faker.address()
8. For city/state/country: faker.city() / faker.state() / faker.country()
9. For dates: faker.date_this_decade().isoformat()
10. For timestamps/created_at/updated_at: faker.iso8601()
11. For money/price/amount: faker.pyfloat(min_value=0, max_value=10000, right_digits=2)
12. For status/type/role enum columns: faker.random_element(['option1', 'option2', 'option3'])
13. For text/description/bio: faker.text(max_nb_chars=200)
14. For boolean/flag columns: faker.boolean()
15. For username/login: faker.user_name()
16. For URL/website: faker.url()
17. For IP: faker.ipv4()

Respond ONLY with a valid JSON object like:
{{"column_name": "faker_expression", ...}}

No markdown, no explanation, just the JSON."""

    client = _get_client()
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=800,
    )

    raw = response.choices[0].message.content.strip()
    tokens = response.usage.total_tokens if response.usage else 0

    # Strip markdown fences if Groq wraps output in them
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)

    try:
        mapping = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: basic mapping if JSON parse fails
        mapping = {col["name"]: "faker.word()" for col in columns}

    return mapping, tokens


def map_schema(schema: dict) -> tuple[dict, int]:
    """
    Map all tables in the schema to Faker expressions.
    Uses cache where possible to avoid repeated Groq API calls.

    Returns:
        (mapped_schema, total_tokens_used)
    """
    cache = load_cache()
    total_tokens = 0
    mapped_schema = {}

    for table_name, table_info in schema.items():
        columns = table_info["columns"]
        schema_hash = _hash_schema(table_name, columns)

        if schema_hash in cache:
            raw_mapping = cache[schema_hash]["mapping"]
            tokens_used = 0
        else:
            raw_mapping, tokens_used = _call_groq(table_name, columns)
            cache[schema_hash] = {
                "table": table_name,
                "mapping": raw_mapping
            }
            save_cache(cache)

        total_tokens += tokens_used

        # Build final column list with sanitised Faker expressions
        mapped_columns = []
        for col in columns:
            faker_expr = raw_mapping.get(col["name"], "faker.word()")

            if col["foreign_key"] and not faker_expr.startswith("FK:"):
                ref = col["foreign_key"]
                faker_expr = f"FK:{ref['table']}.{ref['column']}"
            elif not col["foreign_key"] and faker_expr.startswith("FK:"):
                faker_expr = "faker.word()"
            elif not col["foreign_key"]:
                faker_expr = _sanitize_expression(faker_expr)

            mapped_columns.append({**col, "faker_expr": faker_expr})

        mapped_schema[table_name] = {"columns": mapped_columns}

    return mapped_schema, total_tokens
