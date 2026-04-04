import os
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter,
    FieldCondition, MatchValue
)
from groq import Groq
from utils.document_loader import load_all_documents

QDRANT_PATH = os.getenv("QDRANT_PATH", "./qdrant_db")
DRAFTS_DATA_PATH = os.getenv("DRAFTS_DATA_PATH", "../data/drafts")
COLLECTION_NAME = "nyayasetu_legal_docs"
VECTOR_SIZE = 1536

_qdrant_client = None


def get_qdrant():
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(path=QDRANT_PATH)
    return _qdrant_client


def get_embeddings(texts: list) -> list:
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    result = []
    # Groq embeddings API processes one at a time
    for text in texts:
        response = client.embeddings.create(
            model="nomic-embed-text-v1_5",
            input=text
        )
        result.append(response.data[0].embedding)
    return result


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
        print("[RAG] No documents found.")
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

    print(f"[RAG] Generating embeddings for {len(all_texts)} chunks via Groq...")
    all_embeddings = get_embeddings(all_texts)

    print(f"[RAG] Storing {len(all_texts)} chunks in Qdrant...")
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
        return []

    query_embedding = get_embeddings([query])[0]

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