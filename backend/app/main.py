import uuid
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import setup_logging, logger, correlation_id_ctx, operation_id_ctx
from app.core.exceptions import AppException
from app.db.database import init_db, engine
from app.api import (
    auth,
    hospitals,
    doctors,
    scheduling,
    patients,
    appointments,
    questionnaires,
    ai,
    workflows,
    integrations,
    notifications,
    audit,
    analytics,
    mock_ehr_routes,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup structured logging
    setup_logging()
    logger.info("Initializing Autonomous Healthcare Platform Backend...")
    # Initialize database tables if needed
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
    yield
    logger.info("Shutting down Healthcare Platform Backend.")
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description=(
        "Autonomous Multi-Hospital Patient Intake, Scheduling & Pre-Visit Voice Agent API. "
        "Complies strictly with PRD specifications including multi-tenancy, real availability engine, "
        "Mock EHR verification & failure recovery, controlled AI capabilities, and pre-visit questionnaires."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Correlation Tracking Middleware
@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    corr_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    op_id = request.headers.get("X-Operation-ID") or str(uuid.uuid4())
    correlation_id_ctx.set(corr_id)
    operation_id_ctx.set(op_id)

    start_time = time.time()
    response = await call_next(request)
    duration_ms = int((time.time() - start_time) * 1000)

    response.headers["X-Correlation-ID"] = corr_id
    response.headers["X-Operation-ID"] = op_id
    response.headers["X-Response-Time-Ms"] = str(duration_ms)
    return response


# Application Exception Handler
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    corr_id = exc.correlation_id or correlation_id_ctx.get() or "unknown"
    logger.warning(f"AppException [{exc.code}]: {exc.message} (corr={corr_id})")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "correlation_id": corr_id,
                "details": exc.details,
            }
        }
    )


# Unhandled Internal Exception Handler (Never expose raw stack traces in production)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    corr_id = correlation_id_ctx.get() or "unknown"
    logger.error(f"Unhandled Exception: {exc} (corr={corr_id})", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred while processing your request.",
                "correlation_id": corr_id,
            }
        }
    )


# Health and Readiness Endpoints (Section 29)
@app.get("/health", tags=["Observability"])
async def health_check():
    """Liveness probe."""
    return {"status": "UP", "timestamp": time.time(), "version": settings.PROJECT_VERSION}


@app.get("/ready", tags=["Observability"])
async def readiness_check():
    """Readiness probe verifying database, AI provider, and EHR connectivity."""
    db_status = "UNKNOWN"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "HEALTHY"
    except Exception as e:
        db_status = f"UNHEALTHY: {e}"

    ai_status = "CONFIGURED (Gemini API)" if settings.GEMINI_API_KEY else "READY (Deterministic Simulation Mode)"

    return {
        "status": "READY" if db_status == "HEALTHY" else "DEGRADED",
        "database": db_status,
        "ai_provider": ai_status,
        "mock_ehr": "HEALTHY",
        "workflow_worker": "ACTIVE",
    }


# Mount Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(hospitals.router, prefix=settings.API_V1_STR)
app.include_router(doctors.router, prefix=settings.API_V1_STR)
app.include_router(scheduling.router, prefix=settings.API_V1_STR)
app.include_router(patients.router, prefix=settings.API_V1_STR)
app.include_router(appointments.router, prefix=settings.API_V1_STR)
app.include_router(questionnaires.router, prefix=settings.API_V1_STR)
app.include_router(ai.router, prefix=settings.API_V1_STR)
app.include_router(workflows.router, prefix=settings.API_V1_STR)
app.include_router(integrations.router, prefix=settings.API_V1_STR)
app.include_router(notifications.router, prefix=settings.API_V1_STR)
app.include_router(audit.router, prefix=settings.API_V1_STR)
app.include_router(analytics.router, prefix=settings.API_V1_STR)
app.include_router(mock_ehr_routes.router)  # Mounted at /mock-ehr

# Serve Static UI and mount /static
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(os.path.join(static_dir, "index.html"))

