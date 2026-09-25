import os

# Must run before the imports below: several modules read env vars at import time.
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apscheduler.schedulers.background import BackgroundScheduler
from models.database import create_tables, engine, SessionLocal
from services.compliance_fetcher import refresh_compliance_alerts
from services.llm import LLMUnavailableError, llm_status
from routes import auth, workflow, compliance, documents, cases, legal_aid

app = FastAPI(
    title="NyayaSetu API",
    description="AI-powered legal assistant — Auth, Workflow, Compliance, Documents, Case Search, Legal Aid",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

allowed_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://nyayasetu.vercel.app",
]
# Extra origins (e.g. a custom domain) as a comma-separated list.
allowed_origins += [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = BackgroundScheduler()


@app.on_event("startup")
def on_startup():
    create_tables()
    print("[NyayaSetu] Database tables ready.")

    def scheduled_refresh():
        db = SessionLocal()
        try:
            refresh_compliance_alerts(db)
        finally:
            db.close()

    scheduler.add_job(scheduled_refresh, "interval", hours=12, id="compliance_refresh")
    scheduler.start()
    print("[NyayaSetu] Compliance auto-refresh every 12 hours.")
    print("[NyayaSetu] Server ready at http://localhost:8000/docs")


@app.on_event("shutdown")
def on_shutdown():
    scheduler.shutdown()
    print("[NyayaSetu] Scheduler stopped.")


@app.exception_handler(LLMUnavailableError)
async def llm_unavailable_handler(request: Request, exc: LLMUnavailableError):
    print(f"[LLM] {request.method} {request.url.path} -> 503 ({exc.reason})")
    return JSONResponse(status_code=503, content={"detail": exc.message})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    print(f"[Error] Unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again."},
    )


app.include_router(auth.router,       prefix="/auth",       tags=["Authentication"])
app.include_router(workflow.router,   prefix="/workflow",   tags=["Workflow & Tasks"])
app.include_router(compliance.router, prefix="/compliance", tags=["Compliance Monitor"])
app.include_router(documents.router,  prefix="/documents",  tags=["Document Automation"])
app.include_router(cases.router,      prefix="/cases",      tags=["Case Search"])
app.include_router(legal_aid.router,  prefix="/legal-aid",  tags=["Legal Aid"])


@app.get("/", tags=["Health"])
def root():
    return {
        "app": "NyayaSetu",
        "tagline": "Bridge to Justice",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health():
    # Deployment checklist at a glance — booleans/names only, never secrets.
    return {
        "status": "ok",
        "llm": llm_status(),  # is GROQ_API_KEY set, which models, why the last AI call failed
        "config": {
            "database": engine.dialect.name,  # "sqlite" = accounts are lost on every Render restart
            "vector_db": "cloud" if os.getenv("QDRANT_URL") and os.getenv("QDRANT_API_KEY") else "local",
            "indian_kanoon_api": bool(os.getenv("INDIAN_KANOON_TOKEN", "").strip()),  # false = scraper only
        },
    }
