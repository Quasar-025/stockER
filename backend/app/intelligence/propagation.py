"""Probabilistic, channel-based causal event propagation.

No relationship label in this module maps to a market direction.  Directions
come only from comparable observed residual outcomes.  In their absence, a
direction-neutral prior produces an explicitly insufficient-evidence result.
"""

from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, Field

from app.graph.historical_observations import (
    CausalRelationshipObservation,
    HistoricalEdgeCalibrator,
)
from app.graph.queries import InMemoryCausalGraph
from app.graph.schema import ChannelType
from app.intelligence.distribution import EmpiricalImpactDistribution
from app.intelligence.effect_decomposition import (
    EffectChannel,
    EffectDecomposition,
    ReliabilityCalibrator,
    ReliabilityInputs,
)
from app.intelligence.ontology import EventOntologySchema
from app.intelligence.regime import MarketRegime
from app.schemas.forecast import (
    ContradictingEvent,
    DataQualitySummary,
    EntityImpact,
    EventSummary,
    ForecastDirection,
    HistoricalEvidenceSummary,
    HistoricalSupport,
    ProbabilisticForecast,
    PropagationPath,
)

FORECAST_HORIZONS = (1, 3, 7, 14, 30, 90)


class DirectEventObservation(BaseModel):
    """Historical outcome for an entity directly affected by an event."""

    event_id: str
    event_date: datetime
    available_at: datetime
    ticker: str
    event_magnitude: float | None = Field(default=None, ge=0.0, le=1.0)
    event_duration_days: int | None = Field(default=None, ge=0)
    market_regime: MarketRegime | None = None
    target_return: float
    market_return: float = 0.0
    sector_excess_return: float = 0.0
    data_quality: float = Field(default=1.0, ge=0.0, le=1.0)
    is_seeded_demo: bool = False
    evidence_reference: str | None = None

    @property
    def residual_return(self) -> float:
        return self.target_return - self.market_return - self.sector_excess_return


class FactorEstimate(BaseModel):
    """Market or sector contribution, supplied from observed factor history."""

    expected_return: float = 0.0
    probability: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sample_count: int = Field(default=0, ge=0)
    estimation_method: str = "insufficient_data"
    is_prior: bool = True


@dataclass(frozen=True)
class PropagationContext:
    """Observed factor estimates by horizon; omitted factors remain unknown."""

    market_by_horizon: dict[int, FactorEstimate] = field(default_factory=dict)
    sector_by_horizon: dict[int, FactorEstimate] = field(default_factory=dict)
    provider_statuses: dict[str, str] = field(default_factory=dict)
    source_quality_score: float = 0.0

    def market(self, horizon: int) -> FactorEstimate:
        return self.market_by_horizon.get(horizon, FactorEstimate())

    def sector(self, horizon: int) -> FactorEstimate:
        return self.sector_by_horizon.get(horizon, FactorEstimate())


