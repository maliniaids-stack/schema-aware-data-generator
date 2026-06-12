import os
import io
import csv
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import sqlglot

from backend.parser.ddl_parser import parse_ddl
from backend.mapper.llm_mapper import get_or_build_column_map
from backend.generator.data_generator import build_order, generate_data
from backend.exporter.exporter import to_sql_inserts

load_dotenv()

app = Flask(__name__)
CORS(app)

# ----------------------------
# ROUTE
# ----------------------------
@app.route("/api/generate", methods=["POST"])
def generate():

    try:
        data = request.get_json()

        ddl = data.get("ddl", "")
        rows = int(data.get("rows", 20))

        if not ddl:
            return jsonify({"error": "DDL is required"}), 400

        # 1. Parse DDL
        schema = parse_ddl(ddl)

        # 2. OpenAI mapping
        column_map, tokens_used = get_or_build_column_map(schema)

        # 3. Order tables
        topo_order = build_order(schema)

        # 4. Generate data
        generated = generate_data(
            schema,
            column_map,
            topo_order,
            num_rows=rows
        )

        results = {
            "tables": [],
            "seed_all": "",
            "tokens_used": tokens_used
        }

        combined_sql = []

        # 5. Build output
        for table_name in topo_order:

            rows_data = generated.get(table_name, [])
            if not rows_data:
                continue

            # SQL
            sql_str = to_sql_inserts(table_name, rows_data)
            combined_sql.append(sql_str)

            # CSV (in-memory)
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=rows_data[0].keys())
            writer.writeheader()

            for row in rows_data:
                writer.writerow({k: ("" if v is None else v) for k, v in row.items()})

            csv_str = output.getvalue()

            results["tables"].append({
                "name": table_name,
                "sql": sql_str,
                "csv": csv_str,
                "data": rows_data
            })

        results["seed_all"] = "\n\n".join(combined_sql)

        return jsonify(results)

    except sqlglot.errors.ParseError as e:
        return jsonify({"error": f"Bad DDL: {str(e)}"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ----------------------------
# RUN SERVER
# ----------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)