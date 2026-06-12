import os
import json
import hashlib
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CACHE_FILE = "mapper_cache.json"

PROMPT = """
You are a data engineering assistant.

Map SQL table columns to Faker-style expressions.

Rules:
- primary key → faker.unique.random_int(1, 99999)
- foreign key → FK:table.column
- infer meaning from column names
- return ONLY JSON

Table: {table}
Columns: {columns}
Foreign Keys: {fks}

Return format:
{{ "col": "faker.email()" }}
"""


def load_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def get_or_build_column_map(schema):
    cache = load_cache()
    full_map = {}
    total_tokens = 0

    for table, data in schema.items():

        key = hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

        cache_key = f"{table}:{key}"

        if cache_key in cache:
            full_map[table] = cache[cache_key]
            continue

        prompt = PROMPT.format(
            table=table,
            columns=json.dumps(data["columns"], indent=2),
            fks=json.dumps(data["foreign_keys"], indent=2)
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        content = response.choices[0].message.content

        if "```" in content:
            content = content.split("```")[1]

        mapping = json.loads(content)

        cache[cache_key] = mapping
        full_map[table] = mapping

        total_tokens += response.usage.total_tokens

    save_cache(cache)

    return full_map, total_tokens