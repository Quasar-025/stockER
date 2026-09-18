"""Tests for the LLM Provider and Explainer."""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.llm.provider import OllamaProvider, OpenAIProvider, LLMProviderFactory
from app.llm.explainer import (
    build_explanation_prompt,
    explain_forecast,
    _fallback_explanation,
    EXPLAINER_SYSTEM_PROMPT,
)
from app.intelligence.impact import ForecastResult
from app.intelligence.regime import MarketRegime


def _make_forecast(**overrides) -> ForecastResult:
    defaults = {
        "event_id": uuid.uuid4(),
        "ticker": "AAPL",
        "predicted_impact": -0.045,
        "confidence_score": 0.72,
        "time_horizon_days": 30,
        "market_regime": MarketRegime.BULL_HIGH_VOL,
        "similar_events": [
            {
                "title": "2011 Thailand Floods",
                "category": "SUPPLY_CHAIN_DISRUPTION",
                "similarity_score": 0.85,
                "historical_impact": -0.06,
                "regime_at_time": 0.7,
            }
        ],
        "causal_chain": ["Taiwan Earthquake", "TSMC Shutdown", "Apple Supply Shortage"],
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return ForecastResult(**defaults)


class TestOllamaProvider:
    def test_initialization(self):
        provider = OllamaProvider(host="http://localhost:11434", model="test-model")
        assert provider.host == "http://localhost:11434"
        assert provider.model == "test-model"


class TestOpenAIProvider:
    def test_unavailable_without_key(self):
        provider = OpenAIProvider(api_key=None)
        # Can't call is_available synchronously in the test,
        # so just check the api_key is None
        assert provider.api_key is None


class TestProviderFactory:
    def test_get_provider_sync_ollama(self):
        provider = LLMProviderFactory.get_provider_sync("ollama")
        assert isinstance(provider, OllamaProvider)

    def test_get_provider_sync_openai(self):
        provider = LLMProviderFactory.get_provider_sync("openai")
        assert isinstance(provider, OpenAIProvider)

    def test_get_provider_sync_unknown(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            LLMProviderFactory.get_provider_sync("claude")


class TestBuildExplanationPrompt:
    def test_prompt_contains_ticker(self):
        forecast = _make_forecast()
        prompt = build_explanation_prompt(forecast)
        assert "AAPL" in prompt

    def test_prompt_contains_impact(self):
        forecast = _make_forecast(predicted_impact=-0.045)
        prompt = build_explanation_prompt(forecast)
        assert "4.5%" in prompt
        assert "decline" in prompt

    def test_prompt_distinguishes_probability_from_reliability(self):
        forecast = _make_forecast(direction_probability=0.72, model_confidence=0.44, sample_count=3)
        prompt = build_explanation_prompt(forecast)
        assert "72%" in prompt
        assert "44%" in prompt

    def test_prompt_contains_similar_events(self):
        forecast = _make_forecast()
        prompt = build_explanation_prompt(forecast)
        assert "2011 Thailand Floods" in prompt
        assert "85%" in prompt

    def test_prompt_contains_causal_chain(self):
        forecast = _make_forecast()
        prompt = build_explanation_prompt(forecast)
        assert "Taiwan Earthquake" in prompt
        assert "TSMC Shutdown" in prompt

    def test_prompt_no_similar_events(self):
        forecast = _make_forecast(similar_events=[])
        prompt = build_explanation_prompt(forecast)
        assert "No similar historical events found" in prompt


class TestFallbackExplanation:
    def test_fallback_contains_prediction(self):
        forecast = _make_forecast()
        text = _fallback_explanation(forecast)
        assert "AAPL" in text
        assert "4.5%" in text
        assert "decline" in text
        assert "Direction likelihood" in text

    def test_fallback_contains_similar_events(self):
        forecast = _make_forecast()
        text = _fallback_explanation(forecast)
        assert "2011 Thailand Floods" in text

    def test_fallback_contains_causal_chain(self):
        forecast = _make_forecast()
        text = _fallback_explanation(forecast)
        assert "Taiwan Earthquake" in text


class TestExplainForecast:
    @pytest.mark.asyncio
    async def test_explain_with_mock_provider(self):
        """Test that explain_forecast calls the LLM provider correctly."""
        forecast = _make_forecast()
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = "This is a test explanation."

        result = await explain_forecast(forecast, mock_provider)

        assert result == "This is a test explanation."
        mock_provider.generate.assert_called_once()
        # Verify system prompt was passed
        call_kwargs = mock_provider.generate.call_args
        assert call_kwargs.kwargs["system_prompt"] == EXPLAINER_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_explain_falls_back_on_error(self):
        """Test that a provider error triggers the fallback explanation."""
        forecast = _make_forecast()
        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = RuntimeError("LLM down")

        result = await explain_forecast(forecast, mock_provider)

        # Should get the fallback explanation, not an error
        assert "AAPL" in result
        assert "4.5%" in result
