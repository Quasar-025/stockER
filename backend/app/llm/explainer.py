"""LLM Explainer — translates ForecastResult into natural language.

This is the ONLY place the LLM is used in the intelligence pipeline.
It receives a fully computed ForecastResult (from the statistical
engines) and produces a human-readable explanation with citations.
"""

import logging

from app.intelligence.impact import ForecastResult
from app.llm.provider import LLMProvider
from app.schemas.forecast import ProbabilisticForecast

logger = logging.getLogger(__name__)

# System prompt for the explainer
EXPLAINER_SYSTEM_PROMPT = """You are a financial research analyst at a quantitative hedge fund.
Your job is to explain statistically estimated market scenarios in clear, evidence-based language.

CRITICAL RULES:
1. You are EXPLAINING an estimate already computed by statistical models. You are NOT making one yourself.
2. Never say the system "predicts" or guarantees an outcome. Use "estimates", "suggests", or "indicates".
3. Every numerical claim must cite supplied historical events or edge sources. Do not add facts or sources.
4. Always distinguish outcome probability from model confidence/reliability.
5. State sample count, contradictory evidence, priors, calibration status, and insufficient evidence plainly.
6. Explain direct, sector, market, competitive/substitution, and residual channels separately.
7. Use professional but accessible language."""


def build_explanation_prompt(forecast: ForecastResult | ProbabilisticForecast) -> str:
    """Build the LLM prompt from a ForecastResult.

    The prompt contains ALL the structured data the LLM needs to
    explain the prediction. The LLM adds no new data — it only
    translates numbers into narrative.
    """
    if isinstance(forecast, ProbabilisticForecast):
        return _build_probabilistic_prompt(forecast)

    impact_direction = "decline" if forecast.predicted_impact < 0 else "increase"
    impact_pct = abs(forecast.predicted_impact * 100)

    similar_events_text = ""
    for i, event in enumerate(forecast.similar_events, 1):
        similar_events_text += (
            f"\n  {i}. \"{event['title']}\" "
            f"(Category: {event['category']}, "
            f"Similarity: {event['similarity_score']:.0%}, "
            f"Historical Impact: {event['historical_impact']:+.1%})"
        )

    causal_chain_text = " → ".join(forecast.causal_chain) if forecast.causal_chain else "No causal chain available"

    return f"""Explain the following market impact prediction to an investor.

## Prediction Summary
- **Ticker**: {forecast.ticker}
- **Estimated Impact**: {impact_pct:.1f}% {impact_direction}
- **Direction likelihood**: {forecast.direction_probability:.0%}
- **Model reliability**: {forecast.model_confidence or forecast.confidence_score:.0%}
- **Comparable sample count**: {forecast.sample_count}
- **Time Horizon**: {forecast.time_horizon_days} days
- **Current Market Regime**: {forecast.market_regime.value}

## Historical Precedents (from statistical similarity engine)
{similar_events_text if similar_events_text else "  No similar historical events found."}

## Causal Chain
{causal_chain_text}

Please provide:
1. A concise 2-3 sentence summary of the estimate
2. Why these historical events are relevant
3. Key risks and limitations of this prediction
4. What to watch for in the coming days
5. An explicit sentence if historical evidence is insufficient"""


def _build_probabilistic_prompt(forecast: ProbabilisticForecast) -> str:
    """Build a prompt bounded by the v2 forecast's supplied evidence."""

    impacts = [
        *forecast.primary_impacts,
        *forecast.secondary_impacts,
        *forecast.tertiary_impacts,
        *forecast.potential_beneficiaries,
    ]
    impact_lines: list[str] = []
    for impact in impacts:
        decomposition = impact.effect_decomposition
        sources = sorted({source for path in impact.causal_paths for source in path.evidence_sources})
        impact_lines.append(
            f"- {impact.ticker} (depth {impact.propagation_depth}, {impact.time_horizon_days}d): "
            f"direction={impact.direction.value}; direction likelihood={impact.direction_probability:.0%}; "
            f"model reliability={impact.model_confidence:.0%}; sample={impact.historical_support.sample_count}; "
            f"range=[{impact.return_range[0]:+.2%}, {impact.return_range[1]:+.2%}]; "
            f"direct={decomposition.direct_event_effect.estimated_effect:+.2%}; "
            f"sector={decomposition.sector_effect.estimated_effect:+.2%}; "
            f"market={decomposition.market_effect.estimated_effect:+.2%}; "
            f"competitive={decomposition.competitive_substitution_effect.estimated_effect:+.2%}; "
            f"residual={decomposition.residual_effect.estimated_effect:+.2%}; "
            f"prior={impact.historical_support.is_prior}; calibrated={impact.confidence_is_calibrated}; "
            f"sources={sources or ['none supplied']}"
        )
    return f"""Explain the following evidence-scoped causal event forecast.

## Event
- Event: {forecast.event.title}
- Category: {forecast.event.category}
- Magnitude: {forecast.event.estimated_disruption_magnitude}
- Duration: {forecast.event.estimated_duration_days} days
- Regime: {forecast.current_regime.value}

## Entity estimates
{chr(10).join(impact_lines) if impact_lines else "No entity estimate met the evidence threshold."}

## Evidence and coverage
- Comparable canonical events: {forecast.historical_evidence.comparable_event_count}
- Observations used: {forecast.historical_evidence.observation_count}
- Graph causal edges: {forecast.graph_coverage.causal_edge_count}
- Context-only edges: {forecast.graph_coverage.contextual_edge_count}
- Graph limitations: {forecast.graph_coverage.limitations}
- Insufficient-evidence flags: {forecast.insufficient_evidence_flags}
- General limitations: {forecast.limitations}

Write a cautious explanation. Clearly state that probability and model reliability are different,
describe each effect channel, identify potential beneficiaries as conditional rather than guaranteed,
and state where the result has insufficient historical evidence. Do not introduce numerical claims
without a supplied source or sample."""


