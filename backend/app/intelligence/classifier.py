"""FinBERT-based event classifier with ontology tagging.

Classifies raw news text into EventCategory values using a
two-stage approach:
1. FinBERT sentiment analysis (positive/negative/neutral)
2. Keyword + pattern matching to map to specific ontology categories

The classifier does NOT use an LLM for classification — this is
deterministic and reproducible by design.
"""

import logging
import re
from typing import Any

from app.intelligence.ontology import EventCategory

logger = logging.getLogger(__name__)

# Category detection patterns (keyword → category mapping)
# Ordered by specificity — more specific patterns first
_CATEGORY_PATTERNS: list[tuple[list[str], EventCategory]] = [
    # Macro / Central Bank
    (["interest rate", "rate hike", "rate cut", "basis point", "bps"], EventCategory.INTEREST_RATE_CHANGE),
    (["federal reserve", "fed meeting", "fomc", "ecb", "bank of japan", "central bank"], EventCategory.MONETARY_POLICY),
    (["inflation", "cpi", "consumer price", "deflation"], EventCategory.INFLATION_DATA),
    (["unemployment", "jobs report", "nonfarm payroll", "labor market", "jobless claims"], EventCategory.EMPLOYMENT_DATA),
    (["gdp", "gross domestic product", "economic growth", "recession"], EventCategory.GDP_REPORT),

    # Geopolitical
    (["tariff", "trade war", "trade deal", "trade deficit"], EventCategory.TRADE_WAR),
    (["sanction", "embargo", "trade restriction", "export ban"], EventCategory.SANCTIONS),
    (["military", "war", "invasion", "missile", "armed conflict", "airstrike"], EventCategory.MILITARY_CONFLICT),
    (["coup", "political crisis", "government collapse", "regime change"], EventCategory.POLITICAL_INSTABILITY),
    (["election", "presidential race", "midterm", "referendum", "vote"], EventCategory.ELECTION),

    # Company / Corporate
    (["earnings beat", "revenue beat", "profit surge", "exceeded expectations"], EventCategory.EARNINGS_SURPRISE),
    (["earnings miss", "revenue miss", "profit decline", "missed expectations", "disappointing quarter"], EventCategory.EARNINGS_MISS),
    (["merger", "acquisition", "takeover", "buyout", "deal announced"], EventCategory.MERGER_ACQUISITION),
    (["ceo resign", "ceo step", "new ceo", "chief executive", "leadership change"], EventCategory.CEO_CHANGE),
    (["bankruptcy", "chapter 11", "chapter 7", "insolvent", "liquidation"], EventCategory.BANKRUPTCY),
    (["fraud", "scandal", "sec investigation", "accounting irregularity", "whistleblower"], EventCategory.FRAUD_SCANDAL),
    (["product launch", "new product", "unveil", "release", "announce"], EventCategory.PRODUCT_LAUNCH),
    (["regulatory", "regulation", "antitrust", "compliance", "fine", "penalty"], EventCategory.REGULATORY_ACTION),
    (["layoff", "job cut", "workforce reduction", "restructuring", "downsizing"], EventCategory.LAYOFFS),
    (["buyback", "share repurchase", "stock repurchase"], EventCategory.STOCK_BUYBACK),
    (["dividend", "payout", "distribution", "yield increase"], EventCategory.DIVIDEND_CHANGE),

    # Supply Chain / Industry
    (["supply chain", "shortage", "supply disruption", "factory shutdown", "port congestion"], EventCategory.SUPPLY_CHAIN_DISRUPTION),
    (["oil price", "commodity", "gold", "copper", "raw material"], EventCategory.COMMODITY_SHOCK),
    (["energy crisis", "power outage", "oil embargo", "opec"], EventCategory.ENERGY_CRISIS),
    (["chip shortage", "semiconductor", "fab shutdown", "wafer"], EventCategory.CHIP_SHORTAGE),

    # Natural / Climate
    (["earthquake", "hurricane", "tsunami", "flood", "wildfire", "volcano"], EventCategory.NATURAL_DISASTER),
    (["pandemic", "covid", "virus outbreak", "epidemic", "lockdown"], EventCategory.PANDEMIC),
    (["climate", "carbon", "emission", "green energy", "esg"], EventCategory.CLIMATE_EVENT),

    # Market Structure
    (["market crash", "black monday", "bear market", "correction"], EventCategory.MARKET_CRASH),
    (["flash crash", "circuit breaker", "trading halt"], EventCategory.FLASH_CRASH),
    (["short squeeze", "gamma squeeze", "wallstreetbets"], EventCategory.SHORT_SQUEEZE),
    (["liquidity crisis", "credit crunch", "bank run", "contagion"], EventCategory.LIQUIDITY_CRISIS),
    (["currency crisis", "devaluation", "forex", "exchange rate"], EventCategory.CURRENCY_CRISIS),

    # Tech / Innovation
    (["artificial intelligence", "ai breakthrough", "machine learning", "gpt", "llm"], EventCategory.AI_BREAKTHROUGH),
    (["cyber attack", "data breach", "hack", "ransomware", "security breach"], EventCategory.CYBERSECURITY_BREACH),
    (["tech regulation", "big tech", "antitrust tech", "platform regulation"], EventCategory.TECH_REGULATION),
]


