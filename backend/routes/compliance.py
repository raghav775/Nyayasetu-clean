from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from models.database import get_db, User
from models.schemas import ComplianceAlertResponse, ComplianceCheckRequest, ComplianceCheckResponse
from utils.auth import get_current_user
from services.compliance_fetcher import refresh_compliance_alerts, get_active_alerts
from services.llm import call_llm, LLMUnavailableError
import json
import re

router = APIRouter()


@router.get("/alerts", response_model=List[ComplianceAlertResponse])
def get_alerts(
    law_area: Optional[str] = Query(None, description="Filter: labour, data_privacy, corporate"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_active_alerts(db, law_area=law_area)


@router.post("/refresh")
def refresh_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    refresh_compliance_alerts(db)
    return {"message": "Compliance alerts refreshed successfully"}


@router.post("/check", response_model=ComplianceCheckResponse)
def check_compliance(
    payload: ComplianceCheckRequest,
    current_user: User = Depends(get_current_user)
):
    system_prompt = """You are an Indian legal compliance expert.
Analyze the given business activity or document description and identify:
1. Any compliance issues under Indian law
2. Specific recommendations to achieve compliance
3. Relevant laws and regulations that apply

Respond ONLY in this JSON format:
{
  "is_compliant": true/false,
  "issues": ["issue 1", "issue 2"],
  "recommendations": ["recommendation 1", "recommendation 2"],
  "relevant_laws": ["law 1", "law 2"]
}"""

    user_message = f"""Check compliance for the following under Indian law:

{payload.description}

Check against: Labour laws, Data Privacy (PDPA/IT Act), Corporate law (Companies Act 2013), Contract Act, and any other applicable Indian regulations."""

    try:
        raw = call_llm(system_prompt, user_message)
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            return ComplianceCheckResponse(**data)
    except LLMUnavailableError:
        raise
    except Exception as e:
        print(f"[Compliance] Parse error: {e}")

    return ComplianceCheckResponse(
        is_compliant=False,
        issues=["Unable to complete compliance check. Please try again."],
        recommendations=["Please consult a qualified advocate for compliance review."],
        relevant_laws=[]
    )