class PropagationEngine:
    """Propagate potential effects through evidence-backed causal channels."""

    def __init__(
        self,
        graph: InMemoryCausalGraph,
        edge_observations: list[CausalRelationshipObservation] | None = None,
        direct_observations: list[DirectEventObservation] | None = None,
        *,
        edge_calibrator: HistoricalEdgeCalibrator | None = None,
        reliability_calibrator: ReliabilityCalibrator | None = None,
        min_confidence: float = 0.35,
    ) -> None:
        self.graph = graph
        self.edge_observations = edge_observations or []
        self.direct_observations = direct_observations or []
        self.edge_calibrator = edge_calibrator or HistoricalEdgeCalibrator()
        self.reliability_calibrator = reliability_calibrator or ReliabilityCalibrator()
        self.min_confidence = min_confidence

    def forecast(
        self,
        event: EventOntologySchema,
        current_regime: MarketRegime,
        *,
        context: PropagationContext | None = None,
        max_depth: int = 4,
        as_of: datetime | None = None,
        include_seeded_demo: bool = False,
        allow_temporal_approximation: bool = False,
        horizons: tuple[int, ...] = FORECAST_HORIZONS,
    ) -> ProbabilisticForecast:
        """Build a multi-horizon forecast, flagging unsupported conclusions."""

        context = context or PropagationContext()
        as_of = as_of or event.event_date or event.published_at
        roots = event.affected_tickers
        direct_impacts: list[EntityImpact] = []
        secondary_impacts: list[EntityImpact] = []
        tertiary_impacts: list[EntityImpact] = []
        beneficiaries: list[EntityImpact] = []
        evidence_count = 0
        flags: list[str] = []

        for ticker in roots:
            observations = self._direct_comparable(
                ticker, event, current_regime, as_of, include_seeded_demo
            )
            for horizon in horizons:
                impact = self._impact_from_returns(
                    ticker=ticker, returns=[item.residual_return for item in observations],
                    event_ids=[item.event_id for item in observations],
                    quality=[item.data_quality for item in observations], current_regime=current_regime,
                    horizon=horizon, depth=1, context=context, paths=[], edge_confidence=1.0,
                    estimation_method="historical_direct_outcomes" if observations else "insufficient_data",
                    calibration_window=self._direct_window(observations), is_prior=not observations,
                )
                direct_impacts.append(impact)
                evidence_count += len(observations)
                if impact.insufficient_historical_evidence:
                    flags.append(f"{ticker} at {horizon}d: insufficient historical evidence")

        paths = self.graph.traverse(
            roots, max_depth=max_depth, as_of=as_of,
            allow_temporal_approximation=allow_temporal_approximation,
        )
        for edges, depth in paths:
            edge = edges[-1]
            calibration = self.edge_calibrator.estimate(
                self.edge_observations,
                source_entity=edge.source_entity, target_entity=edge.target_entity,
                event_magnitude=event.estimated_disruption_magnitude,
                event_duration_days=event.estimated_duration_days, market_regime=current_regime,
                as_of=as_of, include_seeded_demo=include_seeded_demo,
            )
            # Structural attenuation controls repeated propagation magnitude but
            # has no sign; the historical residuals determine sign/outcome.
            attenuation = edge.strength ** max(0, depth - 1)
            residuals = [value * attenuation for value in calibration.residual_returns]
            path = PropagationPath(
                entities=[edges[0].source_entity, *[item.target_entity for item in edges]],
                relationship_types=[item.relationship_type.value for item in edges],
                channel_types=[item.channel_type.value for item in edges], propagation_depth=depth,
                cumulative_lag_days=sum(item.typical_time_lag_days for item in edges),
                edge_confidence=min(item.confidence for item in edges),
                evidence_sources=[source for item in edges for source in item.evidence_sources],
                temporal_approximation=any(item.temporal_approximation for item in edges),
            )
            for horizon in horizons:
                if horizon < path.cumulative_lag_days:
                    continue
                impact = self._impact_from_returns(
                    ticker=edge.target_entity, returns=residuals,
                    event_ids=[item.observation.event_id for item in calibration.comparable_observations],
                    quality=[item.observation.data_quality for item in calibration.comparable_observations],
                    current_regime=current_regime, horizon=horizon, depth=depth, context=context,
                    paths=[path], edge_confidence=path.edge_confidence,
                    estimation_method=calibration.metadata.estimation_method.value,
                    calibration_window=calibration.metadata.estimation_window,
                    is_prior=calibration.metadata.is_prior,
                    standard_error=calibration.metadata.standard_error,
                    competitive=edge.channel_type == ChannelType.SUBSTITUTION,
                )
                evidence_count += len(calibration.comparable_observations)
                if edge.channel_type == ChannelType.SUBSTITUTION:
                    beneficiaries.append(impact)
                elif depth == 1:
                    direct_impacts.append(impact)
                elif depth == 2:
                    secondary_impacts.append(impact)
                else:
                    tertiary_impacts.append(impact)
                if impact.insufficient_historical_evidence:
                    flags.append(f"{edge.target_entity} at depth {depth}, {horizon}d: insufficient historical evidence")

        coverage = self.graph.coverage(roots)
        limitations = list(coverage.limitations)
        if not include_seeded_demo:
            limitations.append("Seeded/demo observations are excluded from empirical calibration.")
        if not context.provider_statuses:
            limitations.append("No live provider quality records were supplied to this forecast.")
        if not allow_temporal_approximation:
            limitations.append("Temporal-approximation graph edges were excluded from this forecast.")
        return ProbabilisticForecast(
            event=EventSummary(
                title=event.title, category=event.category.value, event_date=event.event_date or event.published_at,
                estimated_disruption_magnitude=event.estimated_disruption_magnitude,
                estimated_duration_days=event.estimated_duration_days, affected_tickers=roots,
            ),
            current_regime=current_regime, primary_impacts=direct_impacts,
            secondary_impacts=secondary_impacts, tertiary_impacts=tertiary_impacts,
            potential_beneficiaries=beneficiaries,
            historical_evidence=HistoricalEvidenceSummary(
                comparable_event_count=len({item.event_id for item in self.direct_observations} | {item.event_id for item in self.edge_observations}),
                observation_count=evidence_count, includes_seeded_demo_data=include_seeded_demo,
                caveat="Historical sample counts are exposed; bootstrap metadata is not empirical calibration data.",
            ),
            uncertainty_sources=sorted(set(flag.split(": ", 1)[-1] for flag in flags)),
            data_quality=DataQualitySummary(
                provider_statuses=context.provider_statuses, source_quality_score=context.source_quality_score,
                limitations=[] if context.provider_statuses else ["Provider quality metadata unavailable."],
            ),
            graph_coverage=coverage, limitations=limitations,
            insufficient_evidence_flags=sorted(set(flags)),
        )

    def _direct_comparable(
        self, ticker: str, event: EventOntologySchema, regime: MarketRegime, as_of: datetime, include_seeded_demo: bool
    ) -> list[DirectEventObservation]:
        matches: list[DirectEventObservation] = []
        for observation in self.direct_observations:
            if observation.ticker != ticker or observation.available_at > as_of:
                continue
            if observation.is_seeded_demo and not include_seeded_demo:
                continue
            magnitude = self.edge_calibrator._proximity(event.estimated_disruption_magnitude, observation.event_magnitude)
            duration = self.edge_calibrator._proximity(
                float(event.estimated_duration_days) if event.estimated_duration_days is not None else None,
                float(observation.event_duration_days) if observation.event_duration_days is not None else None,
            )
            regime_score = 1.0 if observation.market_regime == regime else 0.35
            if (magnitude + duration + regime_score) / 3 >= 0.25:
                matches.append(observation)
        return matches

    def _impact_from_returns(
        self,
        *,
        ticker: str,
        returns: list[float],
        event_ids: list[str],
        quality: list[float],
        current_regime: MarketRegime,
        horizon: int,
        depth: int,
        context: PropagationContext,
        paths: list[PropagationPath],
        edge_confidence: float,
        estimation_method: str,
        calibration_window: str | None,
        is_prior: bool,
        standard_error: float | None = None,
        competitive: bool = False,
    ) -> EntityImpact:
        evidence = EmpiricalImpactDistribution.from_returns(returns)
        market = context.market(horizon)
        sector = context.sector(horizon)
        adjusted_returns = [value + market.expected_return + sector.expected_return for value in returns]
        net = EmpiricalImpactDistribution.from_returns(adjusted_returns)
        if not returns:
            # No residual evidence: common-factor estimates are still separated,
            # but cannot turn an unknown causal channel into certainty.
            net = EmpiricalImpactDistribution.from_returns([])
        uncertainty = min(1.0, (standard_error or evidence.standard_error or 0.05) / 0.05)
        reliability = self.reliability_calibrator.estimate(ReliabilityInputs(
            sample_count=evidence.sample_count, consistency=evidence.historical_consistency,
            similarity_quality=0.5 if is_prior else 0.75,
            data_quality=sum(quality) / len(quality) if quality else 0.0,
            edge_confidence=edge_confidence, model_uncertainty=uncertainty,
        ))
        direction, direction_probability = self._direction(net, evidence.sample_count, is_prior)
        insufficient = (
            is_prior or evidence.sample_count <= 5 or not reliability.is_calibrated
            or reliability.value < self.min_confidence
        )
        direct_channel = self._channel(
            "competitive/substitution" if competitive else "direct event",
            evidence.mean_return, direction_probability, reliability.value, evidence.sample_count,
            estimation_method, is_prior,
        )
        zero_channel = self._channel(
            "direct event" if competitive else "competitive/substitution", 0.0, 0.5, 0.0, 0,
            "not_applicable", True,
        )
        direct = zero_channel if competitive else direct_channel
        competition = direct_channel if competitive else zero_channel
        market_channel = EffectChannel(
            channel_name="market", estimated_effect=market.expected_return, probability=market.probability,
            confidence=market.confidence, sample_count=market.sample_count,
            estimation_method=market.estimation_method, evidence_summary="Observed market factor estimate." if not market.is_prior else "Market factor unavailable.",
            is_prior=market.is_prior,
        )
        sector_channel = EffectChannel(
            channel_name="sector", estimated_effect=sector.expected_return, probability=sector.probability,
            confidence=sector.confidence, sample_count=sector.sample_count,
            estimation_method=sector.estimation_method, evidence_summary="Observed sector excess-return estimate." if not sector.is_prior else "Sector factor unavailable.",
            is_prior=sector.is_prior,
        )
        residual_channel = EffectChannel(
            channel_name="residual/other", estimated_effect=0.0, probability=0.5, confidence=0.0,
            sample_count=0, estimation_method="not_identified", evidence_summary="Residual channel is not assumed away.", is_prior=True,
        )
        decomposition = EffectDecomposition.combine(
            direct_event_effect=direct, sector_effect=sector_channel, market_effect=market_channel,
            competitive_substitution_effect=competition, residual_effect=residual_channel,
            net_direction_probability=direction_probability, model_confidence=reliability.value,
        )
        contradicting = [
            ContradictingEvent(event_id=event_id, observed_return=value, reason="Observed residual had the opposite sign.")
            for event_id, value in zip(event_ids, returns, strict=False)
            if evidence.mean_return and value * evidence.mean_return < 0
        ]
        flags: list[str] = []
        if evidence.sample_count <= 5:
            flags.append("Five or fewer comparable observations.")
        if is_prior:
            flags.append("Direction-neutral prior used; no learned coefficient.")
        if not reliability.is_calibrated:
            flags.append(reliability.reason)
        return EntityImpact(
            ticker=ticker, direction=ForecastDirection.UNCERTAIN if insufficient else direction,
            direction_probability=direction_probability, model_confidence=reliability.value,
            confidence_is_calibrated=reliability.is_calibrated,
            expected_return=decomposition.net_expected_return,
            return_range=(net.quantiles.p25, net.quantiles.p75), return_p50=net.quantiles.p50,
            time_horizon_days=horizon, propagation_depth=depth, effect_decomposition=decomposition,
            causal_paths=paths,
            historical_support=HistoricalSupport(
                sample_count=evidence.sample_count, supporting_event_ids=event_ids,
                estimation_method=estimation_method, is_prior=is_prior, calibration_window=calibration_window,
                standard_error=standard_error or evidence.standard_error,
            ),
            contradicting_evidence=contradicting, insufficient_historical_evidence=insufficient,
            uncertainty_sources=flags,
        )

    @staticmethod
    def _channel(
        name: str, effect: float, probability: float, confidence: float, sample_count: int,
        method: str, is_prior: bool,
    ) -> EffectChannel:
        return EffectChannel(
            channel_name=name, estimated_effect=effect, probability=probability, confidence=confidence,
            sample_count=sample_count, estimation_method=method,
            evidence_summary=("Direction-neutral cold-start prior." if is_prior else f"Estimated from {sample_count} comparable observations."),
            is_prior=is_prior,
        )

    @staticmethod
    def _direction(
        distribution: EmpiricalImpactDistribution, sample_count: int, is_prior: bool
    ) -> tuple[ForecastDirection, float]:
        if is_prior or sample_count == 0:
            return ForecastDirection.UNCERTAIN, max(distribution.probability_positive, distribution.probability_negative)
        options = {
            ForecastDirection.BULLISH: distribution.probability_positive,
            ForecastDirection.BEARISH: distribution.probability_negative,
            ForecastDirection.NEUTRAL: distribution.probability_neutral,
        }
        return max(options.items(), key=lambda item: item[1])

    @staticmethod
    def _direct_window(observations: list[DirectEventObservation]) -> str | None:
        if not observations:
            return None
        dates = sorted(item.event_date.date().isoformat() for item in observations)
        return f"{dates[0]} to {dates[-1]}"
