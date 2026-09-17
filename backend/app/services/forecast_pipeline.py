"""Forecast pipeline — orchestrates the full prediction flow.

    Event → Classify → Find Similar → Detect Regime → Impact → Explain
"""

import logging
import math
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.yahoo_finance import MARKET_BENCHMARK, YahooFinanceClient
from app.intelligence.classifier import EventClassifier
from app.intelligence.impact import MarketImpactEngine, ForecastResult
from app.intelligence.ontology import EventCategory, EventOntologySchema
from app.intelligence.regime import MarketRegime, MarketRegimeDetector
from app.intelligence.similarity import HybridSimilarityEngine, SimilarityBreakdown
from app.llm.explainer import explain_forecast
from app.llm.provider import LLMProviderFactory
from app.vectors.store import QdrantEventStore

logger = logging.getLogger(__name__)


class ForecastPipeline:
    """Orchestrate the full forecast generation flow."""

    def __init__(
        self,
        session: AsyncSession,
        qdrant_store: QdrantEventStore | None = None,
        classifier: EventClassifier | None = None,
        neo4j_client: Any | None = None,
    ) -> None:
        self.session = session
        self.qdrant_store = qdrant_store
        self.neo4j_client = neo4j_client
        self.classifier = classifier or EventClassifier(use_finbert=False)
        self.similarity_engine = HybridSimilarityEngine()
        self.impact_engine = MarketImpactEngine()
        self.regime_detector = MarketRegimeDetector()
        self.yf_client = YahooFinanceClient()

    async def forecast_from_text(
        self,
        title: str,
        description: str,
        affected_tickers: list[str] | None = None,
    ) -> dict[str, Any]:
        """Generate a forecast from raw event text.

        This is the primary entry point — takes free-text event
        description and produces a full forecast with LLM explanation.
        """
        # Step 1: Classify the event
        category = self.classifier.classify_category(title, description)
        sentiment = self.classifier.score_sentiment(f"{title} {description}")
        severity = self.classifier.estimate_severity(category, sentiment)

        event = EventOntologySchema(
            title=title,
            description=description,
            source_url="",
            published_at=datetime.now(tz=timezone.utc),
            event_date=datetime.now(tz=timezone.utc),
            category=category,
            severity_score=severity,
            affected_tickers=affected_tickers or [],
        )

        # Step 2: Detect current market regime
        current_regime = await self._detect_current_regime()

        # Step 3: Find similar historical events via Qdrant
        similar_events = await self._find_similar_events(event, current_regime)

        # Step 4: Determine affected tickers
        tickers = affected_tickers or self._infer_tickers(event)

        # Step 5: Compute forecasts for each ticker
        forecasts: list[dict[str, Any]] = []
        causal_paths: list[dict[str, Any]] = []
        
        # Optionally fetch causal graph surrounding affected_tickers
        if self.neo4j_client and tickers:
            try:
                # Get a small sub-graph starting from these tickers
                ticker_list_str = "[" + ", ".join(f"'{t}'" for t in tickers[:5]) + "]"
                query = f"""
                MATCH path = (s:Company)-[*1..2]->(t:Company)
                WHERE s.ticker IN {ticker_list_str}
                RETURN [n IN nodes(path) | n.ticker] AS path_tickers,
                       [r IN relationships(path) | type(r)] AS path_rels
                LIMIT 20
                """
                logger.info(f"Running Neo4j causal propagation for {ticker_list_str}")
                results = await self.neo4j_client.run(query)
                logger.info(f"Neo4j propagation returned {len(results)} paths")
                causal_paths = results
            except Exception as e:
                logger.error(f"Neo4j propagation failed: {e}", exc_info=True)

        for ticker in tickers[:10]:  # Cap at 10 tickers
            forecast_result = self.impact_engine.compute_forecast(
                event=event,
                ticker=ticker,
                similar_events=similar_events,
                current_regime=current_regime,
            )
            forecast_result.company_name = self.yf_client.get_company_name(ticker)

            forecasts.append(self._format_forecast(forecast_result))

        # Step 6: Generate LLM explanation (best-effort)
        explanation = await self._explain(forecasts, event, current_regime)

        # Step 7: Store the forecast
        forecast_id = str(uuid.uuid4())
        await self._store_forecast(forecast_id, event, forecasts, explanation)

        return {
            "forecast_id": forecast_id,
            "event": {
                "title": event.title,
                "category": event.category.value,
                "severity_score": event.severity_score,
                "severity_level": event.severity_level.value,
            },
            "current_regime": current_regime.value,
            "forecasts": forecasts,
            "causal_paths": causal_paths,
            "explanation": explanation,
            "meta": {
                "similar_events_found": len(similar_events),
                "tickers_analyzed": len(forecasts),
            },
        }

    async def forecast_from_event_id(self, event_id: str) -> dict[str, Any]:
        """Generate a forecast from a stored event ID."""
        # Load event from database
        stmt = text("""
            SELECT title, description, category, severity_score,
                   affected_tickers
            FROM events WHERE id = :event_id
        """)
        result = await self.session.execute(stmt, {"event_id": event_id})
        row = result.mappings().first()

        if not row:
            raise ValueError(f"Event {event_id} not found")

        tickers = row["affected_tickers"].split(",") if row["affected_tickers"] else []

        return await self.forecast_from_text(
            title=row["title"],
            description=row["description"],
            affected_tickers=tickers,
        )

    async def _detect_current_regime(self) -> MarketRegime:
        """Detect the current market regime from recent SPY returns."""
        try:
            end = date.today()
            start = end - timedelta(days=120)
            spy_closes = self.yf_client.download_close_series(
                MARKET_BENCHMARK, start, end
            )

            if len(spy_closes) < 20:
                logger.warning("Insufficient SPY data for regime detection")
                return MarketRegime.SIDEWAYS

            sorted_dates = sorted(spy_closes.keys())
            prices = [spy_closes[d] for d in sorted_dates]

            returns = []
            for i in range(1, len(prices)):
                if prices[i - 1] > 0:
                    returns.append(math.log(prices[i] / prices[i - 1]))

            result = self.regime_detector.detect(returns)
            logger.info(f"Detected market regime: {result.regime.value}")
            return result.regime

        except Exception as e:
            logger.error(f"Regime detection failed: {e}")
            return MarketRegime.SIDEWAYS

    async def _find_similar_events(
        self,
        event: EventOntologySchema,
        current_regime: MarketRegime,
    ) -> list[tuple[EventOntologySchema, SimilarityBreakdown, float]]:
        """Find similar historical events using Qdrant + structured scoring."""
        similar: list[tuple[EventOntologySchema, SimilarityBreakdown, float]] = []

        # Query Qdrant for semantically similar events
        if self.qdrant_store:
            try:
                search_text = f"{event.title}. {event.description}"
                qdrant_results = await self.qdrant_store.search_similar(
                    search_text, top_k=30
                )

                for event_id, semantic_score, payload in qdrant_results:
                    # Reconstruct a minimal EventOntologySchema from payload
                    hist_event = EventOntologySchema(
                        title=payload.get("text_preview", "")[:200],
                        description=payload.get("text_preview", ""),
                        source_url="",
                        published_at=datetime.now(tz=timezone.utc),
                        category=EventCategory(payload.get("category", "OTHER")),
                        severity_score=payload.get("severity_score", 0.5),
                        affected_tickers=payload.get("affected_tickers", []),
                    )

                    # Load historical return for this event from DB
                    hist_return = await self._get_event_return(event_id)

                    # Compute full hybrid similarity
                    hist_regime_str = payload.get("market_regime", "SIDEWAYS")
                    try:
                        hist_regime = MarketRegime(hist_regime_str)
                    except ValueError:
                        hist_regime = MarketRegime.SIDEWAYS

                    breakdown = self.similarity_engine.compute_similarity(
                        query=event,
                        candidate=hist_event,
                        semantic_score=semantic_score,
                        query_regime=current_regime,
                        candidate_regime=hist_regime,
                    )

                    similar.append((hist_event, breakdown, hist_return))

            except Exception as e:
                logger.warning(f"Qdrant search failed (non-fatal): {e}")

        # Also search by category match in the database
        db_matches = await self._find_category_matches(event.category.value)
        for match in db_matches:
            hist_event = EventOntologySchema(
                title=match["title"],
                description=match["title"],
                source_url="",
                published_at=datetime.now(tz=timezone.utc),
                category=EventCategory(match["category"]),
                severity_score=0.5,
            )
            breakdown = self.similarity_engine.compute_similarity(
                query=event,
                candidate=hist_event,
                semantic_score=0.3,  # Lower default for non-Qdrant matches
                query_regime=current_regime,
                candidate_regime=MarketRegime.SIDEWAYS,
            )
            hist_return = match.get("avg_return", 0.0)
            similar.append((hist_event, breakdown, hist_return))

        # Sort by similarity and take top 20
        similar.sort(key=lambda x: x[1].overall_score, reverse=True)
        return similar[:20]

    async def _get_event_return(self, event_id: str) -> float:
        """Load the 30-day return for an event from historical outcomes."""
        try:
            stmt = text("""
                SELECT AVG(return_30d) as avg_return
                FROM historical_event_outcomes
                WHERE canonical_event_id = :event_id
                  AND return_30d IS NOT NULL
            """)
            result = await self.session.execute(stmt, {"event_id": event_id})
            row = result.mappings().first()
            return float(row["avg_return"]) if row and row["avg_return"] else 0.0
        except Exception:
            return 0.0

    async def _find_category_matches(self, category: str) -> list[dict[str, Any]]:
        """Find canonical events with the same category that have outcomes."""
        try:
            stmt = text("""
                SELECT ce.title, ce.category,
                       AVG(heo.return_30d) as avg_return
                FROM canonical_events ce
                JOIN historical_event_outcomes heo ON heo.canonical_event_id = ce.id
                WHERE ce.category = :category
                  AND heo.return_30d IS NOT NULL
                GROUP BY ce.id, ce.title, ce.category
                LIMIT 20
            """)
            result = await self.session.execute(stmt, {"category": category})
            return [dict(row) for row in result.mappings().all()]
        except Exception:
            return []

    def _infer_tickers(self, event: EventOntologySchema) -> list[str]:
        """Infer affected tickers from event category."""
        from app.ingestion.outcome_collector import CATEGORY_TICKER_MAP
        tickers, _ = CATEGORY_TICKER_MAP.get(
            event.category.value, (["SPY"], "Technology")
        )
        return tickers

    def _format_forecast(self, result: ForecastResult) -> dict[str, Any]:
        """Format a ForecastResult into a JSON-serializable dict."""
        direction = "BEARISH" if result.predicted_impact < 0 else "BULLISH"
        if abs(result.predicted_impact) < 0.005:
            direction = "NEUTRAL"

        return {
            "ticker": result.ticker,
            "company_name": result.company_name,
            "direction": direction,
            "predicted_impact": round(result.predicted_impact * 100, 2),
            "predicted_impact_pct": f"{result.predicted_impact * 100:+.2f}%",
            "direction_probability": round(result.direction_probability * 100, 1),
            "model_confidence": round(result.model_confidence * 100, 1),
            "confidence_is_calibrated": result.confidence_is_calibrated,
            "time_horizon_days": result.time_horizon_days,
            "return_range": {
                "p25": round(result.return_p25 * 100, 2),
                "p50": round(result.return_p50 * 100, 2),
                "p75": round(result.return_p75 * 100, 2),
            },
            "sample_count": result.sample_count,
            "insufficient_evidence": result.insufficient_historical_evidence,
            "similar_events": result.similar_events[:5],
        }

    async def _explain(
        self,
        forecasts: list[dict],
        event: EventOntologySchema,
        regime: MarketRegime,
    ) -> str:
        """Generate LLM explanation (best-effort, falls back to structured text)."""
        try:
            provider = await LLMProviderFactory.get_provider()

            # Build a summary for the LLM
            forecast_lines = []
            for f in forecasts[:5]:
                forecast_lines.append(
                    f"- {f['ticker']}: {f['predicted_impact_pct']} "
                    f"({f['direction']}, {f['direction_probability']}% likely, "
                    f"confidence {f['model_confidence']}%)"
                )

            prompt = f"""Explain this market forecast to an investor.

Event: {event.title}
Category: {event.category.value}
Severity: {event.severity_level.value} ({event.severity_score:.2f})
Market Regime: {regime.value}

Forecasted impacts:
{chr(10).join(forecast_lines)}

Provide:
1. A 2-3 sentence summary
2. Why these impacts are expected
3. Key risks and limitations
4. What to watch for"""

            return await provider.generate(
                prompt=prompt,
                system_prompt=(
                    "You are a financial analyst explaining statistical estimates. "
                    "Use 'estimates' not 'predicts'. Always caveat with sample size and confidence."
                ),
            )

        except Exception as e:
            logger.warning(f"LLM explanation failed, using fallback: {e}")
            lines = [f"**{event.title}** — {event.category.value} event, "
                     f"severity {event.severity_level.value}, regime {regime.value}."]
            for f in forecasts[:5]:
                lines.append(
                    f"- **{f['ticker']}**: {f['predicted_impact_pct']} "
                    f"({f['direction']}, {f['direction_probability']}% direction likelihood, "
                    f"{f['model_confidence']}% model confidence, "
                    f"sample={f['sample_count']})"
                )
            if any(f["insufficient_evidence"] for f in forecasts):
                lines.append("\n⚠️ Some estimates have insufficient historical evidence.")
            return "\n".join(lines)

    async def _store_forecast(
        self,
        forecast_id: str,
        event: EventOntologySchema,
        forecasts: list[dict],
        explanation: str,
    ) -> None:
        """Persist the forecast to the database."""
        try:
            import json
            import uuid
            # Ensure event exists to satisfy FK if needed, but since this is free-text,
            # we might just generate a dummy event_id or link it to a canonical event if one exists.
            # For now, we will skip inserting into the 'forecasts' table because 
            # the schema expects a strict event_id foreign key and one row per ticker.
            # We'll just log it instead of crashing the DB schema.
            logger.info(f"Forecast {forecast_id} generated successfully but DB storage is mocked for now.")
        except Exception as e:
            logger.error(f"Failed to store forecast: {e}")
