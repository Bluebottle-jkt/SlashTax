from typing import Optional, Any
import logging
from datetime import datetime

from app.core.database import execute_query, execute_write
from app.schemas.models import (
    GraphData, GraphNode, GraphEdge, Person, Post,
    Location, Account, Hashtag, SearchQuery, StatsResponse
)

logger = logging.getLogger(__name__)


def _serialize_value(value: Any) -> Any:
    """Convert Neo4j types to JSON-serializable Python types."""
    if value is None:
        return None
    # Handle Neo4j DateTime
    if hasattr(value, 'iso_format'):
        return value.iso_format()
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    # Handle lists
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    # Handle dicts
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    return value


def _sanitize_properties(props: dict) -> dict:
    """Sanitize all properties to be JSON-serializable."""
    if not props:
        return {}
    return {k: _serialize_value(v) for k, v in props.items()}


def _sanitize_node(n: dict) -> dict:
    """Sanitize a node dict for GraphNode creation."""
    if n.get("properties"):
        n["properties"] = _sanitize_properties(n["properties"])
    return n


def _sanitize_edge(e: dict) -> dict:
    """Sanitize an edge dict for GraphEdge creation."""
    if e.get("properties"):
        e["properties"] = _sanitize_properties(e["properties"])
    return e


class GraphService:
    """Service for Neo4j graph operations and queries."""

    def get_full_graph(self, limit: int = 500) -> GraphData:
        """Get the full graph data for visualization."""
        query = """
        MATCH (n)
        WITH n LIMIT $limit
        OPTIONAL MATCH (n)-[r]->(m)
        WHERE m IS NOT NULL
        RETURN
            collect(DISTINCT {
                id: coalesce(n.id, id(n)),
                label: CASE
                    WHEN labels(n)[0] = 'Face' THEN 'Face ' + substring(n.id, 0, 8)
                    WHEN labels(n)[0] = 'FaceCluster' THEN coalesce(n.label, 'Cluster ' + substring(n.id, 0, 8))
                    ELSE coalesce(n.name, n.username, n.shortcode, 'Unknown')
                END,
                type: labels(n)[0],
                properties: properties(n)
            }) as nodes,
            collect(DISTINCT {
                source: coalesce(startNode(r).id, id(startNode(r))),
                target: coalesce(endNode(r).id, id(endNode(r))),
                type: type(r),
                properties: properties(r)
            }) as edges
        """

        results = execute_query(query, {"limit": limit})

        if not results:
            return GraphData(nodes=[], edges=[])

        data = results[0]
        nodes = [
            GraphNode(**_sanitize_node(n))
            for n in data.get("nodes", []) if n.get("id")
        ]
        edges = [
            GraphEdge(**_sanitize_edge(e))
            for e in data.get("edges", [])
            if e.get("source") and e.get("target") and e.get("type")
        ]

        return GraphData(nodes=nodes, edges=edges)

    def get_person_network(self, person_id: str, depth: int = 2) -> GraphData:
        """Get the network around a specific person."""
        query = """
        MATCH (p:Person {id: $person_id})
        CALL apoc.path.subgraphAll(p, {
            maxLevel: $depth,
            relationshipFilter: 'APPEARS_IN|POSTED|AT_LOCATION|HAS_HASHTAG'
        })
        YIELD nodes, relationships
        RETURN
            [n IN nodes | {
                id: coalesce(n.id, id(n)),
                label: coalesce(n.name, n.username, n.shortcode, 'Unknown'),
                type: labels(n)[0],
                properties: properties(n)
            }] as nodes,
            [r IN relationships | {
                source: coalesce(startNode(r).id, id(startNode(r))),
                target: coalesce(endNode(r).id, id(endNode(r))),
                type: type(r),
                properties: properties(r)
            }] as edges
        """

        try:
            results = execute_query(query, {"person_id": person_id, "depth": depth})
        except Exception:
            # Fallback if APOC is not installed
            return self._get_person_network_fallback(person_id, depth)

        if not results:
            return GraphData(nodes=[], edges=[])

        data = results[0]
        nodes = [GraphNode(**_sanitize_node(n)) for n in data.get("nodes", [])]
        edges = [GraphEdge(**_sanitize_edge(e)) for e in data.get("edges", [])]

        return GraphData(nodes=nodes, edges=edges)

    def _get_person_network_fallback(self, person_id: str, depth: int) -> GraphData:
        """Fallback method without APOC."""
        query = """
        MATCH (p:Person {id: $person_id})-[r1:APPEARS_IN]->(post:Post)
        OPTIONAL MATCH (post)<-[:POSTED]-(account:Account)
        OPTIONAL MATCH (post)-[:AT_LOCATION]->(loc:Location)
        OPTIONAL MATCH (post)-[:HAS_HASHTAG]->(hash:Hashtag)
        OPTIONAL MATCH (other:Person)-[:APPEARS_IN]->(post)
        WHERE other.id <> $person_id
        RETURN
            collect(DISTINCT {
                id: p.id,
                label: p.name,
                type: 'Person',
                properties: properties(p)
            }) +
            collect(DISTINCT {
                id: post.id,
                label: post.shortcode,
                type: 'Post',
                properties: properties(post)
            }) +
            collect(DISTINCT CASE WHEN account IS NOT NULL THEN {
                id: account.id,
                label: account.username,
                type: 'Account',
                properties: properties(account)
            } END) +
            collect(DISTINCT CASE WHEN loc IS NOT NULL THEN {
                id: loc.id,
                label: loc.name,
                type: 'Location',
                properties: properties(loc)
            } END) +
            collect(DISTINCT CASE WHEN hash IS NOT NULL THEN {
                id: hash.id,
                label: hash.name,
                type: 'Hashtag',
                properties: properties(hash)
            } END) +
            collect(DISTINCT CASE WHEN other IS NOT NULL THEN {
                id: other.id,
                label: other.name,
                type: 'Person',
                properties: properties(other)
            } END) as nodes
        """

        results = execute_query(query, {"person_id": person_id})

        if not results:
            return GraphData(nodes=[], edges=[])

        all_nodes = [n for n in results[0].get("nodes", []) if n]
        nodes = [GraphNode(**_sanitize_node(n)) for n in all_nodes if n.get("id")]

        # Get edges separately
        edge_query = """
        MATCH (p:Person {id: $person_id})-[r]->(connected)
        WHERE connected:Post
        WITH p, r, connected
        OPTIONAL MATCH (connected)-[r2]->(related)
        RETURN
            collect(DISTINCT {
                source: p.id,
                target: connected.id,
                type: type(r)
            }) +
            collect(DISTINCT CASE WHEN r2 IS NOT NULL THEN {
                source: connected.id,
                target: related.id,
                type: type(r2)
            } END) as edges
        """

        edge_results = execute_query(edge_query, {"person_id": person_id})
        edges = []
        if edge_results:
            edges = [
                GraphEdge(**e) for e in edge_results[0].get("edges", [])
                if e and e.get("source") and e.get("target")
            ]

        return GraphData(nodes=nodes, edges=edges)

    def search(self, query: SearchQuery) -> GraphData:
        """Search across the graph."""
        search_queries = {
            "all": self._search_all,
            "person": self._search_persons,
            "location": self._search_locations,
            "caption": self._search_captions,
            "hashtag": self._search_hashtags,
        }

        search_func = search_queries.get(query.search_type, self._search_all)
        return search_func(query.query, query.limit)

    def _search_all(self, search_term: str, limit: int) -> GraphData:
        """Search across all node types."""
        query = """
        CALL {
            MATCH (p:Person)
            WHERE toLower(p.name) CONTAINS toLower($term)
            RETURN p as node, 'Person' as type
            UNION
            MATCH (l:Location)
            WHERE toLower(l.name) CONTAINS toLower($term)
            RETURN l as node, 'Location' as type
            UNION
            MATCH (a:Account)
            WHERE toLower(a.username) CONTAINS toLower($term)
               OR toLower(a.full_name) CONTAINS toLower($term)
            RETURN a as node, 'Account' as type
            UNION
            MATCH (h:Hashtag)
            WHERE toLower(h.name) CONTAINS toLower($term)
            RETURN h as node, 'Hashtag' as type
            UNION
            MATCH (post:Post)
            WHERE toLower(post.caption) CONTAINS toLower($term)
            RETURN post as node, 'Post' as type
        }
        WITH node, type
        LIMIT $limit
        RETURN collect({
            id: coalesce(node.id, id(node)),
            label: coalesce(node.name, node.username, node.shortcode, 'Unknown'),
            type: type,
            properties: properties(node)
        }) as nodes
        """

        results = execute_query(query, {"term": search_term, "limit": limit})

        if not results:
            return GraphData(nodes=[], edges=[])

        nodes = [GraphNode(**_sanitize_node(n)) for n in results[0].get("nodes", [])]
        return GraphData(nodes=nodes, edges=[])

    def _search_persons(self, search_term: str, limit: int) -> GraphData:
        """Search for persons."""
        query = """
        MATCH (p:Person)
        WHERE toLower(p.name) CONTAINS toLower($term)
        RETURN collect({
            id: p.id,
            label: p.name,
            type: 'Person',
            properties: properties(p)
        }) as nodes
        LIMIT $limit
        """

        results = execute_query(query, {"term": search_term, "limit": limit})

        if not results:
            return GraphData(nodes=[], edges=[])

        nodes = [GraphNode(**_sanitize_node(n)) for n in results[0].get("nodes", [])]
        return GraphData(nodes=nodes, edges=[])

    def _search_locations(self, search_term: str, limit: int) -> GraphData:
        """Search for locations."""
        query = """
        MATCH (l:Location)
        WHERE toLower(l.name) CONTAINS toLower($term)
        RETURN collect({
            id: l.id,
            label: l.name,
            type: 'Location',
            properties: properties(l)
        }) as nodes
        LIMIT $limit
        """

        results = execute_query(query, {"term": search_term, "limit": limit})

        if not results:
            return GraphData(nodes=[], edges=[])

        nodes = [GraphNode(**_sanitize_node(n)) for n in results[0].get("nodes", [])]
        return GraphData(nodes=nodes, edges=[])

    def _search_captions(self, search_term: str, limit: int) -> GraphData:
        """Search in post captions using fulltext index."""
        query = """
        CALL db.index.fulltext.queryNodes('caption_search', $term)
        YIELD node, score
        WITH node, score
        ORDER BY score DESC
        LIMIT $limit
        RETURN collect({
            id: node.id,
            label: node.shortcode,
            type: 'Post',
            properties: properties(node)
        }) as nodes
        """

        try:
            results = execute_query(query, {"term": search_term, "limit": limit})
        except Exception:
            # Fallback if fulltext index fails
            return self._search_captions_fallback(search_term, limit)

        if not results:
            return GraphData(nodes=[], edges=[])

        nodes = [GraphNode(**_sanitize_node(n)) for n in results[0].get("nodes", [])]
        return GraphData(nodes=nodes, edges=[])

    def _search_captions_fallback(self, search_term: str, limit: int) -> GraphData:
        """Fallback caption search without fulltext index."""
        query = """
        MATCH (p:Post)
        WHERE toLower(p.caption) CONTAINS toLower($term)
        RETURN collect({
            id: p.id,
            label: p.shortcode,
            type: 'Post',
            properties: properties(p)
        }) as nodes
        LIMIT $limit
        """

        results = execute_query(query, {"term": search_term, "limit": limit})

        if not results:
            return GraphData(nodes=[], edges=[])

        nodes = [GraphNode(**_sanitize_node(n)) for n in results[0].get("nodes", [])]
        return GraphData(nodes=nodes, edges=[])

    def _search_hashtags(self, search_term: str, limit: int) -> GraphData:
        """Search for hashtags."""
        # Remove # if present
        term = search_term.lstrip("#")

        query = """
        MATCH (h:Hashtag)
        WHERE toLower(h.name) CONTAINS toLower($term)
        RETURN collect({
            id: h.id,
            label: h.name,
            type: 'Hashtag',
            properties: properties(h)
        }) as nodes
        LIMIT $limit
        """

        results = execute_query(query, {"term": term, "limit": limit})

        if not results:
            return GraphData(nodes=[], edges=[])

        nodes = [GraphNode(**_sanitize_node(n)) for n in results[0].get("nodes", [])]
        return GraphData(nodes=nodes, edges=[])

    def get_stats(self) -> StatsResponse:
        """Get database statistics."""
        # Get counts separately to handle empty collections gracefully
        stats = {
            "persons": 0,
            "posts": 0,
            "locations": 0,
            "accounts": 0,
            "hashtags": 0,
            "faces": 0,
        }

        queries = [
            ("persons", "MATCH (n:Person) RETURN count(n) as count"),
            ("posts", "MATCH (n:Post) RETURN count(n) as count"),
            ("locations", "MATCH (n:Location) RETURN count(n) as count"),
            ("accounts", "MATCH (n:Account) RETURN count(n) as count"),
            ("hashtags", "MATCH (n:Hashtag) RETURN count(n) as count"),
            ("faces", "MATCH (n:Face) RETURN count(n) as count"),
        ]

        for key, query in queries:
            try:
                results = execute_query(query)
                if results:
                    stats[key] = results[0]["count"]
            except Exception as e:
                logger.warning(f"Error getting {key} count: {e}")

        # Get recent posts
        recent_query = """
        MATCH (p:Post)
        OPTIONAL MATCH (f:Face)-[:APPEARS_IN]->(p)
        WITH p, count(f) as faces_detected
        RETURN p {.*, faces_detected: faces_detected} as post
        ORDER BY p.posted_at DESC
        LIMIT 10
        """

        recent_results = execute_query(recent_query)
        recent_posts = [
            Post(**r["post"]) for r in recent_results
            if r.get("post")
        ]

        return StatsResponse(
            total_persons=stats["persons"],
            total_posts=stats["posts"],
            total_locations=stats["locations"],
            total_accounts=stats["accounts"],
            total_hashtags=stats["hashtags"],
            total_faces_detected=stats["faces"],
            recent_posts=recent_posts,
        )

    def get_co_appearances(self, person_id: str) -> list[dict]:
        """Find people who appear in the same posts as a given person."""
        query = """
        MATCH (p:Person {id: $person_id})-[:APPEARS_IN]->(post:Post)<-[:APPEARS_IN]-(other:Person)
        WHERE other.id <> $person_id
        WITH other, count(post) as shared_posts
        ORDER BY shared_posts DESC
        RETURN {
            person_id: other.id,
            person_name: other.name,
            shared_posts: shared_posts
        } as co_appearance
        """

        results = execute_query(query, {"person_id": person_id})
        return [r["co_appearance"] for r in results]

    def get_person_locations(self, person_id: str) -> list[dict]:
        """Get all locations where a person has appeared."""
        query = """
        MATCH (p:Person {id: $person_id})-[:APPEARS_IN]->(post:Post)-[:AT_LOCATION]->(loc:Location)
        WITH loc, count(post) as visits, collect(post.posted_at) as visit_dates
        ORDER BY visits DESC
        RETURN {
            location_id: loc.id,
            location_name: loc.name,
            visit_count: visits,
            last_visit: visit_dates[0]
        } as location_data
        """

        results = execute_query(query, {"person_id": person_id})
        return [r["location_data"] for r in results]

    def get_timeline(self, person_id: str) -> list[dict]:
        """Get a timeline of a person's appearances."""
        query = """
        MATCH (p:Person {id: $person_id})-[:APPEARS_IN]->(post:Post)
        OPTIONAL MATCH (post)<-[:POSTED]-(account:Account)
        OPTIONAL MATCH (post)-[:AT_LOCATION]->(loc:Location)
        RETURN {
            post_id: post.id,
            shortcode: post.shortcode,
            caption: post.caption,
            posted_at: post.posted_at,
            location: loc.name,
            account: account.username
        } as timeline_item
        ORDER BY post.posted_at DESC
        """

        results = execute_query(query, {"person_id": person_id})
        return [r["timeline_item"] for r in results]


graph_service = GraphService()
