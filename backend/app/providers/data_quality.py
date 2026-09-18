"""Provider payload provenance and freshness metadata.

Forecasting code must be able to distinguish a fresh, verified observation from
an unavailable or stale feed.  This module deliberately records provenance; it
does not infer that a value is correct merely because a provider returned it.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TypeVar

from pydantic import BaseModel, Field


class DataStatus(StrEnum):
    """Operational state of a data source at the time it was read."""

    HEALTHY = "HEALTHY"
    DELAYED = "DELAYED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class VerificationStatus(StrEnum):
    """How strongly a record's origin has been verified."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    APPROXIMATE = "approximate"
    UNRESOLVED = "unresolved"


class DataQualityRecord(BaseModel):
    """Quality and provenance attached to every provider response.

    ``quality_score`` and ``confidence`` describe the feed/record quality,
    rather than the probability of a forecast outcome.
    """

    source: str = Field(min_length=1)
    source_timestamp: datetime | None = None
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data_quality: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness_seconds: float | None = Field(default=None, ge=0.0)
    completeness: float = Field(ge=0.0, le=1.0)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    status: DataStatus = DataStatus.HEALTHY

    @classmethod
    def from_source(
        cls,
        *,
        source: str,
        source_timestamp: datetime | None,
        completeness: float = 1.0,
        verification_status: VerificationStatus = VerificationStatus.UNVERIFIED,
        stale_after_seconds: float = 86_400,
        ingested_at: datetime | None = None,
    ) -> "DataQualityRecord":
        """Create a transparent quality record from timestamp availability.

        Missing source time does not become fresh by assumption: it lowers
        quality and is marked delayed.  The score is provider-data quality only
        and never substitutes for forecast confidence.
        """

        captured_at = ingested_at or datetime.now(UTC)
        if source_timestamp is None:
            return cls(
                source=source,
                source_timestamp=None,
                ingested_at=captured_at,
                data_quality=round(0.5 * completeness, 4),
                confidence=0.4,
                completeness=completeness,
                verification_status=verification_status,
                status=DataStatus.DELAYED,
            )

        if source_timestamp.tzinfo is None:
            source_timestamp = source_timestamp.replace(tzinfo=UTC)
        freshness = max(0.0, (captured_at - source_timestamp).total_seconds())
        if freshness > stale_after_seconds:
            status = DataStatus.STALE
            quality = 0.45 * completeness
            confidence = 0.4
        else:
            status = DataStatus.HEALTHY
            quality = 0.9 * completeness
            confidence = 0.8
        return cls(
            source=source,
            source_timestamp=source_timestamp,
            ingested_at=captured_at,
            data_quality=round(quality, 4),
            confidence=confidence,
            freshness_seconds=round(freshness, 3),
            completeness=completeness,
            verification_status=verification_status,
            status=status,
        )


T = TypeVar("T")


@dataclass(frozen=True)
class ProviderPayload[T]:
    """A provider result coupled to record-level quality metadata."""

    data: T
    quality: DataQualityRecord
