from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Primitive types
# ---------------------------------------------------------------------------

Platform = Literal["Instagram", "YouTube", "Facebook", "Twitter / X", "All Platforms"]
Period = Literal["Today", "Last 7 Days", "Last 30 Days", "1 Year"]
ChartPeriod = Literal["Daily", "Weekly", "Monthly", "Yearly"]
Mode = Literal["general", "topic"]


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class AnalysisRequest(BaseModel):
    topic: str = Field(default="", max_length=160)
    query: str = Field(default="", max_length=160)
    platform: Platform = "Instagram"
    period: Period = "Last 30 Days"
    chart_period: ChartPeriod = "Monthly"
    refresh_tick: int = Field(default=0, ge=0)   # for gradual demo drift; 0 = auto


class GeneralRequest(BaseModel):
    platform: Platform = "All Platforms"
    period: Period = "Last 30 Days"
    chart_period: ChartPeriod = "Monthly"
    refresh_tick: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class AnalysisResponse(BaseModel):
    """
    Stable contract consumed by the existing frontend normalizer.

    All new fields added in the upgrade are OPTIONAL with safe defaults so
    that the EmptyDataProvider and existing tests remain unaffected.
    """

    # --- core (unchanged) ---------------------------------------------------
    platform: str
    topic: str
    query: str
    period: str
    chart_period: str
    data_available: bool
    source: Literal["empty", "demo", "provider"]
    metrics: dict
    audience: dict
    sentiment: dict
    emotions: dict
    trending: dict
    network: dict
    activity: list[int]
    growth_series: list[int]
    insights: dict

    # --- extended fields (all optional with safe defaults) ------------------
    # Structured AI insight cards [{type, icon, severity, title, text}]
    ai_insights: list[dict[str, Any]] = Field(default_factory=list)

    # Sentiment over time (index 0 = oldest)
    sentiment_series: list[int] = Field(default_factory=list)

    # Top trending topics [{rank, name, score, growth_pct, direction, keyword, influencer_name, influencer_score, mentions}]
    top_trends: list[dict[str, Any]] = Field(default_factory=list)

    # Influencer list [{rank, name, score, platform, communities, topic}]
    influencers: list[dict[str, Any]] = Field(default_factory=list)

    # Network graph data {nodes:[{id,label,community,size,x,y}], edges:[{source,target,weight}], propagation:[{step,label,nodes,reach}]}
    network_graph: dict[str, Any] = Field(default_factory=dict)

    # Extended demographics
    geo_distribution: dict[str, int] = Field(default_factory=dict)
    language_distribution: dict[str, int] = Field(default_factory=dict)
    interest_segments: dict[str, int] = Field(default_factory=dict)

    # Activity over time (more granular than activity[5])
    activity_series: list[int] = Field(default_factory=list)

    # Engagement over time
    engagement_series: list[float] = Field(default_factory=list)

    # Mode used to generate this response
    mode: Mode = "topic"

    # Refresh tick echoed back (useful for frontend to detect drift)
    refresh_tick: int = 0


class GeneralResponse(AnalysisResponse):
    """
    Ecosystem-wide overview response.  Inherits all AnalysisResponse fields.
    `mode` is always 'general'.  `topic` and `query` are empty strings.
    """
    mode: Mode = "general"


class HealthResponse(BaseModel):
    status: str
    data_mode: str
    version: str
