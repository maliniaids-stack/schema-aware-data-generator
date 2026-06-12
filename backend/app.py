"""
backend/app.py
Flask API server — Schema-Aware Test Data Generator (Groq Edition).
Serves JSON only; frontend is fully separated in /frontend.
"""

import os
import json
import sys
import io
import zipfile

# Allow running as: python backend/app.py from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

# Load .env from same directory as this file
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from backend.parser.ddl_parser import parse_ddl
from backend.mapper.llm_mapper import map_schema
from backend.resolver import resolve_order
from backend.generator.data_generator import generate_data
from backend.exporter.exporter import export_sql, export_csv, export_seed_all
from backend.utils.cache import get_cache_path

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# Allow requests from any origin so the standalone frontend can call the API
CORS(app, resources={r"/api/*": {"origins": "*"}})


# ─── Health check ─────────────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "model": "llama-3.1-8b-instant", "provider": "groq"})


# ─── Main generation endpoint ─────────────────────────────────────────────────

@app.route("/api/generate", methods=["POST"])
def generate():
    try:
        body = request.get_json(force=True)
        ddl = body.get("ddl", "").strip()
        rows = int(body.get("rows", 20))

        if not ddl:
            return jsonify({"error": "DDL is required"}), 400

        if rows < 1 or rows > 500:
            return jsonify({"error": "Row count must be between 1 and 500"}), 400

        # 1. Parse DDL
        schema = parse_ddl(ddl)
        if not schema:
            return jsonify({"error": "Could not parse DDL. Please check your SQL syntax."}), 400

        # 2. Map columns via Groq LLM (with cache)
        mapped_schema, tokens_used = map_schema(schema)

        # 3. Resolve dependency order (topological sort)
        ordered_tables = resolve_order(mapped_schema)

        # 4. Generate data
        generated = generate_data(ordered_tables, mapped_schema, rows)

        # 5. Export
        tables_output = []
        for table_name in ordered_tables:
            data = generated[table_name]
            columns = [col["name"] for col in mapped_schema[table_name]["columns"]]
            sql = export_sql(table_name, columns, data)
            csv_content = export_csv(table_name, columns, data)
            tables_output.append({
                "name": table_name,
                "sql": sql,
                "csv": csv_content,
                "columns": columns,
                "data": data[:5],       # preview first 5 rows
                "total_rows": len(data)
            })

        seed_all = export_seed_all(tables_output)

        return jsonify({
            "tables": tables_output,
            "seed_all": seed_all,
            "tokens_used": tokens_used,
            "table_count": len(tables_output)
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        app.logger.error(f"Generation error: {e}", exc_info=True)
        return jsonify({"error": f"Internal error: {str(e)}"}), 500


# ─── ZIP download endpoint ────────────────────────────────────────────────────

@app.route("/api/download", methods=["POST"])
def download():
    """Package all exports into a ZIP file for download."""
    try:
        body = request.get_json(force=True)
        tables = body.get("tables", [])
        seed_all = body.get("seed_all", "")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("seed_all.sql", seed_all)
            for table in tables:
                zf.writestr(f"sql/{table['name']}.sql", table["sql"])
                zf.writestr(f"csv/{table['name']}.csv", table["csv"])

        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name="test_data.zip"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Cache management endpoints ───────────────────────────────────────────────

@app.route("/api/cache/stats", methods=["GET"])
def cache_stats():
    """Return cache statistics."""
    try:
        cache_path = get_cache_path()
        if os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                cache = json.load(f)
            return jsonify({
                "entries": len(cache),
                "size_bytes": os.path.getsize(cache_path)
            })
        return jsonify({"entries": 0, "size_bytes": 0})
    except Exception:
        return jsonify({"entries": 0, "size_bytes": 0})


@app.route("/api/cache/clear", methods=["DELETE"])
def clear_cache():
    """Clear the mapper cache."""
    try:
        cache_path = get_cache_path()
        if os.path.exists(cache_path):
            os.remove(cache_path)
        return jsonify({"message": "Cache cleared successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    print(f"\n[DataGenAI] Backend running at http://localhost:{port}")
    print(f"[DataGenAI] Open frontend/index.html in your browser to use the app\n")
    app.run(debug=debug, port=port)
