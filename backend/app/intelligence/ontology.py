"""Event Ontology — The structured vocabulary of market events.

This module defines the category taxonomy, severity levels, and
Pydantic schemas used to classify raw news into structured EventObjects.
The LLM/FinBERT classifies into these categories; the similarity engine
uses them for dimension weighting.
"""

from enum import StrEnum
from datetime import datetime
from pydantic import BaseModel, Field


class EventCategory(StrEnum):
    """Structured event categories for the ontology.

    Each raw news article is classified into exactly one category.
    Categories are designed to be semantically distinct so the similarity
    engine can weight sector/geo dimensions appropriately.
    """

    # === Macro / Central Bank ===
    INTEREST_RATE_CHANGE = "INTEREST_RATE_CHANGE"
    MONETARY_POLICY = "MONETARY_POLICY"
    INFLATION_DATA = "INFLATION_DATA"
    EMPLOYMENT_DATA = "EMPLOYMENT_DATA"
    GDP_REPORT = "GDP_REPORT"

    # === Geopolitical ===
    TRADE_WAR = "TRADE_WAR"
    SANCTIONS = "SANCTIONS"
    MILITARY_CONFLICT = "MILITARY_CONFLICT"
    POLITICAL_INSTABILITY = "POLITICAL_INSTABILITY"
    ELECTION = "ELECTION"

    # === Company / Corporate ===
    EARNINGS_SURPRISE = "EARNINGS_SURPRISE"
    EARNINGS_MISS = "EARNINGS_MISS"
    MERGER_ACQUISITION = "MERGER_ACQUISITION"
    CEO_CHANGE = "CEO_CHANGE"
    BANKRUPTCY = "BANKRUPTCY"
    FRAUD_SCANDAL = "FRAUD_SCANDAL"
    PRODUCT_LAUNCH = "PRODUCT_LAUNCH"
    REGULATORY_ACTION = "REGULATORY_ACTION"
    LAYOFFS = "LAYOFFS"
    STOCK_BUYBACK = "STOCK_BUYBACK"
    DIVIDEND_CHANGE = "DIVIDEND_CHANGE"

    # === Supply Chain / Industry ===
    SUPPLY_CHAIN_DISRUPTION = "SUPPLY_CHAIN_DISRUPTION"
    COMMODITY_SHOCK = "COMMODITY_SHOCK"
    ENERGY_CRISIS = "ENERGY_CRISIS"
    CHIP_SHORTAGE = "CHIP_SHORTAGE"

    # === Natural / Climate ===
    NATURAL_DISASTER = "NATURAL_DISASTER"
    PANDEMIC = "PANDEMIC"
    CLIMATE_EVENT = "CLIMATE_EVENT"

    # === Market Structure ===
    MARKET_CRASH = "MARKET_CRASH"
    FLASH_CRASH = "FLASH_CRASH"
    SHORT_SQUEEZE = "SHORT_SQUEEZE"
    LIQUIDITY_CRISIS = "LIQUIDITY_CRISIS"
    CURRENCY_CRISIS = "CURRENCY_CRISIS"

    # === Tech / Innovation ===
    AI_BREAKTHROUGH = "AI_BREAKTHROUGH"
    CYBERSECURITY_BREACH = "CYBERSECURITY_BREACH"
    TECH_REGULATION = "TECH_REGULATION"

    # === Catch-all ===
    OTHER = "OTHER"


class SeverityLevel(StrEnum):
    """Discrete severity levels mapped to score ranges."""

    LOW = "LOW"              # 0.0 - 0.3: Minor, minimal market impact expected
    MEDIUM = "MEDIUM"        # 0.3 - 0.6: Moderate, sector-level impact
    HIGH = "HIGH"            # 0.6 - 0.8: Significant, multi-sector impact
    CRITICAL = "CRITICAL"    # 0.8 - 1.0: Extreme, market-wide impact

    @classmethod
    def from_score(cls, score: float) -> "SeverityLevel":
        """Convert a float severity score to a discrete level."""
        if score >= 0.8:
            return cls.CRITICAL
        elif score >= 0.6:
            return cls.HIGH
        elif score >= 0.3:
            return cls.MEDIUM
        return cls.LOW


class EventOntologySchema(BaseModel):
    """Pydantic schema for a classified event.

    This is the output of the event classification pipeline. Every
    raw news article/filing is transformed into this structured format
    before it enters the similarity engine.
    """

    title: str = Field(..., description="Concise event title")
    description: str = Field(..., description="Full event description")
    source_url: str = Field(..., description="Original source URL")
    published_at: datetime = Field(..., description="Publication timestamp")

    # Classification
    category: EventCategory = Field(..., description="Event category from ontology")
    severity_score: float = Field(..., ge=0.0, le=1.0, description="Severity 0-1")

    # Affected entities (extracted by NER)
    affected_tickers: list[str] = Field(default_factory=list)
    affected_sectors: list[str] = Field(default_factory=list)
    affected_countries: list[str] = Field(default_factory=list)

    # Supply chain propagation hints
    supply_chain_impact: list[str] = Field(
        default_factory=list,
        description="List of downstream entities affected via supply chain"
    )

    @property
    def severity_level(self) -> SeverityLevel:
        """Get the discrete severity level."""
        return SeverityLevel.from_score(self.severity_score)

    @property
    def is_macro(self) -> bool:
        """Check if this is a macroeconomic event."""
        macro_categories = {
            EventCategory.INTEREST_RATE_CHANGE,
            EventCategory.MONETARY_POLICY,
            EventCategory.INFLATION_DATA,
            EventCategory.EMPLOYMENT_DATA,
            EventCategory.GDP_REPORT,
        }
        return self.category in macro_categories

    @property
    def is_geopolitical(self) -> bool:
        """Check if this is a geopolitical event."""
        geo_categories = {
            EventCategory.TRADE_WAR,
            EventCategory.SANCTIONS,
            EventCategory.MILITARY_CONFLICT,
            EventCategory.POLITICAL_INSTABILITY,
            EventCategory.ELECTION,
        }
        return self.category in geo_categories


# Category → typical affected scope (used for default similarity weighting)
CATEGORY_SCOPE: dict[EventCategory, str] = {
    EventCategory.INTEREST_RATE_CHANGE: "market_wide",
    EventCategory.MONETARY_POLICY: "market_wide",
    EventCategory.INFLATION_DATA: "market_wide",
    EventCategory.EMPLOYMENT_DATA: "market_wide",
    EventCategory.GDP_REPORT: "market_wide",
    EventCategory.TRADE_WAR: "multi_sector",
    EventCategory.SANCTIONS: "multi_sector",
    EventCategory.MILITARY_CONFLICT: "multi_sector",
    EventCategory.EARNINGS_SURPRISE: "single_stock",
    EventCategory.EARNINGS_MISS: "single_stock",
    EventCategory.MERGER_ACQUISITION: "single_stock",
    EventCategory.CEO_CHANGE: "single_stock",
    EventCategory.SUPPLY_CHAIN_DISRUPTION: "sector",
    EventCategory.NATURAL_DISASTER: "multi_sector",
    EventCategory.PANDEMIC: "market_wide",
    EventCategory.MARKET_CRASH: "market_wide",
    EventCategory.SHORT_SQUEEZE: "single_stock",
}
