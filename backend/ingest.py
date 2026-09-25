from dotenv import load_dotenv
load_dotenv()

from services.rag import ingest_documents

if __name__ == "__main__":
    print("=" * 55)
    print("NyayaSetu — Document Ingestion Pipeline")
    print("=" * 55)
    print("This will load all RTF/DOCX files from data/drafts/")
    print("into the Qdrant vector database.")
    print("This runs ONCE and takes 10-15 minutes.")
    print("=" * 55)
    ingest_documents()
    print("=" * 55)
    print("Done! You can now start the server:")
    print("uvicorn main:app --reload --port 8000")
    print("=" * 55)
