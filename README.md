# sqliteRAG

Local-first chat application using Ollama for LLM inference and SQLite with vector search (sqlite-vec) for RAG.

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- [Ollama](https://ollama.ai) running locally

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173` with API proxy to backend.

### Pull a model

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy async, aiosqlite, sqlite-vec, Alembic
- **Frontend**: Vite, React, TypeScript, Tailwind CSS, Zustand
- **LLM**: Ollama (local inference)
- **Embeddings**: nomic-embed-text via Ollama
- **Vector Search**: sqlite-vec (vec0 virtual table)

## Testing

```bash
cd backend
source .venv/bin/activate
pytest
```
