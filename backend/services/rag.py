import os
import uuid
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter,
    FieldCondition, MatchValue
)
from utils.document_loader import load_all_documents

QDRANT_PATH = os.getenv("CHROMA_DB_PATH", "./qdrant_db")
DRAFTS_DATA_PATH = os.getenv("DRAFTS_DATA_PATH", "../data/drafts")
COLLECTION_NAME = "nyayasetu_legal_docs"
VECTOR_SIZE = 384

# Lazy loaded — not at startup
_embedding_model = None
_qdrant_client = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        print("[RAG] Loading embedding model (all-MiniLM-L6-v2)...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        print("[RAG] Embedding model ready.")
    return _embedding_model


def get_qdrant():
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(path=QDRANT_PATH)
    return _qdrant_client


def ensure_collection():
    client = get_qdrant()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def get_collection_count() -> int:
    try:
        ensure_collection()
        return get_qdrant().count(collection_name=COLLECTION_NAME).count
    except Exception:
        return 0


def chunk_text(text: str, chunk_size: int = 600, overlap: int = 80) -> list:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        chunk = " ".join(words[start:start + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def ingest_documents():
    ensure_collection()

    if get_collection_count() > 0:
        print(f"[RAG] {get_collection_count()} chunks already stored. Skipping.")
        return

    documents = load_all_documents(DRAFTS_DATA_PATH)
    if not documents:
        print("[RAG] No documents found. Add RTF/DOCX files to data/drafts/")
        return

    all_ids, all_texts, all_metadatas = [], [], []

    for doc in documents:
        for i, chunk in enumerate(chunk_text(doc["text"])):
            all_ids.append(str(uuid.uuid4()))
            all_texts.append(chunk)
            all_metadatas.append({
                "filename": doc["metadata"]["filename"],
                "category": doc["metadata"]["category"],
                "chunk_index": i,
            })

    model = get_embedding_model()
    print(f"[RAG] Generating embeddings for {len(all_texts)} chunks...")
    all_embeddings = []
    batch_size = 64

    for i in range(0, len(all_texts), batch_size):
        batch = all_texts[i:i + batch_size]
        embeddings = model.encode(batch, show_progress_bar=False).tolist()
        all_embeddings.extend(embeddings)
        print(f"[RAG] Embedded {min(i + batch_size, len(all_texts))}/{len(all_texts)}", end="\r")

    print(f"\n[RAG] Storing {len(all_texts)} chunks in Qdrant...")
    client = get_qdrant()
    store_batch = 256

    for i in range(0, len(all_texts), store_batch):
        points = [
            PointStruct(
                id=all_ids[i + j],
                vector=all_embeddings[i + j],
                payload={"text": all_texts[i + j], **all_metadatas[i + j]}
            )
            for j in range(min(store_batch, len(all_texts) - i))
        ]
        client.upsert(collection_name=COLLECTION_NAME, points=points)

    print(f"[RAG] Done. {get_collection_count()} chunks stored.")


def search_drafts(query: str, n_results: int = 5, category_filter: str = None) -> list:
    ensure_collection()

    if get_collection_count() == 0:
        print("[RAG] Empty collection. Run ingest.py first.")
        return []

    model = get_embedding_model()
    query_embedding = model.encode([query]).tolist()[0]

    query_filter = None
    if category_filter:
        query_filter = Filter(
            must=[FieldCondition(key="category", match=MatchValue(value=category_filter))]
        )

    results = get_qdrant().search(
        collection_name=COLLECTION_NAME,
        query_vector=query_embedding,
        limit=n_results,
        query_filter=query_filter,
        with_payload=True,
    )

    output = []
    for r in results:
        if r.score < 0.15:
            continue
        output.append({
            "text": r.payload.get("text", ""),
            "metadata": {
                "filename": r.payload.get("filename", ""),
                "category": r.payload.get("category", ""),
                "chunk_index": r.payload.get("chunk_index", 0),
            },
            "score": r.score,
        })

    return output