class EventClassifier:
    """Classifies raw news text into EventCategory values.

    Uses keyword pattern matching for category detection.
    FinBERT integration for sentiment scoring is loaded lazily
    to avoid slow startup when running tests or lightweight operations.
    """

    def __init__(self, use_finbert: bool = False) -> None:
        """Initialize the classifier.

        Args:
            use_finbert: If True, loads the FinBERT model for sentiment scoring.
                        Set to False for tests or environments without GPU.
        """
        self._finbert_pipeline = None
        self._use_finbert = use_finbert

    def _load_finbert(self) -> Any:
        """Lazily load FinBERT model."""
        if self._finbert_pipeline is None and self._use_finbert:
            try:
                from transformers import pipeline
                self._finbert_pipeline = pipeline(
                    "sentiment-analysis",
                    model="ProsusAI/finbert",
                    device=-1,  # CPU by default
                )
                logger.info("FinBERT model loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load FinBERT: {e}. Using fallback scoring.")
                self._use_finbert = False
        return self._finbert_pipeline

    def classify_category(self, title: str, description: str) -> EventCategory:
        """Classify text into an EventCategory using keyword matching.

        The combined text of title + description is searched against
        the pattern list. First match wins (patterns are ordered by specificity).
        """
        text = f"{title} {description}".lower()

        for keywords, category in _CATEGORY_PATTERNS:
            for keyword in keywords:
                if keyword in text:
                    return category

        return EventCategory.OTHER

    def score_sentiment(self, text: str) -> dict[str, float]:
        """Score text sentiment using FinBERT (or fallback).

        Returns: {"positive": float, "negative": float, "neutral": float}
        """
        pipe = self._load_finbert()

        if pipe is not None:
            try:
                # FinBERT returns [{"label": "positive", "score": 0.95}, ...]
                results = pipe(text[:512])  # FinBERT has 512 token limit
                return {r["label"]: r["score"] for r in results}
            except Exception as e:
                logger.error(f"FinBERT scoring failed: {e}")

        # Fallback: simple keyword-based sentiment
        return self._fallback_sentiment(text)

    def _fallback_sentiment(self, text: str) -> dict[str, float]:
        """Simple keyword-based sentiment fallback when FinBERT unavailable."""
        text_lower = text.lower()

        positive_words = {"beat", "surge", "growth", "rally", "bullish", "strong", "gain", "profit", "upgrade"}
        negative_words = {"miss", "crash", "decline", "bearish", "weak", "loss", "downgrade", "layoff", "bankruptcy"}

        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        total = pos_count + neg_count

        if total == 0:
            return {"positive": 0.0, "negative": 0.0, "neutral": 1.0}

        pos_score = pos_count / total
        neg_score = neg_count / total

        return {
            "positive": round(pos_score, 3),
            "negative": round(neg_score, 3),
            "neutral": round(max(0, 1.0 - pos_score - neg_score), 3),
        }

    def estimate_severity(self, category: EventCategory, sentiment: dict[str, float]) -> float:
        """Estimate severity score based on category and sentiment.

        This is a heuristic: severity is driven primarily by category
        (macro/geopolitical = higher base) modulated by sentiment strength.
        """
        # Base severity by category type
        from app.intelligence.ontology import CATEGORY_SCOPE
        scope = CATEGORY_SCOPE.get(category, "single_stock")

        base_severity = {
            "market_wide": 0.7,
            "multi_sector": 0.5,
            "sector": 0.4,
            "single_stock": 0.3,
        }.get(scope, 0.3)

        # Modulate by sentiment strength (strong negative → higher severity)
        neg_score = sentiment.get("negative", 0.0)
        severity = base_severity + (neg_score * 0.3)

        return round(min(severity, 1.0), 3)
