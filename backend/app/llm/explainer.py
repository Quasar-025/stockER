"""LLM Explainer — translates ForecastResult into natural language.

This is the ONLY place the LLM is used in the intelligence pipeline.
It receives a fully computed ForecastResult (from the statistical
engines) and produces a human-readable explanation with citations.
"""

import logging

from app.intelligence.impact import ForecastResult
from app.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

# System prompt for the explainer
EXPLAINER_SYSTEM_PROMPT = """You are a financial research analyst at a quantitative hedge fund.
Your job is to explain market predictions to investors in clear, evidence-based language.

CRITICAL RULES:
1. You are EXPLAINING a prediction that was already computed by statistical models.
   You are NOT making the prediction yourself.
2. Every claim must reference the historical events that support it.
3. State confidence levels clearly and honestly.
4. If confidence is low, say so explicitly.
5. Use professional but accessible language.
6. Structure your response with clear sections.
7. Never hallucinate data — only reference what's in the provided context."""


def build_explanation_prompt(forecast: ForecastResult) -> str:
    """Build the LLM prompt from a ForecastResult.

    The prompt contains ALL the structured data the LLM needs to
    explain the prediction. The LLM adds no new data — it only
    translates numbers into narrative.
    """
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
- **Predicted Impact**: {impact_pct:.1f}% {impact_direction}
- **Confidence**: {forecast.confidence_score:.0%}
- **Time Horizon**: {forecast.time_horizon_days} days
- **Current Market Regime**: {forecast.market_regime.value}

## Historical Precedents (from statistical similarity engine)
{similar_events_text if similar_events_text else "  No similar historical events found."}

## Causal Chain
{causal_chain_text}

Please provide:
1. A concise 2-3 sentence summary of the prediction
2. Why these historical events are relevant
3. Key risks and limitations of this prediction
4. What to watch for in the coming days"""


async def explain_forecast(forecast: ForecastResult, provider: LLMProvider) -> str:
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


def _fallback_explanation(forecast: ForecastResult) -> str:
    """Generate a structured explanation without an LLM."""
    direction = "decline" if forecast.predicted_impact < 0 else "increase"
    pct = abs(forecast.predicted_impact * 100)

    lines = [
        f"**{forecast.ticker}**: Predicted {pct:.1f}% {direction} "
        f"over the next {forecast.time_horizon_days} days.",
        f"Confidence: {forecast.confidence_score:.0%}.",
        f"Market Regime: {forecast.market_regime.value}.",
    ]

    if forecast.similar_events:
        lines.append(f"\nBased on {len(forecast.similar_events)} historically similar events:")
        for event in forecast.similar_events[:3]:
            lines.append(f"  - {event['title']} ({event['historical_impact']:+.1%})")

    if forecast.causal_chain:
        lines.append(f"\nCausal chain: {' → '.join(forecast.causal_chain)}")

    return "\n".join(lines)
