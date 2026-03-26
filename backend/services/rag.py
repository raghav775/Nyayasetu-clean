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
DATA_PATH = os.path.join(os.getcwd(), "data/drafts")
COLLECTION_NAME = "nyayasetu_legal_docs"
VECTOR_SIZE = 384

print("[RAG] Loading embedding model (all-MiniLM-L6-v2)...")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
print("[RAG] Embedding model ready.")

qdrant = QdrantClient(path=QDRANT_PATH)


def ensure_collection():
    existing = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION_NAME not in existing:
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


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


def get_collection_count() -> int:
    try:
        ensure_collection()
        return qdrant.count(collection_name=COLLECTION_NAME).count
    except Exception:
        return 0


def ingest_documents():
    ensure_collection()

    if get_collection_count() > 0:
        print(f"[RAG] {get_collection_count()} chunks already stored. Skipping ingestion.")
        print("[RAG] To re-ingest, delete the qdrant_db folder and run again.")
        return

    documents = load_all_documents(DATA_PATH)
    if not documents:
        print("[RAG] No documents found. Add RTF/DOCX files to data/drafts/")
        return

    all_ids = []
    all_texts = []
    all_metadatas = []

    for doc in documents:
        for i, chunk in enumerate(chunk_text(doc["text"])):
            all_ids.append(str(uuid.uuid4()))
            all_texts.append(chunk)
            all_metadatas.append({
                "filename": doc["metadata"]["filename"],
                "category": doc["metadata"]["category"],
                "chunk_index": i,
            })

    print(f"[RAG] Generating embeddings for {len(all_texts)} chunks...")
    batch_size = 64
    all_embeddings = []

    for i in range(0, len(all_texts), batch_size):
        batch = all_texts[i:i + batch_size]
        embeddings = embedding_model.encode(batch, show_progress_bar=False).tolist()
        all_embeddings.extend(embeddings)
        done = min(i + batch_size, len(all_texts))
        print(f"[RAG] Embedded {done}/{len(all_texts)}", end="\r")

    print(f"\n[RAG] Storing {len(all_texts)} chunks in Qdrant...")
    store_batch = 256
    for i in range(0, len(all_texts), store_batch):
        points = [
            PointStruct(
                id=all_ids[i + j],
                vector=all_embeddings[i + j],
                payload={
                    "text": all_texts[i + j],
                    **all_metadatas[i + j]
                }
            )
            for j in range(min(store_batch, len(all_texts) - i))
        ]
        qdrant.upsert(collection_name=COLLECTION_NAME, points=points)

    print(f"[RAG] Done. {get_collection_count()} chunks stored.")


def search_drafts(query: str, n_results: int = 5, category_filter: str = None) -> list:
    ensure_collection()

    if get_collection_count() == 0:
        print("[RAG] Empty collection. Run ingest.py first.")
        return []

    # Expand query with general Indian law context only
    expanded_query = f"{query} Indian law legal case judgment"

    query_embedding = embedding_model.encode([expanded_query]).tolist()[0]

    query_filter = None
    if category_filter:
        query_filter = Filter(
            must=[FieldCondition(key="category", match=MatchValue(value=category_filter))]
        )

    results = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_embedding,
        limit=10,
        query_filter=query_filter,
        with_payload=True,
    )

    output = []
    for r in results:
        output.append({
            "text": r.payload.get("text", ""),
            "metadata": {
                "filename": r.payload.get("filename", ""),
                "category": r.payload.get("category", ""),
                "chunk_index": r.payload.get("chunk_index", 0),
            },
            "score": r.score,
        })

    print("RAW SCORES:", [r.score for r in results])

    return output