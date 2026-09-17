"""Public v2 forecast schemas with explicit uncertainty and evidence."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.graph.schema import GraphCoverageSummary
from app.intelligence.effect_decomposition import EffectDecomposition
from app.intelligence.regime import MarketRegime


class ForecastDirection(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    UNCERTAIN = "UNCERTAIN"


class EventSummary(BaseModel):
    title: str
    category: str
    event_date: datetime
    estimated_disruption_magnitude: float | None = None
    estimated_duration_days: int | None = None
    affected_tickers: list[str] = Field(default_factory=list)


class PropagationPath(BaseModel):
    entities: list[str]
    relationship_types: list[str]
    channel_types: list[str]
    propagation_depth: int = Field(ge=1)
    cumulative_lag_days: int = Field(ge=0)
    edge_confidence: float = Field(ge=0.0, le=1.0)
    evidence_sources: list[str] = Field(default_factory=list)
    temporal_approximation: bool = False


class HistoricalSupport(BaseModel):
    sample_count: int = Field(ge=0)
    supporting_event_ids: list[str] = Field(default_factory=list)
    estimation_method: str
    is_prior: bool
    calibration_window: str | None = None
    standard_error: float | None = None


class ContradictingEvent(BaseModel):
    event_id: str
    observed_return: float
    reason: str


class EntityImpact(BaseModel):
    ticker: str
    direction: ForecastDirection
    direction_probability: float = Field(ge=0.0, le=1.0)
    model_confidence: float = Field(ge=0.0, le=1.0)
    confidence_is_calibrated: bool
    expected_return: float
    # Explicitly named range from empirical p25/p75 quantile summaries.
    return_range: tuple[float, float]
    return_p50: float
    time_horizon_days: int
    propagation_depth: int = Field(ge=1)
    effect_decomposition: EffectDecomposition
    causal_paths: list[PropagationPath] = Field(default_factory=list)
    historical_support: HistoricalSupport
    contradicting_evidence: list[ContradictingEvent] = Field(default_factory=list)
    insufficient_historical_evidence: bool
    uncertainty_sources: list[str] = Field(default_factory=list)


class HistoricalEvidenceSummary(BaseModel):
    comparable_event_count: int = Field(ge=0)
    observation_count: int = Field(ge=0)
    includes_seeded_demo_data: bool = False
    caveat: str


class DataQualitySummary(BaseModel):
    provider_statuses: dict[str, str] = Field(default_factory=dict)
    source_quality_score: float = Field(ge=0.0, le=1.0)
    limitations: list[str] = Field(default_factory=list)


class ProbabilisticForecast(BaseModel):
    """A calibrated, evidence-scoped forecast—not a claim of certainty."""

    event: EventSummary
    current_regime: MarketRegime
    primary_impacts: list[EntityImpact] = Field(default_factory=list)
    secondary_impacts: list[EntityImpact] = Field(default_factory=list)
    tertiary_impacts: list[EntityImpact] = Field(default_factory=list)
    potential_beneficiaries: list[EntityImpact] = Field(default_factory=list)
    historical_evidence: HistoricalEvidenceSummary
    uncertainty_sources: list[str] = Field(default_factory=list)
    data_quality: DataQualitySummary
    graph_coverage: GraphCoverageSummary
    limitations: list[str] = Field(default_factory=list)
    insufficient_evidence_flags: list[str] = Field(default_factory=list)
