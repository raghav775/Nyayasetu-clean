from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from models.database import get_db, User, QueryLog
from models.schemas import (
    DraftRequest, DraftResponse,
    ContradictionRequest, ContradictionResponse, ContradictionPoint,
    SearchSource
)
from services.rag import search_drafts
from services.llm import call_llm
from services.contradiction import find_contradictions
from utils.auth import get_current_user
from utils.encryption import encrypt

router = APIRouter()


@router.post("/draft", response_model=DraftResponse)
def generate_draft(
    req: DraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not req.description.strip():
        raise HTTPException(status_code=400, detail="Description cannot be empty")

    search_query = f"{req.category} {req.description}" if req.category else req.description

    # Always search WITHOUT category filter — category names may not match folder names
    results = search_drafts(search_query, n_results=req.n_results)

    if not results:
        results = search_drafts(req.description, n_results=req.n_results)

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No templates found. Make sure you have run ingest.py first."
        )

    context = "\n\n---\n\n".join([
        f"Template: {r['metadata']['filename']}\nCategory: {r['metadata']['category']}\n\n{r['text']}"
        for r in results
    ])

    system_prompt = """You are NyayaSetu, an expert Indian legal document drafter.
You generate complete, accurate, and professionally formatted legal documents.

STRICT RULES:
- Follow proper Indian legal formatting and structure
- Use correct Indian legal terminology
- Include ALL standard clauses for the document type
- Use placeholders: [PARTY NAME], [DATE], [ADDRESS], [AMOUNT], [COURT NAME] where needed
- Number all clauses properly
- Include WHEREAS clauses where applicable
- Include NOW THEREFORE clause
- End with proper execution block (signatures, witnesses, notary)
- Do not leave any section incomplete or vague
- The document must be ready to use after filling in placeholders"""

    user_message = f"""Draft Request: {req.description}
{f"Document Category: {req.category}" if req.category else ""}

Reference Templates from Database:
{context}

Generate a complete, properly formatted legal document under Indian law."""

    draft = call_llm(system_prompt, user_message)

    try:
        log = QueryLog(
            user_id=current_user.id,
            query_type="draft",
            encrypted_query=encrypt(req.description),
        )
        db.add(log)
        db.commit()
    except Exception:
        pass

    sources = [
        SearchSource(
            filename=r["metadata"]["filename"],
            category=r["metadata"]["category"],
            score=round(r["score"], 3),
        )
        for r in results
    ]

    return DraftResponse(
        description=req.description,
        draft=draft,
        sources=sources,
    )


@router.post("/scan-contradictions", response_model=ContradictionResponse)
def scan_contradictions(
    req: ContradictionRequest,
    current_user: User = Depends(get_current_user)
):
    if not req.document_a.strip() or not req.document_b.strip():
        raise HTTPException(
            status_code=400,
            detail="Both Document A and Document B must have content"
        )

    result = find_contradictions(req.document_a, req.document_b)

    contradictions = [
        ContradictionPoint(**c)
        for c in result.get("contradictions", [])
    ]

    return ContradictionResponse(
        total_contradictions=result.get("total_contradictions", 0),
        contradictions=contradictions,
        overall_compatibility=result.get("overall_compatibility", "Unable to determine"),
    )