async def explain_forecast(forecast: ForecastResult | ProbabilisticForecast, provider: LLMProvider) -> str:
    """Generate a natural language explanation of a forecast.

    Args:
        forecast: The computed ForecastResult from the impact engine.
        provider: The LLM provider to use for generation.

    Returns:
        A natural language explanation string.
    """
    prompt = build_explanation_prompt(forecast)

    try:
        explanation = await provider.generate(
            prompt=prompt,
            system_prompt=EXPLAINER_SYSTEM_PROMPT,
        )
        return explanation
    except Exception as e:
        logger.error(f"Failed to generate explanation: {e}")
        # Return a structured fallback (no LLM needed)
        return _fallback_explanation(forecast)


def _fallback_explanation(forecast: ForecastResult | ProbabilisticForecast) -> str:
    """Generate a structured explanation without an LLM."""
    if isinstance(forecast, ProbabilisticForecast):
        return _probabilistic_fallback(forecast)

    direction = "decline" if forecast.predicted_impact < 0 else "increase"
    pct = abs(forecast.predicted_impact * 100)

    lines = [
        f"**{forecast.ticker}**: Estimated {pct:.1f}% {direction} "
        f"over the next {forecast.time_horizon_days} days.",
        f"Direction likelihood: {forecast.direction_probability:.0%}; model reliability: {(forecast.model_confidence or forecast.confidence_score):.0%}.",
        f"Comparable sample count: {forecast.sample_count}.",
        f"Market Regime: {forecast.market_regime.value}.",
    ]

    if forecast.similar_events:
        lines.append(f"\nBased on {len(forecast.similar_events)} historically similar events:")
        for event in forecast.similar_events[:3]:
            lines.append(f"  - {event['title']} ({event['historical_impact']:+.1%})")

    if forecast.causal_chain:
        lines.append(f"\nCausal chain: {' → '.join(forecast.causal_chain)}")

    return "\n".join(lines)


def _probabilistic_fallback(forecast: ProbabilisticForecast) -> str:
    """Deterministic v2 fallback that cannot overstate available evidence."""

    impacts = [*forecast.primary_impacts, *forecast.secondary_impacts, *forecast.tertiary_impacts]
    lines = [
        f"**{forecast.event.title}**: a probabilistic, evidence-scoped estimate in {forecast.current_regime.value}.",
        f"Comparable events: {forecast.historical_evidence.comparable_event_count}; observations used: {forecast.historical_evidence.observation_count}.",
    ]
    for impact in impacts[:5]:
        decomposition = impact.effect_decomposition
        lines.append(
            f"- **{impact.ticker}** ({impact.time_horizon_days}d, depth {impact.propagation_depth}): "
            f"{impact.direction.value} likelihood {impact.direction_probability:.0%}; "
            f"model reliability {impact.model_confidence:.0%}; direct {decomposition.direct_event_effect.estimated_effect:+.2%}, "
            f"sector {decomposition.sector_effect.estimated_effect:+.2%}, market {decomposition.market_effect.estimated_effect:+.2%}, "
            f"competitive {decomposition.competitive_substitution_effect.estimated_effect:+.2%}."
        )
        if impact.insufficient_historical_evidence:
            lines.append("  Insufficient historical evidence for a reliable directional estimate.")
    if forecast.potential_beneficiaries:
        lines.append("Potential beneficiaries are conditional substitution channels, not guaranteed gains.")
    lines.extend(f"Limitation: {item}" for item in forecast.limitations)
    return "\n".join(lines)
