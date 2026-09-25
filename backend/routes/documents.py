from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from models.database import get_db, User, QueryLog
from models.schemas import (
    DraftRequest, DraftResponse,
    ContradictionRequest, ContradictionResponse, ContradictionPoint,
    SearchSource
)
from services.rag import search_drafts
from services.llm import call_llm, clip, LLMUnavailableError
from services.contradiction import find_contradictions
from utils.auth import get_current_user
from utils.encryption import encrypt

router = APIRouter()

# Keep prompt + answer inside Groq's free-tier request limit (see services/llm.py).
# 5 templates x 2400 chars is ~3k tokens, leaving room for a long generated document.
LLM_TEMPLATE_CHARS = 2400
DRAFT_MAX_TOKENS = 2800


@router.post("/draft", response_model=DraftResponse)
def generate_draft(
    req: DraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not req.description.strip():
        raise HTTPException(status_code=400, detail="Description cannot be empty")

    try:
        search_query = f"{req.category} {req.description}" if req.category else req.description
        results = search_drafts(search_query, n_results=req.n_results)
        if not results:
            results = search_drafts(req.description, n_results=req.n_results)

        # No templates (e.g. vector DB unreachable or not ingested yet): still draft from
        # standard Indian legal practice — the UI already handles an empty sources list.
        context = "\n\n---\n\n".join([
            f"Template: {r['metadata']['filename']}\nCategory: {r['metadata']['category']}\n\n{clip(r['text'], LLM_TEMPLATE_CHARS)}"
            for r in results
        ]) if results else "No reference templates available — draft from standard Indian legal practice."

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
- The document must be ready to use after filling in placeholders
- Always cite 2-3 real landmark Indian Supreme Court or High Court cases relevant to the document type
- Use actual case names, year, and citation (e.g. Arnesh Kumar v. State of Bihar (2014) 8 SCC 273)"""

        user_message = f"""Draft Request: {req.description}
{f"Document Category: {req.category}" if req.category else ""}

Reference Templates from Database:
{context}

Generate a complete, properly formatted legal document under Indian law."""

        draft = call_llm(system_prompt, user_message, max_tokens=DRAFT_MAX_TOKENS)

        try:
            db.add(QueryLog(
                user_id=current_user.id,
                query_type="draft",
                encrypted_query=encrypt(req.description),
            ))
            db.commit()
        except Exception:
            pass

        return DraftResponse(
            description=req.description,
            draft=draft,
            sources=[
                SearchSource(
                    filename=r["metadata"]["filename"],
                    category=r["metadata"]["category"],
                    score=round(r["score"], 3),
                )
                for r in results
            ],
        )
    except (HTTPException, LLMUnavailableError):
        raise
    except Exception as e:
        print(f"[Documents] Unhandled error: {e}")
        raise HTTPException(status_code=500, detail="Draft generation failed. Please try again.")


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

    # A malformed AI reply is a failed analysis, not "no contradictions found".
    if result.get("_error"):
        raise HTTPException(status_code=502, detail=result["_error"])

    contradictions = [
        ContradictionPoint(**c)
        for c in result.get("contradictions", [])
    ]

    return ContradictionResponse(
        total_contradictions=result.get("total_contradictions", 0),
        contradictions=contradictions,
        overall_compatibility=result.get("overall_compatibility", "Unable to determine"),
    )