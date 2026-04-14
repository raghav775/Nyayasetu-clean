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
- **LLM (Online)** — Groq API (Llama 3.3 70B) — free tier
- **LLM (Offline)** — Ollama (Llama 3.2)
- **Embeddings** — sentence-transformers (local, free)
- **Vector DB** — Qdrant (local, embedded)
- **Case Data** — Indian Kanoon (live search + Hugging Face dataset)
- **Frontend** — React

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
cp .env.example .env      # Add your Groq API key
uvicorn main:app --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm start
```

### Offline Mode (Ollama)
```bash
ollama pull llama3.2
# Ollama runs automatically as fallback when Groq is unavailable
```

---

## Environment Variables

```
GROQ_API_KEY=your_groq_api_key_here
```

---

## License

MIT License — free to use, modify, and distribute.

---

*Built for the people. Powered by open source.*
