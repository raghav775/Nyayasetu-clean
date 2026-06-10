from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from models.database import create_tables, SessionLocal
from services.compliance_fetcher import refresh_compliance_alerts
from routes import auth, workflow, compliance, documents, cases, legal_aid

load_dotenv()

app = FastAPI(
    title="NyayaSetu API",
    description="AI-powered legal assistant — Auth, Workflow, Compliance, Documents, Case Search, Legal Aid",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://nyayasetu.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = BackgroundScheduler()


@app.on_event("startup")
def on_startup():
    create_tables()
    print("[NyayaSetu] Database tables ready.")
    print("[NyayaSetu] Server ready.")

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
    return {"status": "ok"}
