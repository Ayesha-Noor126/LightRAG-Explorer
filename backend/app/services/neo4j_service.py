"""
Direct, read-only access to the Neo4j instance that LightRAG uses as its
graph storage backend. This is intentionally decoupled from
lightrag_service.py: LightRAG builds and owns the graph, we just read it
to power the Graph tab and analytics.

Queries are written generically (MATCH (n), MATCH ()-[r]->()) rather than
against LightRAG's specific node/relationship schema, so stats and
visualization keep working even if that internal schema changes between
LightRAG versions.
"""
from functools import lru_cache

from neo4j import GraphDatabase

from app.config import settings
from app.models.schemas import GraphDataResponse, GraphEdge, GraphNode, GraphStatsResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _get_driver():
    return GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
    )


def _node_label(node) -> str:
    """Prefer a human-readable property LightRAG commonly sets, else fall back."""
    for key in ("entity_id", "name", "id", "title"):
        if key in node and node[key]:
            return str(node[key])
    labels = list(node.labels) if hasattr(node, "labels") else []
    return labels[0] if labels else "Unknown"


def _node_type(node) -> str | None:
    for key in ("entity_type", "type"):
        if key in node and node[key]:
            return str(node[key])
    return None


def is_reachable() -> bool:
    try:
        driver = _get_driver()
        driver.verify_connectivity()
        return True
    except Exception:
        return False


def get_graph_stats() -> GraphStatsResponse:
    if not is_reachable():
        return GraphStatsResponse(
            node_count=0, edge_count=0, density=0.0, avg_degree=0.0, reachable=False
        )

    driver = _get_driver()
    with driver.session(database=settings.NEO4J_DATABASE) as session:
        node_count = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        edge_count = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]

    if node_count > 1:
        density = (2 * edge_count) / (node_count * (node_count - 1))
    else:
        density = 0.0
    avg_degree = (2 * edge_count) / node_count if node_count else 0.0

    return GraphStatsResponse(
        node_count=node_count,
        edge_count=edge_count,
        density=round(density, 4),
        avg_degree=round(avg_degree, 2),
        reachable=True,
    )


def get_graph_data(limit: int | None = None) -> GraphDataResponse:
    limit = limit or settings.GRAPH_VIEW_NODE_LIMIT

    if not is_reachable():
        return GraphDataResponse(nodes=[], edges=[], truncated=False)

    driver = _get_driver()
    with driver.session(database=settings.NEO4J_DATABASE) as session:
        total_nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]

        node_records = session.run(
            """
            MATCH (n)
            OPTIONAL MATCH (n)-[r]-()
            RETURN elementId(n) AS id, n AS node, count(r) AS degree
            ORDER BY degree DESC
            LIMIT $limit
            """,
            limit=limit,
        )
        nodes = []
        node_ids = set()
        for rec in node_records:
            node = rec["node"]
            node_id = rec["id"]
            node_ids.add(node_id)
            nodes.append(
                GraphNode(
                    id=node_id,
                    label=_node_label(node),
                    entity_type=_node_type(node),
                    description=node.get("description") or None,
                    source_id=node.get("source_id") or None,
                    degree=rec["degree"],
                )
            )

        edge_records = session.run(
            """
            MATCH (a)-[r]->(b)
            WHERE elementId(a) IN $ids AND elementId(b) IN $ids
            RETURN elementId(a) AS source, elementId(b) AS target,
                   type(r) AS label,
                   r.description AS description,
                   r.weight AS weight
            LIMIT $limit
            """,
            ids=list(node_ids),
            limit=limit * 3,
        )
        edges = [
            GraphEdge(
                source=rec["source"],
                target=rec["target"],
                label=rec["label"],
                description=rec["description"] or None,
                weight=float(rec["weight"]) if rec["weight"] is not None else None,
            )
            for rec in edge_records
        ]

    return GraphDataResponse(
        nodes=nodes, edges=edges, truncated=total_nodes > limit
    )


def close() -> None:
    try:
        _get_driver().close()
    except Exception:
        pass
