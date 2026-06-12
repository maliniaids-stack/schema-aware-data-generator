# DataGenAI — Schema-Aware Test Data Generator

> **AI-powered SQL DDL → Relational Test Data** using Groq (LLaMA 3.1) + Faker + Flask

---

## Features

- 🤖 **AI Column Mapping** — Groq's `llama-3.1-8b-instant` maps each SQL column to the best Faker generator
- 🔗 **FK Integrity** — Topological sort ensures parent tables are generated before children
- ⚡ **SHA-256 Cache** — Repeated schemas skip the LLM call entirely
- 📦 **Multiple Exports** — SQL INSERT statements, CSV files, and combined `seed_all.sql`
- 🛡 **Safe Evaluation** — No `eval()` — custom Faker dispatcher with whitelist validation
- 🎨 **Premium UI** — Dark-mode glassmorphism design with animated pipeline steps

---

## Project Structure

```
datagenai/
├── backend/
│   ├── app.py                      # Flask API server (CORS-enabled)
│   ├── parser/
│   │   └── ddl_parser.py           # SQL DDL parser (sqlglot + regex fallback)
│   ├── mapper/
│   │   └── llm_mapper.py           # Groq API column mapping
│   ├── generator/
│   │   └── data_generator.py       # Safe Faker-based data generation
│   ├── exporter/
│   │   └── exporter.py             # SQL/CSV/seed_all export
│   ├── utils/
│   │   └── cache.py                # JSON cache utilities
│   ├── resolver.py                 # FK dependency resolver (Kahn's algorithm)
│   └── .env                        # GROQ_API_KEY (create this!)
│
├── frontend/
│   ├── index.html                  # Standalone UI (open in browser)
│   ├── style.css                   # Premium dark-mode design
│   └── script.js                   # API calls to backend
│
├── output/                         # Generated files
├── requirements.txt
└── README.md
```

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Your Groq API Key

Edit `backend/.env`:
```
GROQ_API_KEY=gsk_your_actual_key_here
```

> Get a free API key at: https://console.groq.com

### 3. Start the Backend

```bash
python backend/app.py
```

Backend runs at `http://localhost:5000`

### 4. Open the Frontend

Simply open `frontend/index.html` in your browser.

Or serve it with Python's built-in server:

```bash
cd frontend
python -m http.server 8080
```

Then open: http://localhost:8080

---

## API Reference

### `POST /api/generate`

Generate test data from DDL.

**Request:**
```json
{
  "ddl": "CREATE TABLE users (...);",
  "rows": 20
}
```

**Response:**
```json
{
  "tables": [
    {
      "name": "users",
      "sql": "INSERT INTO ...",
      "csv": "id,name,...",
      "columns": ["id", "name"],
      "data": [...],
      "total_rows": 20
    }
  ],
  "seed_all": "-- Combined SQL...",
  "tokens_used": 245,
  "table_count": 1
}
```

### `POST /api/download`
Returns a ZIP file containing all SQL and CSV exports.

### `GET /api/cache/stats`
Returns cache entry count and file size.

### `DELETE /api/cache/clear`
Clears the mapper cache.

### `GET /api/health`
Health check — returns model info.

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | — | Required. From https://console.groq.com |
| `PORT` | `5000` | Backend port |
| `FLASK_DEBUG` | `true` | Debug mode |

Frontend: edit `API_BASE` in `frontend/script.js` to point to your backend host.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask 3.x + Flask-CORS |
| AI | Groq API — `llama-3.1-8b-instant` |
| SQL Parser | sqlglot |
| Data Generator | Faker |
| Cache | JSON file (SHA-256 keyed) |
| Frontend | Vanilla HTML + CSS + JavaScript |
