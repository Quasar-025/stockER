"""Evidence-backed causal graph contracts.

Relationship labels describe possible transmission mechanisms only.  They
cannot encode a return direction; outcome direction is estimated from
observations in ``historical_observations.py``.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class RelationshipType(StrEnum):
    SUPPLIES = "SUPPLIES"
    DEPENDS_ON = "DEPENDS_ON"
    COMPETES_WITH = "COMPETES_WITH"
    CORRELATED_WITH = "CORRELATED_WITH"
    INFLUENCES = "INFLUENCES"


class ChannelType(StrEnum):
    SUPPLY_EXPOSURE = "SUPPLY_EXPOSURE"
    DEPENDENCY = "DEPENDENCY"
    SUBSTITUTION = "SUBSTITUTION"
    COMMON_FACTOR = "COMMON_FACTOR"
    REGULATORY = "REGULATORY"


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    APPROXIMATE = "approximate"
    UNRESOLVED = "unresolved"


class EstimationMethod(StrEnum):
    OLS_REGRESSION = "ols_regression"
    BAYESIAN_PRIOR = "bayesian_prior"
    MANUAL_PRIOR = "manual_prior"
    INSUFFICIENT_DATA = "insufficient_data"


CHANNEL_FOR_RELATIONSHIP: dict[RelationshipType, ChannelType] = {
    RelationshipType.SUPPLIES: ChannelType.SUPPLY_EXPOSURE,
    RelationshipType.DEPENDS_ON: ChannelType.DEPENDENCY,
    RelationshipType.COMPETES_WITH: ChannelType.SUBSTITUTION,
    RelationshipType.CORRELATED_WITH: ChannelType.COMMON_FACTOR,
    RelationshipType.INFLUENCES: ChannelType.REGULATORY,
}


class EstimationMetadata(BaseModel):
    """Provenance of a coefficient or transmission estimate."""

    sample_count: int = Field(ge=0)
    estimation_method: EstimationMethod
    estimation_window: str | None = None
    standard_error: float | None = Field(default=None, ge=0.0)
    is_prior: bool

    @model_validator(mode="after")
    def validate_prior_labelling(self) -> "EstimationMetadata":
        if self.is_prior and self.estimation_method not in {
            EstimationMethod.BAYESIAN_PRIOR,
            EstimationMethod.MANUAL_PRIOR,
            EstimationMethod.INSUFFICIENT_DATA,
        }:
            raise ValueError("Prior estimates must use a prior or insufficient-data method")
        if not self.is_prior and self.estimation_method == EstimationMethod.INSUFFICIENT_DATA:
            raise ValueError("Insufficient-data estimates must be marked prior-based")
        return self


class CausalEdge(BaseModel):
    """A temporal, evidence-backed propagation channel.

    ``historical_coefficient`` may only be present when observations supported
    an estimate.  A cold-start edge has a conservative *direction-neutral*
    strength prior and is explicitly marked through estimation metadata.
    """

    source_entity: str = Field(min_length=1)
    target_entity: str = Field(min_length=1)
    relationship_type: RelationshipType
    channel_type: ChannelType
    strength: float = Field(ge=0.0, le=1.0)
    dependency_exposure: float = Field(ge=0.0, le=1.0)
    substitutability: float = Field(ge=0.0, le=1.0)
    historical_coefficient: float | None = None
    historical_observation_count: int = Field(ge=0)
    estimation_metadata: EstimationMetadata
    typical_time_lag_days: int = Field(ge=0)
    min_lag_days: int | None = Field(default=None, ge=0)
    max_lag_days: int | None = Field(default=None, ge=0)
    relationship_created_at: datetime
    relationship_verified_at: datetime | None = None
    source_date: datetime | None = None
    temporal_approximation: bool = False
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_count: int = Field(ge=1)
    evidence_sources: list[str] = Field(min_length=1)
    verification_status: VerificationStatus

    @model_validator(mode="after")
    def validate_edge_contract(self) -> "CausalEdge":
        expected_channel = CHANNEL_FOR_RELATIONSHIP[self.relationship_type]
        if self.channel_type != expected_channel:
            raise ValueError("Relationship type must map to its propagation channel")
        if (
            self.min_lag_days is not None
            and self.max_lag_days is not None
            and self.min_lag_days > self.max_lag_days
        ):
            raise ValueError("min_lag_days cannot exceed max_lag_days")
        if self.historical_coefficient is None and not self.estimation_metadata.is_prior:
            raise ValueError("Data-estimated edges require a historical coefficient")
        if self.historical_coefficient is not None and self.estimation_metadata.is_prior:
            raise ValueError("Prior-based edges must not present a learned coefficient")
        if self.historical_observation_count != self.estimation_metadata.sample_count:
            raise ValueError("Observation count must agree with estimation metadata")
        if self.verification_status == VerificationStatus.UNRESOLVED:
            raise ValueError("Unresolved relationships must not enter the causal graph")
        return self

    @property
    def participates_in_causal_propagation(self) -> bool:
        """Correlations are contextual evidence, never causal traversal edges."""

        return self.channel_type != ChannelType.COMMON_FACTOR

    def available_at(self, as_of: datetime, *, allow_temporal_approximation: bool = False) -> bool:
        """Whether the relationship was eligible at a simulated historical time."""

        if self.temporal_approximation and not allow_temporal_approximation:
            return False
        if self.relationship_created_at > as_of:
            return False
        if self.source_date is not None and self.source_date > as_of:
            return False
        if not self.temporal_approximation:
            return (
                self.relationship_verified_at is not None and self.relationship_verified_at <= as_of
            )
        return True


class GraphCoverageSummary(BaseModel):
    """Coverage report that identifies missing and non-causal graph evidence."""

    entities_requested: list[str]
    entities_with_edges: list[str]
    covered_entity_ratio: float = Field(ge=0.0, le=1.0)
    causal_edge_count: int = Field(ge=0)
    contextual_edge_count: int = Field(ge=0)
    approximate_edge_count: int = Field(ge=0)
    limitations: list[str] = Field(default_factory=list)
