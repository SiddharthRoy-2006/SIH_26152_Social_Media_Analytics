from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.database.connection import check_connection, close_pool, run_migrations
from backend.database.storage_manager import get_storage_usage
from backend.routes.analysis import router as analysis_router
from backend.routes.audit import router as audit_router
from backend.routes.auth import router as auth_router
from backend.routes.chat import router as chat_router
from backend.routes.credentials import router as credentials_router
from backend.routes.general import router as general_router
from backend.schemas import HealthResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Pre-warm the connector registry singleton so it is always the
    # same instance before any HTTP request arrives. This prevents the race
    # condition where credentials are saved to a different instance than the
    # one used for analysis.
    import asyncio
    try:
        from backend.connectors.registry import get_registry
        get_registry()  # creates and caches the global singleton now
        logger.info("Connector registry pre-warmed at startup.")
    except Exception as exc:
        logger.warning("Could not pre-warm connector registry: %s", exc)

    # Apply database migrations asynchronously without blocking startup
    try:
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, run_migrations)
    except Exception as exc:
        logger.warning("Database startup check encountered: %s", exc)
    yield
    # Shutdown: Cleanly close connection pool
    close_pool()


app = FastAPI(title="SocialIQ Analytics API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins) if "*" not in settings.cors_origins else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis_router)
app.include_router(general_router)
app.include_router(credentials_router)
app.include_router(chat_router)
app.include_router(auth_router)
app.include_router(audit_router, prefix="/api")
app.include_router(audit_router)


@app.get("/")
def home():
    return {
        "message": "SocialIQ Analytics API is running",
        "docs": "/docs",
        "data_mode": settings.data_mode,
        "version": "0.2.0",
    }


@app.get("/health", response_model=HealthResponse)
def health():
    """Dedicated lightweight health-check endpoint for fast monitoring and discovery."""
    from backend.blockchain.service import get_blockchain_service
    from backend.connectors.registry import get_registry

    registry = get_registry()
    db_health = check_connection(cached=True)
    storage_info = get_storage_usage(cached=True, fast=True)
    blockchain_info = get_blockchain_service().get_health()

    return HealthResponse(
        status="ok",
        data_mode=settings.data_mode,
        version="0.2.0",
        platforms=registry.to_dict(),
        database=db_health,
        storage=storage_info,
        blockchain=blockchain_info,
    )

