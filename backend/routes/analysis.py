import time

from fastapi import APIRouter, Depends, Query

from backend.core.config import settings
from backend.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    ChartPeriod,
    Period,
    Platform,
)
from backend.services.analysis_service import PlatformDataProvider, get_provider

router = APIRouter(tags=["analysis"])


def provider() -> PlatformDataProvider:
    return get_provider(settings.data_mode)


def _auto_tick() -> int:
    """Return a 60-second epoch tick for gradual demo drift."""
    return int(time.time() // 60)


@router.get("/analysis", response_model=AnalysisResponse)
def get_analysis(
    topic: str = Query(default="", max_length=160),
    query: str = Query(default="", max_length=160),
    platform: Platform = "Instagram",
    period: Period = "Last 30 Days",
    chart_period: ChartPeriod = "Monthly",
    refresh_tick: int = Query(default=0, ge=0),
    data_provider: PlatformDataProvider = Depends(provider),
) -> AnalysisResponse:
    """Return campaign-specific data from the configured provider."""
    tick = refresh_tick if refresh_tick > 0 else _auto_tick()
    request = AnalysisRequest(
        topic=topic.strip(),
        query=query.strip(),
        platform=platform,
        period=period,
        chart_period=chart_period,
        refresh_tick=tick,
    )
    return data_provider.get_analysis(request)


@router.get("/analytics", response_model=AnalysisResponse, deprecated=True)
def legacy_analytics(
    platform: Platform = "Instagram",
    data_provider: PlatformDataProvider = Depends(provider),
) -> AnalysisResponse:
    """Compatibility endpoint; use /analysis for campaign-aware requests."""
    return data_provider.get_analysis(
        AnalysisRequest(platform=platform, refresh_tick=_auto_tick())
    )
