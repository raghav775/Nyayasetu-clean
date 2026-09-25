# NyayaSetu — न्यायसेतु

**Bridge to Justice** | AI-powered legal assistant for advocates and legal interns

---

## What is NyayaSetu?

NyayaSetu is a free, open-source legal AI platform built for Indian legal professionals. It helps advocates and interns:

- **Find real cases** — Search actual Indian court judgments with proper citations
- **Draft documents** — Generate error-free legal drafts from a library of 1841 templates
- **Get legal guidance** — Article-backed Q&A for common legal questions

No hallucinations. No guesswork. Every answer is grounded in real legal data.

---

## Features

| Feature | Description |
|---|---|
| Case Finder | RAG-powered search over Indian Kanoon judgments |
| Draft Assistant | Generate contracts, petitions, plaints from templates |
| Legal Aid | Article-backed Q&A for legal guidance |
| Offline Mode | Full functionality via Ollama — no internet needed |

---

## Tech Stack

- **Backend** — Python, FastAPI
- **LLM (Online)** — Groq API (`openai/gpt-oss-120b`, falling back to `openai/gpt-oss-20b`) — free tier
- **LLM (Offline)** — Ollama (Llama 3.2)
- **Embeddings** — fastembed (`BAAI/bge-small-en-v1.5`, local, free)
- **Vector DB** — Qdrant (embedded locally, or Qdrant Cloud in production)
- **Case Data** — Indian Kanoon (live search + Hugging Face dataset)
- **Frontend** — React + Vite

---

## Project Structure

```
nyayasetu/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── routes/              # API route handlers
│   ├── services/            # Core logic (RAG, LLM, scraper)
│   ├── models/              # Pydantic data models
│   └── utils/               # Helpers and loaders
├── frontend/
│   ├── src/
│   │   ├── pages/           # Case Finder, Draft Assistant, Legal Aid
│   │   └── components/      # Reusable UI components
├── data/
│   ├── drafts/              # Legal draft templates (RTF/DOCX)
│   ├── cases/               # Case study data
│   └── articles/            # Legal articles
└── README.md
```

---

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- Ollama (for offline mode)

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # Add your Groq API key, then generate secrets: python utils/generate_keys.py
python ingest.py          # one-time: load the draft templates into the vector DB
uvicorn main:app --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev      # proxies /api to http://localhost:8000
```

### Offline Mode (Ollama)
```bash
ollama pull llama3.2
# Ollama runs automatically as fallback when Groq is unavailable
```

---

## Environment Variables

See [backend/.env.example](backend/.env.example) for the full list. The important ones:

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | Enables the AI features (required) |
| `JWT_SECRET_KEY`, `ENCRYPTION_KEY` | Auth + query encryption — generate with `python utils/generate_keys.py` |
| `INDIAN_KANOON_TOKEN` | Indian Kanoon API token (falls back to scraping) |
| `QDRANT_URL`, `QDRANT_API_KEY` | Qdrant Cloud, so templates survive Render restarts |
| `DATABASE_URL` | Hosted Postgres for user accounts (SQLite is wiped on Render's free tier) |
| `GROQ_MODEL`, `GROQ_FALLBACK_MODELS` | Optional model overrides |

> **Groq model retirements:** Groq retired `llama-3.3-70b-versatile` and `llama-3.1-8b-instant` on
> 2026-08-16 — calls to them fail with `404 model_not_found`. The defaults are now
> `openai/gpt-oss-120b` → `openai/gpt-oss-20b`. If AI features stop working, open `/health` on the
> backend: it reports whether the key is set, which models are in use, and why the last AI call failed.

---

## License

MIT License — free to use, modify, and distribute.

---

*Built for the people. Powered by open source.*
