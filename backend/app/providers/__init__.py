"""Stable provider interfaces over vendor-specific ingestion clients.

The application depends on these contracts rather than directly on Finnhub,
FRED, SEC EDGAR, or Alpha Vantage.  Existing clients remain intact and are
adapted below to avoid a disruptive ingestion rewrite.
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from app.ingestion.alphavantage import AlphaVantageClient
from app.ingestion.finnhub_rest import FinnhubRESTClient
from app.ingestion.fred import FREDClient
from app.ingestion.sec_edgar import SecEdgarClient
from app.providers.data_quality import (
    DataQualityRecord,
    ProviderPayload,
    VerificationStatus,
)


class MarketDataProvider(ABC):
    """Interface for market-price and company market-data responses."""

    @abstractmethod
    async def company_profile(self, ticker: str) -> ProviderPayload[dict[str, Any]]:
        """Return a company profile with origin metadata."""


class NewsDataProvider(ABC):
    """Interface for company news and sentiment feeds."""

    @abstractmethod
    async def company_news(
        self, ticker: str, start_date: str, end_date: str
    ) -> ProviderPayload[list[dict[str, Any]]]:
        """Return news records with provider-quality metadata."""


class CompanyDataProvider(ABC):
    """Interface for company filings and profiles."""

    @abstractmethod
    async def latest_filings(self, ticker: str) -> ProviderPayload[list[dict[str, Any]]]:
        """Return filings with provenance."""


class MacroDataProvider(ABC):
    """Interface for macroeconomic time series."""

    @abstractmethod
    async def series_observations(
        self, series_id: str, limit: int = 100
    ) -> ProviderPayload[list[dict[str, Any]]]:
        """Return macro observations with provenance."""


class SupplyChainDataProvider(ABC):
    """Interface reserved for evidence-backed supply-chain sources.

    Implementations must return source documents, not economically plausible
    relationships inferred without evidence.
    """

    @abstractmethod
    async def relationship_evidence(self, entity: str) -> ProviderPayload[list[dict[str, Any]]]:
        """Return evidence records that may support graph-edge review."""


def _quality(source: str, *, completeness: float, timestamp: datetime | None = None) -> DataQualityRecord:
    return DataQualityRecord.from_source(
        source=source,
        source_timestamp=timestamp,
        completeness=completeness,
        verification_status=VerificationStatus.UNVERIFIED,
    )


class FinnhubProvider(MarketDataProvider, NewsDataProvider):
    """Adapter preserving the existing Finnhub REST client behavior."""

    def __init__(self, client: FinnhubRESTClient | None = None) -> None:
        self.client = client or FinnhubRESTClient()

    async def company_profile(self, ticker: str) -> ProviderPayload[dict[str, Any]]:
        data = await self.client.get_company_profile(ticker)
        return ProviderPayload(data=data, quality=_quality("finnhub", completeness=1.0))

    async def company_news(
        self, ticker: str, start_date: str, end_date: str
    ) -> ProviderPayload[list[dict[str, Any]]]:
        data = await self.client.get_company_news(ticker, start_date, end_date)
        return ProviderPayload(data=data, quality=_quality("finnhub", completeness=1.0))

    async def close(self) -> None:
        await self.client.close()


class AlphaVantageProvider(NewsDataProvider):
    """Adapter for Alpha Vantage sentiment data."""

    def __init__(self, client: AlphaVantageClient | None = None) -> None:
        self.client = client or AlphaVantageClient()

    async def company_news(
        self, ticker: str, start_date: str, end_date: str
    ) -> ProviderPayload[list[dict[str, Any]]]:
        # Alpha Vantage does not support this exact date-range contract on the
        # free endpoint; retain its response and make completeness explicit.
        response = await self.client.get_news_sentiment(ticker)
        return ProviderPayload(
            data=response.get("feed", []),
            quality=_quality("alphavantage", completeness=0.7),
        )

    async def close(self) -> None:
        await self.client.close()


class FREDProvider(MacroDataProvider):
    """Adapter for the existing FRED client."""

    def __init__(self, client: FREDClient | None = None) -> None:
        self.client = client or FREDClient()

    async def series_observations(
        self, series_id: str, limit: int = 100
    ) -> ProviderPayload[list[dict[str, Any]]]:
        data = await self.client.get_series_observations(series_id, limit=limit)
        return ProviderPayload(data=data, quality=_quality("fred", completeness=1.0))

    async def close(self) -> None:
        await self.client.close()


class SecEdgarProvider(CompanyDataProvider):
    """Adapter for the existing SEC EDGAR client."""

    def __init__(self, client: SecEdgarClient | None = None) -> None:
        self.client = client or SecEdgarClient()

    async def latest_filings(self, ticker: str) -> ProviderPayload[list[dict[str, Any]]]:
        data = await self.client.get_latest_filings(ticker)
        return ProviderPayload(
            data=data,
            quality=_quality("sec_edgar", completeness=1.0, timestamp=datetime.now(UTC)),
        )

    async def close(self) -> None:
        await self.client.close()


__all__ = [
    "AlphaVantageProvider",
    "CompanyDataProvider",
    "DataQualityRecord",
    "FREDProvider",
    "FinnhubProvider",
    "MacroDataProvider",
    "MarketDataProvider",
    "NewsDataProvider",
    "ProviderPayload",
    "SecEdgarProvider",
    "SupplyChainDataProvider",
]
