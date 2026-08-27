from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.routes.analysis import router as analysis_router
from backend.routes.credentials import router as credentials_router
from backend.routes.general import router as general_router
from backend.schemas import HealthResponse

app = FastAPI(title="SocialIQ Analytics API", version="0.2.0")

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
    """Dedicated health-check endpoint for monitoring and frontend status checks."""
    from backend.connectors.registry import get_registry

    registry = get_registry()
    return HealthResponse(
        status="ok",
        data_mode=settings.data_mode,
        version="0.2.0",
        platforms=registry.to_dict(),
    )

