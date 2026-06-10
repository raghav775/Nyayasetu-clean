from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from models.database import get_db, User, QueryLog
from models.schemas import CaseSearchRequest, CaseSearchResponse, SearchSource, LiveCase
from services.rag import search_drafts
from services.scraper import search_cases as fetch_live_cases
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

    try:
        rag_results = search_drafts(req.query, n_results=req.n_results)
        live_results = fetch_live_cases(req.query, max_results=10, db=db)

        rag_context = "\n\n---\n\n".join([
            f"Document: {r['metadata']['filename']} | Category: {r['metadata']['category']}\n{r['text']}"
            for r in rag_results
        ]) if rag_results else "No matching documents in local database."

        live_context = "\n\n".join([
            f"Case: {r['title']}\nLink: {r['link']}\nExcerpt: {r['snippet']}"
            for r in live_results
        ]) if live_results else "No live results available right now."

        system_prompt = """You are NyayaSetu, an expert Indian legal research assistant specialising in landmark and leading case law.

Your task: for the given query, produce a COMPREHENSIVE reference of ALL relevant landmark and leading judgments.

RULES:
1. From the Indian Kanoon search results provided, include ONLY landmark or leading cases — skip trivial, procedural, or minor orders.
2. Beyond the provided results, list every other well-established landmark case you know for this legal topic — do not omit important ones.
3. For every case include: full case name · year · court · citation (if known) · the key legal principle it established.
4. For cases present in the Indian Kanoon results, always include their link.
5. For cases added from your legal knowledge, append "(verify citation)" after the citation.
6. Never fabricate case names, citations, courts, or facts.
7. Being exhaustive matters — missing a landmark case is worse than including too many.

Response format:
━━━ LEGAL PRINCIPLES ESTABLISHED ━━━
[Core doctrines and rules these landmark cases collectively set]

━━━ LANDMARK CASES — FROM SEARCH RESULTS ━━━
• [Full Case Name] ([Year]) | [Court] | [Citation]
  Key holding: [what was decided and why it is landmark]
  Link: [Indian Kanoon link]

━━━ LANDMARK CASES — FROM LEGAL KNOWLEDGE ━━━
• [Full Case Name] ([Year]) | [Court] | [Citation or "verify citation"]
  Key holding: [what was decided and why it is landmark]

━━━ PRACTICAL TAKEAWAYS FOR ADVOCATES ━━━
[How to apply these precedents in practice]"""

        user_message = f"""Legal Research Query: {req.query}

--- LOCAL LEGAL DATABASE ---
{rag_context}

--- INDIAN KANOON SEARCH RESULTS ---
{live_context}

Identify ALL landmark and leading cases for this query. Use the search results above AND your own legal knowledge to ensure complete coverage."""

        answer = call_llm(system_prompt, user_message)

        try:
            db.add(QueryLog(
                user_id=current_user.id,
                query_type="case_search",
                encrypted_query=encrypt(req.query),
            ))
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
                keywords=r.get("keywords", []),
            )
            for r in live_results
        ]

        return CaseSearchResponse(
            query=req.query,
            answer=answer,
            sources=sources,
            live_cases=live_cases,
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Cases] Unhandled error: {e}")
        raise HTTPException(status_code=500, detail="Case search failed. Please try again.")