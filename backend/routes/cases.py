from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from models.database import get_db, User, QueryLog
from models.schemas import CaseSearchRequest, CaseSearchResponse, SearchSource, LiveCase
from services.rag import search_drafts
from services.scraper import scrape_indian_kanoon
from services.llm import call_llm
from utils.auth import get_current_user
from utils.encryption import encrypt

router = APIRouter()


@router.post("/search", response_model=CaseSearchResponse)
def search_cases(
    req: CaseSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    rag_results = search_drafts(req.query, n_results=req.n_results)
    live_results = scrape_indian_kanoon(req.query, max_results=5)

    rag_context = "\n\n---\n\n".join([
        f"Document: {r['metadata']['filename']} | Category: {r['metadata']['category']}\n{r['text']}"
        for r in rag_results
    ]) if rag_results else "No matching documents in local database."

    live_context = "\n\n".join([
        f"Case: {r['title']}\nLink: {r['link']}\nExcerpt: {r['snippet']}"
        for r in live_results
    ]) if live_results else "No live results available right now."

    system_prompt = """You are NyayaSetu, an expert Indian legal research assistant.
Your job is to find relevant case law and legal precedents for advocates and legal interns.

STRICT RULES:
- Only cite cases that appear in the provided context
- Never invent or hallucinate case names, citations, or judgments
- If a case is from Indian Kanoon results, always include its link
- Structure your response clearly

Format your response as:
1. RELEVANT LEGAL PRINCIPLES
2. APPLICABLE CASES AND PRECEDENTS (with citations)
3. KEY TAKEAWAYS

Be precise and professional."""

    user_message = f"""Legal Research Query: {req.query}

--- LOCAL LEGAL DATABASE ---
{rag_context}

--- LIVE CASES FROM INDIAN KANOON ---
{live_context}

Provide a structured legal research response. Only cite cases present in the above context."""

    answer = call_llm(system_prompt, user_message)

    try:
        log = QueryLog(
            user_id=current_user.id,
            query_type="case_search",
            encrypted_query=encrypt(req.query),
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
        for r in rag_results
    ]

    live_cases = [
        LiveCase(
            title=r["title"],
            link=r["link"],
            snippet=r["snippet"],
            source=r["source"],
            keywords=r.get("keywords", []),  # ← THIS WAS MISSING
        )
        for r in live_results
    ]

    return CaseSearchResponse(
        query=req.query,
        answer=answer,
        sources=sources,
        live_cases=live_cases,
    )