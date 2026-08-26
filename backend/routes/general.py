"""
General (ecosystem-wide) analytics endpoint.

Returns a GeneralResponse which is a superset of AnalysisResponse.
The frontend calls GET /general for the General dashboard.
"""
import time

from fastapi import APIRouter, Depends, Query

from backend.core.config import settings
from backend.schemas import ChartPeriod, GeneralRequest, GeneralResponse, Period, Platform
from backend.services.general_service import GeneralDataProvider, get_general_provider

router = APIRouter(tags=["general"])


def provider() -> GeneralDataProvider:
    return get_general_provider(settings.data_mode)


def _auto_tick() -> int:
    return int(time.time() // 60)


@router.get("/general", response_model=GeneralResponse)
def get_general(
    platform: Platform = "All Platforms",
    period: Period = "Last 30 Days",
    chart_period: ChartPeriod = "Monthly",
    refresh_tick: int = Query(default=0, ge=0),
    data_provider: GeneralDataProvider = Depends(provider),
) -> GeneralResponse:
    """Return ecosystem-wide social-media intelligence (no topic required)."""
    tick = refresh_tick if refresh_tick > 0 else _auto_tick()
    request = GeneralRequest(
        platform=platform,
        period=period,
        chart_period=chart_period,
        refresh_tick=tick,
    )
    return data_provider.get_general(request)
