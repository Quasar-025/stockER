"""Graph router — explore the causal supply-chain graph in Neo4j."""

import logging

from fastapi import APIRouter, HTTPException

from app.graph.client import Neo4jGraphClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/entities")
async def list_graph_entities():
    """List all company nodes in the causal graph."""
    client = Neo4jGraphClient()
    try:
        query = """
            MATCH (n:Company)
            RETURN n.ticker as ticker, n.name as name, n.sector as sector, n.industry as industry
            ORDER BY n.ticker
        """
        results = await client.run(query)
        return {"entities": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Neo4j query failed: {e}")
        raise HTTPException(status_code=500, detail="Graph database unavailable")
    finally:
        await client.close()


@router.get("/edges")
async def list_graph_edges(ticker: str | None = None):
    """List causal relationships, optionally filtered by a source ticker."""
    client = Neo4jGraphClient()
    try:
        where_clause = "WHERE source.ticker = $ticker" if ticker else ""
        query = f"""
            MATCH (source:Company)-[r]->(target:Company)
            {where_clause}
            RETURN source.ticker as source_ticker,
                   type(r) as relationship_type,
                   r.channel_type as channel_type,
                   target.ticker as target_ticker,
                   r.confidence as confidence,
                   r.lag_days as lag_days,
                   r.temporal_approximation as is_approximate
            ORDER BY source.ticker, target.ticker
        """
        results = await client.run(query, {"ticker": ticker.upper() if ticker else None})
        return {"edges": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Neo4j query failed: {e}")
        raise HTTPException(status_code=500, detail="Graph database unavailable")
    finally:
        await client.close()


@router.get("/traverse/{ticker}")
async def traverse_graph(ticker: str, max_depth: int = 3):
    """Breadth-first traversal from a source ticker to find propagation paths."""
    ticker = ticker.upper()
    client = Neo4jGraphClient()
    try:
        # We use a simple path matching query up to max_depth
        query = f"""
            MATCH path = (source:Company {{ticker: $ticker}})-[*1..{max_depth}]->(target:Company)
            WITH path, nodes(path) as nodes, relationships(path) as rels
            RETURN
                [n IN nodes | n.ticker] as path_tickers,
                [r IN rels | type(r)] as relationship_types,
                [r IN rels | r.channel_type] as channel_types,
                reduce(total = 0, r IN rels | total + r.lag_days) as cumulative_lag,
                length(path) as depth
            ORDER BY depth, target.ticker
        """
        results = await client.run(query, {"ticker": ticker})

        # Format paths for the frontend
        formatted_paths = []
        for r in results:
            formatted_paths.append({
                "path": " → ".join(r["path_tickers"]),
                "nodes": r["path_tickers"],
                "relationships": r["relationship_types"],
                "channels": r["channel_types"],
                "depth": r["depth"],
                "cumulative_lag_days": r["cumulative_lag"],
            })

        return {
            "source_ticker": ticker,
            "max_depth": max_depth,
            "paths": formatted_paths,
            "count": len(formatted_paths),
        }
    except Exception as e:
        logger.error(f"Neo4j query failed: {e}")
        raise HTTPException(status_code=500, detail="Graph database unavailable")
    finally:
        await client.close()
