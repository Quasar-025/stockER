"""Hidden Markov Model market regime detector.

Identifies the current market regime (bull, bear, high-volatility,
recession, etc.) using an HMM trained on market returns and volatility.
This ensures the similarity engine doesn't compare 2008 events to 2024
bull market conditions.

For the MVP, we use a simple returns-based detector that classifies
into 4 regimes without requiring a trained HMM model. The full HMM
will be added when we have sufficient historical data in the database.
"""

import logging
from dataclasses import dataclass
from enum import StrEnum

import numpy as np

logger = logging.getLogger(__name__)


class MarketRegime(StrEnum):
    """Market regime classifications."""

    BULL_LOW_VOL = "BULL_LOW_VOL"  # Rising markets, calm
    BULL_HIGH_VOL = "BULL_HIGH_VOL"  # Rising markets, choppy
    BEAR_LOW_VOL = "BEAR_LOW_VOL"  # Falling markets, orderly
    BEAR_HIGH_VOL = "BEAR_HIGH_VOL"  # Falling markets, panic
    SIDEWAYS = "SIDEWAYS"  # Range-bound
    CRISIS = "CRISIS"  # Extreme drawdown / crash


@dataclass
class RegimeDetectionResult:
    """Output of the regime detector."""

    regime: MarketRegime
    confidence: float  # 0-1 confidence in the classification
    avg_return: float  # Average return in the lookback window
    volatility: float  # Annualized volatility
    description: str  # Human-readable regime description


class MarketRegimeDetector:
    """Detects current market regime from price returns.

    MVP Implementation:
    - Uses rolling returns and volatility thresholds
    - Classifies into 6 regimes

    Future (post-MVP):
    - Train an HMM with hmmlearn on historical data
    - Use multiple features (returns, volume, breadth, VIX)
    """

    def __init__(
        self,
        return_threshold: float = 0.0,
        volatility_threshold: float = 0.20,
        crisis_drawdown: float = -0.20,
        sideways_range: float = 0.02,
    ) -> None:
        """Initialize with classification thresholds.

        Args:
            return_threshold: Annualized return threshold for bull/bear.
            volatility_threshold: Annualized vol threshold for high/low vol.
            crisis_drawdown: Cumulative return threshold for crisis mode.
            sideways_range: Return range for sideways classification.
        """
        self.return_threshold = return_threshold
        self.volatility_threshold = volatility_threshold
        self.crisis_drawdown = crisis_drawdown
        self.sideways_range = sideways_range

    def detect(self, daily_returns: list[float], lookback_days: int = 60) -> RegimeDetectionResult:
        """Detect the current market regime from daily returns.

        Args:
            daily_returns: List of daily log returns (most recent last).
            lookback_days: Number of recent days to analyze.

        Returns:
            RegimeDetectionResult with the detected regime.
        """
        if len(daily_returns) < 5:
            return RegimeDetectionResult(
                regime=MarketRegime.SIDEWAYS,
                confidence=0.0,
                avg_return=0.0,
                volatility=0.0,
                description="Insufficient data for regime detection",
            )

        # Use the most recent N days
        recent = np.array(daily_returns[-lookback_days:])

        # Calculate metrics
        avg_daily_return = float(np.mean(recent))
        daily_vol = float(np.std(recent))

        # Annualize
        annualized_return = avg_daily_return * 252
        annualized_vol = daily_vol * np.sqrt(252)
        cumulative_return = float(np.sum(recent))

        # Classify
        regime, confidence, description = self._classify(
            annualized_return, annualized_vol, cumulative_return
        )

        return RegimeDetectionResult(
            regime=regime,
            confidence=confidence,
            avg_return=round(annualized_return, 4),
            volatility=round(annualized_vol, 4),
            description=description,
        )

    def _classify(
        self,
        annualized_return: float,
        annualized_vol: float,
        cumulative_return: float,
    ) -> tuple[MarketRegime, float, str]:
        """Classify based on thresholds."""
        # Crisis takes priority
        if cumulative_return <= self.crisis_drawdown:
            return (
                MarketRegime.CRISIS,
                0.9,
                f"Crisis: cumulative drawdown of {cumulative_return:.1%}",
            )

        # Sideways
        if abs(annualized_return) <= self.sideways_range:
            return (
                MarketRegime.SIDEWAYS,
                0.6,
                f"Sideways: near-zero return ({annualized_return:.1%} annualized)",
            )

        is_bull = annualized_return > self.return_threshold
        is_high_vol = annualized_vol > self.volatility_threshold

        if is_bull and not is_high_vol:
            return (
                MarketRegime.BULL_LOW_VOL,
                0.8,
                f"Bull market with low volatility ({annualized_vol:.1%})",
            )
        elif is_bull and is_high_vol:
            return (
                MarketRegime.BULL_HIGH_VOL,
                0.7,
                f"Bull market with elevated volatility ({annualized_vol:.1%})",
            )
        elif not is_bull and not is_high_vol:
            return (
                MarketRegime.BEAR_LOW_VOL,
                0.7,
                f"Bear market, orderly decline ({annualized_vol:.1%})",
            )
        else:
            return (
                MarketRegime.BEAR_HIGH_VOL,
                0.85,
                f"Bear market with high volatility ({annualized_vol:.1%})",
            )
