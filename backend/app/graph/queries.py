"""Traversal helpers and Cypher templates with point-in-time safeguards."""

from collections import deque
from datetime import datetime

from app.graph.schema import CausalEdge, GraphCoverageSummary


def build_multihop_query(max_depth: int) -> str:
    """Build a bounded Neo4j traversal query; depth is intentionally capped."""

    if not 1 <= max_depth <= 8:
        raise ValueError("max_depth must be in [1, 8]")
    return f"""
    MATCH path = (source:Company {{ticker: $source_ticker}})-[rels*1..{max_depth}]->(target:Company)
    WHERE all(rel IN rels WHERE rel.channel_type <> 'COMMON_FACTOR'
      AND rel.relationship_created_at <= datetime($as_of)
      AND (rel.source_date IS NULL OR rel.source_date <= datetime($as_of))
      AND (rel.temporal_approximation = false OR $allow_temporal_approximation = true))
    RETURN path
    """


def filter_edges_point_in_time(
    edges: list[CausalEdge], as_of: datetime, *, allow_temporal_approximation: bool = False
) -> list[CausalEdge]:
    """Filter graph state to what was knowable at the backtest date."""

    return [
        edge
        for edge in edges
        if edge.available_at(as_of, allow_temporal_approximation=allow_temporal_approximation)
    ]


class InMemoryCausalGraph:
    """Deterministic repository used by tests and offline forecast execution."""

    def __init__(self, edges: list[CausalEdge]) -> None:
        self.edges = list(edges)

    def outgoing(
        self,
        source_entity: str,
        *,
        as_of: datetime | None = None,
        allow_temporal_approximation: bool = False,
        causal_only: bool = True,
    ) -> list[CausalEdge]:
        edges = [edge for edge in self.edges if edge.source_entity == source_entity]
        if as_of is not None:
            edges = filter_edges_point_in_time(
                edges, as_of, allow_temporal_approximation=allow_temporal_approximation
            )
        if causal_only:
            edges = [edge for edge in edges if edge.participates_in_causal_propagation]
        return edges

    def traverse(
        self,
        roots: list[str],
        *,
        max_depth: int,
        as_of: datetime | None = None,
        allow_temporal_approximation: bool = False,
    ) -> list[tuple[list[CausalEdge], int]]:
        """Breadth-first causal traversal with per-path cycle prevention."""

        paths: list[tuple[list[CausalEdge], int]] = []
        queue: deque[tuple[str, list[CausalEdge], set[str]]] = deque(
            (root, [], {root}) for root in roots
        )
        while queue:
            entity, path, seen = queue.popleft()
            if len(path) >= max_depth:
                continue
            for edge in self.outgoing(
                entity,
                as_of=as_of,
                allow_temporal_approximation=allow_temporal_approximation,
                causal_only=True,
            ):
                if edge.target_entity in seen:
                    continue
                next_path = [*path, edge]
                paths.append((next_path, len(next_path)))
                queue.append((edge.target_entity, next_path, {*seen, edge.target_entity}))
        return paths

    def coverage(self, entities: list[str]) -> GraphCoverageSummary:
        relevant = [
            edge
            for edge in self.edges
            if edge.source_entity in entities or edge.target_entity in entities
        ]
        covered = sorted(
            {entity for edge in relevant for entity in (edge.source_entity, edge.target_entity)}
            & set(entities)
        )
        causal = [edge for edge in relevant if edge.participates_in_causal_propagation]
        contextual = [edge for edge in relevant if not edge.participates_in_causal_propagation]
        missing = sorted(set(entities) - set(covered))
        limitations = [f"No graph coverage for {entity}" for entity in missing]
        if any(edge.temporal_approximation for edge in relevant):
            limitations.append(
                "Some graph edges are temporal approximations and are excluded from rigorous PIT tests."
            )
        return GraphCoverageSummary(
            entities_requested=entities,
            entities_with_edges=covered,
            covered_entity_ratio=len(covered) / len(entities) if entities else 1.0,
            causal_edge_count=len(causal),
            contextual_edge_count=len(contextual),
            approximate_edge_count=sum(edge.temporal_approximation for edge in relevant),
            limitations=limitations,
        )
