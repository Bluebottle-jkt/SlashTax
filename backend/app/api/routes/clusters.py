"""API routes for face clustering operations."""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel

from app.services.clustering_service import clustering_service

router = APIRouter(prefix="/clusters", tags=["clusters"])


class ClusterParams(BaseModel):
    """Parameters for clustering operation."""
    eps: Optional[float] = 0.5
    min_samples: Optional[int] = 2
    only_unassigned: bool = True


class LabelRequest(BaseModel):
    """Request to label a cluster."""
    label: str


class ConvertToPersonRequest(BaseModel):
    """Request to convert cluster to person."""
    name: str
    notes: Optional[str] = None


class MergeClustersRequest(BaseModel):
    """Request to merge multiple clusters."""
    cluster_ids: list[str]
    label: Optional[str] = None


@router.get("/")
async def list_clusters(skip: int = 0, limit: int = Query(50, le=200)):
    """List all face clusters."""
    return clustering_service.get_clusters(skip=skip, limit=limit)


@router.get("/stats")
async def get_cluster_stats():
    """Get clustering statistics."""
    return clustering_service.get_cluster_stats()


@router.get("/{cluster_id}")
async def get_cluster(cluster_id: str):
    """Get a specific cluster with all its faces."""
    cluster = clustering_service.get_cluster(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return cluster


@router.post("/recompute")
async def recompute_clusters(params: ClusterParams):
    """
    Recompute face clusters using DBSCAN algorithm.

    This will:
    1. Clear existing cluster relationships for affected faces
    2. Run DBSCAN clustering on face encodings
    3. Create new FaceCluster nodes and relationships

    Parameters:
    - eps: Maximum distance between samples (0.3-0.7 recommended, lower = stricter)
    - min_samples: Minimum faces to form a cluster (default 2)
    - only_unassigned: If true, only cluster faces not yet assigned to a Person
    """
    return clustering_service.cluster_faces(
        eps=params.eps,
        min_samples=params.min_samples,
        only_unassigned=params.only_unassigned
    )


@router.patch("/{cluster_id}/label")
async def label_cluster(cluster_id: str, request: LabelRequest):
    """Add or update a label for a cluster."""
    result = clustering_service.label_cluster(cluster_id, request.label)
    if not result:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return result


@router.post("/{cluster_id}/convert-to-person")
async def convert_cluster_to_person(cluster_id: str, request: ConvertToPersonRequest):
    """
    Convert a cluster to a Person node.

    All faces in the cluster will be linked to the new Person via BELONGS_TO relationship.
    The cluster node will be deleted after conversion.
    The Person's face_encoding will be the average of all cluster face encodings.
    """
    result = clustering_service.convert_cluster_to_person(
        cluster_id=cluster_id,
        name=request.name,
        notes=request.notes
    )
    if not result:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return result


@router.post("/merge")
async def merge_clusters(request: MergeClustersRequest):
    """
    Merge multiple clusters into one.

    The first cluster in the list will be the target (kept).
    All faces from other clusters will be moved to it.
    Other cluster nodes will be deleted.
    """
    if len(request.cluster_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 cluster IDs required for merge"
        )

    result = clustering_service.merge_clusters(
        cluster_ids=request.cluster_ids,
        new_label=request.label
    )

    if not result:
        raise HTTPException(status_code=404, detail="One or more clusters not found")

    return result


@router.delete("/{cluster_id}")
async def delete_cluster(cluster_id: str):
    """Delete a cluster (faces will become unclustered)."""
    from app.core.database import execute_write

    query = """
    MATCH (c:FaceCluster {id: $cluster_id})
    OPTIONAL MATCH (f:Face)-[r:IN_CLUSTER]->(c)
    DELETE r
    WITH c
    DELETE c
    RETURN count(c) as deleted
    """

    result = execute_write(query, {"cluster_id": cluster_id})

    if not result or result[0]["deleted"] == 0:
        raise HTTPException(status_code=404, detail="Cluster not found")

    return {"message": "Cluster deleted successfully"}
