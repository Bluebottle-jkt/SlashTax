from fastapi import APIRouter, Query
from typing import Optional

from app.schemas.models import GraphData, SearchQuery, StatsResponse
from app.services.graph_service import graph_service

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/", response_model=GraphData)
async def get_full_graph(limit: int = Query(500, le=1000)):
    """Get the full graph for visualization."""
    return graph_service.get_full_graph(limit)


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get database statistics."""
    return graph_service.get_stats()


@router.post("/search", response_model=GraphData)
async def search_graph(query: SearchQuery):
    """Search the graph."""
    return graph_service.search(query)


@router.get("/search", response_model=GraphData)
async def search_graph_get(
    q: str = Query(..., min_length=1),
    type: str = Query("all", regex="^(all|person|location|caption|hashtag)$"),
    limit: int = Query(50, le=200),
):
    """Search the graph (GET endpoint)."""
    query = SearchQuery(query=q, search_type=type, limit=limit)
    return graph_service.search(query)


@router.get("/locations")
async def list_locations(skip: int = 0, limit: int = 100):
    """List all locations."""
    from app.core.database import execute_query

    query = """
    MATCH (l:Location)
    OPTIONAL MATCH (p:Post)-[:AT_LOCATION]->(l)
    WITH l, count(p) as post_count
    RETURN {
        id: l.id,
        name: l.name,
        latitude: l.latitude,
        longitude: l.longitude,
        post_count: post_count
    } as location
    ORDER BY post_count DESC
    SKIP $skip
    LIMIT $limit
    """

    results = execute_query(query, {"skip": skip, "limit": limit})
    return [r["location"] for r in results]


@router.get("/hashtags")
async def list_hashtags(skip: int = 0, limit: int = 100):
    """List all hashtags."""
    from app.core.database import execute_query

    query = """
    MATCH (h:Hashtag)
    OPTIONAL MATCH (p:Post)-[:HAS_HASHTAG]->(h)
    WITH h, count(p) as post_count
    RETURN {
        id: h.id,
        name: h.name,
        post_count: post_count
    } as hashtag
    ORDER BY post_count DESC
    SKIP $skip
    LIMIT $limit
    """

    results = execute_query(query, {"skip": skip, "limit": limit})
    return [r["hashtag"] for r in results]


@router.get("/accounts")
async def list_accounts(skip: int = 0, limit: int = 100):
    """List all Instagram accounts."""
    from app.core.database import execute_query

    query = """
    MATCH (a:Account)
    OPTIONAL MATCH (a)-[:POSTED]->(p:Post)
    WITH a, count(p) as local_post_count
    RETURN {
        id: a.id,
        username: a.username,
        full_name: a.full_name,
        profile_pic_url: a.profile_pic_url,
        followers: a.followers,
        local_post_count: local_post_count
    } as account
    ORDER BY local_post_count DESC
    SKIP $skip
    LIMIT $limit
    """

    results = execute_query(query, {"skip": skip, "limit": limit})
    return [r["account"] for r in results]


@router.get("/connections")
async def get_all_connections():
    """Get all connections/relationships in the graph."""
    from app.core.database import execute_query

    query = """
    MATCH (n)-[r]->(m)
    WITH type(r) as rel_type, count(r) as count
    RETURN {
        relationship: rel_type,
        count: count
    } as connection
    ORDER BY count DESC
    """

    results = execute_query(query)
    return [r["connection"] for r in results]


@router.get("/paths/{start_id}/{end_id}")
async def find_paths(
    start_id: str,
    end_id: str,
    max_depth: int = Query(5, le=10),
):
    """Find paths between two nodes."""
    from app.core.database import execute_query

    query = """
    MATCH (start {id: $start_id}), (end {id: $end_id})
    MATCH path = shortestPath((start)-[*..%d]-(end))
    RETURN [node IN nodes(path) | {
        id: coalesce(node.id, id(node)),
        label: coalesce(node.name, node.username, node.shortcode),
        type: labels(node)[0]
    }] as nodes,
    [rel IN relationships(path) | {
        type: type(rel),
        source: coalesce(startNode(rel).id, id(startNode(rel))),
        target: coalesce(endNode(rel).id, id(endNode(rel)))
    }] as edges
    LIMIT 5
    """ % max_depth

    results = execute_query(query, {"start_id": start_id, "end_id": end_id})

    if not results:
        return {"paths": [], "message": "No paths found"}

    return {"paths": results}


@router.get("/clusters")
async def get_clusters():
    """Get clusters of connected persons."""
    from app.core.database import execute_query

    query = """
    MATCH (p1:Person)-[:APPEARS_IN]->(post:Post)<-[:APPEARS_IN]-(p2:Person)
    WHERE p1.id < p2.id
    WITH p1, p2, count(post) as shared_posts
    WHERE shared_posts >= 2
    RETURN {
        person1: { id: p1.id, name: p1.name },
        person2: { id: p2.id, name: p2.name },
        shared_posts: shared_posts
    } as cluster
    ORDER BY shared_posts DESC
    LIMIT 50
    """

    results = execute_query(query)
    return [r["cluster"] for r in results]


@router.get("/timeline")
async def get_timeline(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(100, le=500),
):
    """Get a timeline of posts."""
    from app.core.database import execute_query

    conditions = []
    params = {"limit": limit}

    if start_date:
        conditions.append("p.posted_at >= datetime($start_date)")
        params["start_date"] = start_date

    if end_date:
        conditions.append("p.posted_at <= datetime($end_date)")
        params["end_date"] = end_date

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
    MATCH (p:Post)
    {where_clause}
    OPTIONAL MATCH (a:Account)-[:POSTED]->(p)
    OPTIONAL MATCH (p)-[:AT_LOCATION]->(l:Location)
    OPTIONAL MATCH (person:Person)-[:APPEARS_IN]->(p)
    WITH p, a, l, collect(DISTINCT person.name) as persons
    RETURN {{
        post_id: p.id,
        shortcode: p.shortcode,
        caption: left(p.caption, 100),
        posted_at: p.posted_at,
        account: a.username,
        location: l.name,
        persons: persons
    }} as timeline_item
    ORDER BY p.posted_at DESC
    LIMIT $limit
    """

    results = execute_query(query, params)
    return [r["timeline_item"] for r in results]
