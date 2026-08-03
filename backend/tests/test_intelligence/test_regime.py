"""Tests for the Market Regime Detector."""

import pytest
import numpy as np

from app.intelligence.regime import MarketRegimeDetector, MarketRegime


class TestMarketRegimeDetector:
    """Tests for the regime detection engine."""

    def setup_method(self):
        self.detector = MarketRegimeDetector()

    def test_insufficient_data(self):
        """Should return SIDEWAYS with 0 confidence for < 5 data points."""
        result = self.detector.detect([0.01, 0.02, -0.01])
        assert result.regime == MarketRegime.SIDEWAYS
        assert result.confidence == 0.0
        assert "Insufficient" in result.description

    def test_bull_low_vol(self):
        """Steady positive returns with low volatility → BULL_LOW_VOL."""
        # Generate 60 days of small positive returns (low vol)
        np.random.seed(42)
        returns = list(np.random.normal(0.001, 0.005, 60))  # ~25% annualized, ~8% vol
        result = self.detector.detect(returns)
        assert result.regime == MarketRegime.BULL_LOW_VOL
        assert result.avg_return > 0

    def test_bear_high_vol(self):
        """Large negative returns with high volatility → BEAR_HIGH_VOL."""
        np.random.seed(42)
        returns = list(np.random.normal(-0.005, 0.03, 60))  # Negative with high vol
        result = self.detector.detect(returns)
        assert result.regime in {MarketRegime.BEAR_HIGH_VOL, MarketRegime.CRISIS}

    def test_crisis_detection(self):
        """Extreme cumulative drawdown → CRISIS."""
        # 30 days of -1% each = -30% drawdown
        returns = [-0.01] * 30
        result = self.detector.detect(returns)
        assert result.regime == MarketRegime.CRISIS
        assert result.confidence >= 0.8

    def test_sideways_market(self):
        """Near-zero returns → SIDEWAYS."""
        # Returns that average very close to zero
        returns = [0.001, -0.001, 0.0005, -0.0005, 0.001, -0.001] * 10
        result = self.detector.detect(returns)
        assert result.regime == MarketRegime.SIDEWAYS

    def test_lookback_window(self):
        """Test that lookback_days parameter works correctly."""
        # First 100 days bearish, last 20 days bullish
        bear_returns = [-0.005] * 100
        bull_returns = [0.003] * 20
        all_returns = bear_returns + bull_returns

        # With short lookback, should see bull
        result_short = self.detector.detect(all_returns, lookback_days=20)
        assert result_short.avg_return > 0

        # With long lookback, should see bear/crisis
        result_long = self.detector.detect(all_returns, lookback_days=100)
        assert result_long.avg_return < 0

    def test_result_fields_populated(self):
        """Test that all result fields are populated."""
        returns = list(np.random.normal(0.001, 0.01, 60))
        result = self.detector.detect(returns)

        assert isinstance(result.regime, MarketRegime)
        assert 0 <= result.confidence <= 1
        assert isinstance(result.avg_return, float)
        assert isinstance(result.volatility, float)
        assert len(result.description) > 0
