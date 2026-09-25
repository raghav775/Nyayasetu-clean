from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
from models.database import get_db, User, Workflow, Task
from models.schemas import (
    WorkflowCreate, WorkflowResponse, TaskCreate,
    TaskResponse, GenerateWorkflowRequest
)
from utils.auth import get_current_user
from services.llm import call_llm, LLMUnavailableError
import json
import re

router = APIRouter()


def ai_generate_tasks(work_description: str, company_a: str, company_b: str) -> list:
    system_prompt = """You are an expert Indian legal workflow planner.
Given a legal work description, generate a complete ordered checklist of tasks and documents needed.
Include all required legal documents, filings, verifications, and procedures.

Respond ONLY in this exact JSON format:
[
  {
    "title": "Task title",
    "description": "What needs to be done",
    "document_type": "type of document if applicable, else null",
    "is_required": true,
    "order_index": 1
  }
]
Return only the JSON array, no other text."""

    user_message = f"""Generate a complete legal task checklist for:

Work: {work_description}
Company A: {company_a or "Party A"}
Company B: {company_b or "Party B"}

Include all documents, verifications, filings, and steps needed under Indian law."""

    try:
        raw = call_llm(system_prompt, user_message)
        json_match = re.search(r'\[.*\]', raw, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except LLMUnavailableError as e:
        print(f"[Workflow] AI unavailable, using default checklist: {e.reason}")
    except Exception as e:
        print(f"[Workflow] Task parse error: {e}")

    return [
        {"title": "Review engagement documents", "description": "Review all provided documents", "document_type": None, "is_required": True, "order_index": 1},
        {"title": "Draft primary agreement", "description": "Prepare initial draft", "document_type": "Agreement", "is_required": True, "order_index": 2},
        {"title": "Client review and approval", "description": "Send for client review", "document_type": None, "is_required": True, "order_index": 3},
    ]


@router.post("/generate", response_model=WorkflowResponse, status_code=201)
def generate_workflow(
    payload: GenerateWorkflowRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    workflow = Workflow(
        user_id=current_user.id,
        title=payload.title,
        company_a=payload.company_a,
        company_b=payload.company_b,
        description=payload.work_description,
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)

    raw_tasks = ai_generate_tasks(
        payload.work_description,
        payload.company_a or "",
        payload.company_b or ""
    )

    tasks = []
    for t in raw_tasks:
        task = Task(
            workflow_id=workflow.id,
            title=t.get("title", "Task"),
            description=t.get("description"),
            document_type=t.get("document_type"),
            is_required=t.get("is_required", True),
            order_index=t.get("order_index", 0),
        )
        db.add(task)
        tasks.append(task)

    db.commit()

    result = WorkflowResponse(
        id=workflow.id,
        user_id=workflow.user_id,
        title=workflow.title,
        company_a=workflow.company_a,
        company_b=workflow.company_b,
        description=workflow.description,
        status=workflow.status,
        created_at=workflow.created_at,
        tasks=[TaskResponse.model_validate(t) for t in tasks]
    )
    return result


@router.post("/", response_model=WorkflowResponse, status_code=201)
def create_workflow(
    payload: WorkflowCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    workflow = Workflow(
        user_id=current_user.id,
        **payload.model_dump()
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return WorkflowResponse(
        **{c.name: getattr(workflow, c.name) for c in workflow.__table__.columns},
        tasks=[]
    )


@router.get("/", response_model=List[WorkflowResponse])
def get_workflows(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    workflows = db.query(Workflow).filter(
        Workflow.user_id == current_user.id
    ).order_by(Workflow.created_at.desc()).all()

    result = []
    for w in workflows:
        tasks = db.query(Task).filter(Task.workflow_id == w.id).order_by(Task.order_index).all()
        result.append(WorkflowResponse(
            **{c.name: getattr(w, c.name) for c in w.__table__.columns},
            tasks=[TaskResponse.model_validate(t) for t in tasks]
        ))
    return result


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.user_id == current_user.id
    ).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    tasks = db.query(Task).filter(
        Task.workflow_id == workflow_id
    ).order_by(Task.order_index).all()

    return WorkflowResponse(
        **{c.name: getattr(workflow, c.name) for c in workflow.__table__.columns},
        tasks=[TaskResponse.model_validate(t) for t in tasks]
    )


@router.patch("/tasks/{task_id}/complete", response_model=TaskResponse)
def complete_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.is_completed = not task.is_completed
    task.completed_at = datetime.utcnow() if task.is_completed else None
    db.commit()
    db.refresh(task)
    return task


@router.post("/{workflow_id}/tasks", response_model=TaskResponse, status_code=201)
def add_task(
    workflow_id: str,
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.user_id == current_user.id
    ).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    task = Task(workflow_id=workflow_id, **payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task
