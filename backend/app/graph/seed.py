"""Clearly labelled semiconductor graph bootstrap for demo visualization.

The relationships have provenance fields but no learned coefficients.  They are
available for an illustrative forecast only when the caller permits temporal
approximations, and never for rigorous point-in-time model scoring.
"""

from datetime import UTC, datetime

from app.graph.schema import (
    CHANNEL_FOR_RELATIONSHIP,
    CausalEdge,
    EstimationMetadata,
    EstimationMethod,
    RelationshipType,
    VerificationStatus,
)


def _prior_edge(
    source: str,
    target: str,
    relationship: RelationshipType,
    *,
    exposure: float,
    substitutability: float,
    lag: int,
    evidence: str,
) -> CausalEdge:
    return CausalEdge(
        source_entity=source,
        target_entity=target,
        relationship_type=relationship,
        channel_type=CHANNEL_FOR_RELATIONSHIP[relationship],
        strength=0.15,
        dependency_exposure=exposure,
        substitutability=substitutability,
        historical_coefficient=None,
        historical_observation_count=0,
        estimation_metadata=EstimationMetadata(
            sample_count=0, estimation_method=EstimationMethod.MANUAL_PRIOR, is_prior=True
        ),
        typical_time_lag_days=lag,
        min_lag_days=max(0, lag - 2),
        max_lag_days=lag + 14,
        relationship_created_at=datetime(2024, 1, 1, tzinfo=UTC),
        relationship_verified_at=None,
        source_date=datetime(2024, 1, 1, tzinfo=UTC),
        temporal_approximation=True,
        confidence=0.55,
        evidence_count=1,
        evidence_sources=[evidence],
        verification_status=VerificationStatus.APPROXIMATE,
    )


def semiconductor_seed_edges() -> list[CausalEdge]:
    """Return demo-only, source-labelled edges without invented calibration."""

    return [
        _prior_edge(
            "TSM",
            "NVDA",
            RelationshipType.SUPPLIES,
            exposure=0.75,
            substitutability=0.25,
            lag=7,
            evidence="https://investor.nvidia.com/financial-info/annual-reports-and-proxies/default.aspx",
        ),
        _prior_edge(
            "TSM",
            "AAPL",
            RelationshipType.SUPPLIES,
            exposure=0.60,
            substitutability=0.35,
            lag=14,
            evidence="https://investor.tsmc.com/english/annual-reports",
        ),
        _prior_edge(
            "TSM",
            "AMD",
            RelationshipType.SUPPLIES,
            exposure=0.70,
            substitutability=0.30,
            lag=7,
            evidence="https://ir.amd.com/financial-information/sec-filings",
        ),
        _prior_edge(
            "NVDA",
            "MSFT",
            RelationshipType.SUPPLIES,
            exposure=0.45,
            substitutability=0.45,
            lag=21,
            evidence="https://www.microsoft.com/en-us/annualreports",
        ),
        _prior_edge(
            "MSFT",
            "ORCL",
            RelationshipType.COMPETES_WITH,
            exposure=0.35,
            substitutability=0.60,
            lag=30,
            evidence="https://www.oracle.com/corporate/investor-relations/financials/",
        ),
        _prior_edge(
            "AMD",
            "NVDA",
            RelationshipType.COMPETES_WITH,
            exposure=0.55,
            substitutability=0.65,
            lag=14,
            evidence="https://ir.amd.com/financial-information/sec-filings",
        ),
        _prior_edge(
            "TSM",
            "Samsung Electronics",
            RelationshipType.COMPETES_WITH,
            exposure=0.45,
            substitutability=0.50,
            lag=30,
            evidence="https://images.samsung.com/is/content/samsung/assets/global/ir/docs/2024_Annual_Report.pdf",
        ),
        _prior_edge(
            "TSM",
            "SOXX",
            RelationshipType.CORRELATED_WITH,
            exposure=0.0,
            substitutability=0.0,
            lag=0,
            evidence="https://www.ishares.com/us/products/239705/ishares-phlx-semiconductor-etf",
        ),
    ]
