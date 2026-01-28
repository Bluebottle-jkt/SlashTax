"""Face clustering service using DBSCAN algorithm."""
import logging
import uuid
from typing import Optional
from datetime import datetime

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import normalize

from app.core.database import execute_query, execute_write

logger = logging.getLogger(__name__)


class ClusteringService:
    """Service for clustering faces using DBSCAN algorithm."""

    def __init__(self, eps: float = 0.5, min_samples: int = 2):
        """
        Initialize clustering service.

        Args:
            eps: Maximum distance between two samples to be in same neighborhood.
                 Lower values = stricter clustering (fewer faces per cluster).
            min_samples: Minimum samples in a neighborhood to form a cluster.
        """
        self.eps = eps
        self.min_samples = min_samples

    def get_all_face_encodings(self) -> tuple[list[str], np.ndarray]:
        """
        Fetch all face encodings from Neo4j.

        Returns:
            Tuple of (face_ids, encodings_array)
        """
        query = """
        MATCH (f:Face)
        WHERE f.encoding IS NOT NULL
        RETURN f.id as face_id, f.encoding as encoding
        """

        results = execute_query(query)

        if not results:
            return [], np.array([])

        face_ids = []
        encodings = []

        for record in results:
            face_ids.append(record["face_id"])
            encodings.append(record["encoding"])

        return face_ids, np.array(encodings)

    def get_unassigned_face_encodings(self) -> tuple[list[str], np.ndarray]:
        """
        Fetch face encodings that are not yet assigned to a person.

        Returns:
            Tuple of (face_ids, encodings_array)
        """
        query = """
        MATCH (f:Face)
        WHERE f.encoding IS NOT NULL
        AND NOT (f)-[:BELONGS_TO]->(:Person)
        RETURN f.id as face_id, f.encoding as encoding
        """

        results = execute_query(query)

        if not results:
            return [], np.array([])

        face_ids = []
        encodings = []

        for record in results:
            face_ids.append(record["face_id"])
            encodings.append(record["encoding"])

        return face_ids, np.array(encodings)

    def cluster_faces(
        self,
        eps: Optional[float] = None,
        min_samples: Optional[int] = None,
        only_unassigned: bool = True
    ) -> dict:
        """
        Cluster faces using DBSCAN algorithm.

        Args:
            eps: Override default eps value
            min_samples: Override default min_samples value
            only_unassigned: If True, only cluster faces not assigned to a Person

        Returns:
            Dict with clustering results and statistics
        """
        eps = eps or self.eps
        min_samples = min_samples or self.min_samples

        # Get face encodings
        if only_unassigned:
            face_ids, encodings = self.get_unassigned_face_encodings()
        else:
            face_ids, encodings = self.get_all_face_encodings()

        if len(face_ids) == 0:
            return {
                "total_faces": 0,
                "clusters_created": 0,
                "noise_faces": 0,
                "clusters": []
            }

        logger.info(f"Clustering {len(face_ids)} faces with eps={eps}, min_samples={min_samples}")

        # Normalize encodings for cosine distance approximation
        # DBSCAN with euclidean on normalized vectors approximates cosine distance
        normalized_encodings = normalize(encodings)

        # Run DBSCAN
        clustering = DBSCAN(eps=eps, min_samples=min_samples, metric='euclidean')
        labels = clustering.fit_predict(normalized_encodings)

        # Process results
        unique_labels = set(labels)
        n_clusters = len(unique_labels) - (1 if -1 in unique_labels else 0)
        n_noise = list(labels).count(-1)

        logger.info(f"Found {n_clusters} clusters, {n_noise} noise faces")

        # Clear existing cluster relationships for these faces
        self._clear_face_clusters(face_ids)

        # Create cluster nodes and relationships
        clusters_info = []
        for cluster_label in unique_labels:
            if cluster_label == -1:
                continue  # Skip noise

            # Get faces in this cluster
            cluster_face_indices = np.where(labels == cluster_label)[0]
            cluster_face_ids = [face_ids[i] for i in cluster_face_indices]

            # Create cluster node
            cluster_id = str(uuid.uuid4())
            cluster_info = self._create_cluster(cluster_id, cluster_face_ids)
            clusters_info.append(cluster_info)

        return {
            "total_faces": len(face_ids),
            "clusters_created": n_clusters,
            "noise_faces": n_noise,
            "eps_used": eps,
            "min_samples_used": min_samples,
            "clusters": clusters_info
        }

    def _clear_face_clusters(self, face_ids: list[str]) -> None:
        """Remove existing cluster relationships for given faces."""
        if not face_ids:
            return

        query = """
        MATCH (f:Face)-[r:IN_CLUSTER]->(c:FaceCluster)
        WHERE f.id IN $face_ids
        DELETE r
        WITH c
        WHERE NOT (c)<-[:IN_CLUSTER]-()
        DELETE c
        """

        execute_write(query, {"face_ids": face_ids})

    def _create_cluster(self, cluster_id: str, face_ids: list[str]) -> dict:
        """Create a FaceCluster node and link faces to it."""
        query = """
        CREATE (c:FaceCluster {
            id: $cluster_id,
            created_at: datetime(),
            face_count: $face_count
        })
        WITH c
        UNWIND $face_ids as face_id
        MATCH (f:Face {id: face_id})
        MERGE (f)-[:IN_CLUSTER]->(c)
        RETURN c.id as id, c.face_count as face_count
        """

        result = execute_write(query, {
            "cluster_id": cluster_id,
            "face_ids": face_ids,
            "face_count": len(face_ids)
        })

        return {
            "cluster_id": cluster_id,
            "face_count": len(face_ids),
            "face_ids": face_ids
        }

    def get_clusters(self, skip: int = 0, limit: int = 50) -> list[dict]:
        """Get all face clusters with their faces."""
        query = """
        MATCH (c:FaceCluster)
        OPTIONAL MATCH (f:Face)-[:IN_CLUSTER]->(c)
        WITH c, collect({
            id: f.id,
            crop_path: f.crop_path,
            post_id: f.post_id
        }) as faces
        RETURN {
            id: c.id,
            label: c.label,
            created_at: c.created_at,
            face_count: size(faces),
            faces: faces
        } as cluster
        ORDER BY size(faces) DESC
        SKIP $skip
        LIMIT $limit
        """

        results = execute_query(query, {"skip": skip, "limit": limit})
        return [r["cluster"] for r in results]

    def get_cluster(self, cluster_id: str) -> Optional[dict]:
        """Get a single cluster with all its faces."""
        query = """
        MATCH (c:FaceCluster {id: $cluster_id})
        OPTIONAL MATCH (f:Face)-[:IN_CLUSTER]->(c)
        OPTIONAL MATCH (f)-[:APPEARS_IN]->(p:Post)
        WITH c, collect({
            id: f.id,
            crop_path: f.crop_path,
            post_id: p.id,
            post_shortcode: p.shortcode
        }) as faces
        RETURN {
            id: c.id,
            label: c.label,
            created_at: c.created_at,
            face_count: size(faces),
            faces: faces
        } as cluster
        """

        results = execute_query(query, {"cluster_id": cluster_id})

        if not results:
            return None

        return results[0]["cluster"]

    def label_cluster(self, cluster_id: str, label: str) -> Optional[dict]:
        """
        Add a label to a cluster (for manual identification).

        Args:
            cluster_id: The cluster to label
            label: Human-readable label for the cluster

        Returns:
            Updated cluster info or None if not found
        """
        query = """
        MATCH (c:FaceCluster {id: $cluster_id})
        SET c.label = $label, c.updated_at = datetime()
        RETURN {
            id: c.id,
            label: c.label,
            updated_at: c.updated_at
        } as cluster
        """

        results = execute_write(query, {"cluster_id": cluster_id, "label": label})

        if not results:
            return None

        return results[0]["cluster"]

    def convert_cluster_to_person(self, cluster_id: str, name: str, notes: Optional[str] = None) -> Optional[dict]:
        """
        Convert a cluster to a Person node.

        All faces in the cluster will be linked to the new Person.
        The cluster is deleted after conversion.

        Args:
            cluster_id: The cluster to convert
            name: Name for the new Person
            notes: Optional notes about the person

        Returns:
            The created Person or None if cluster not found
        """
        # First check the cluster exists and get faces
        cluster = self.get_cluster(cluster_id)
        if not cluster:
            return None

        person_id = str(uuid.uuid4())

        # Get average encoding for the person from cluster faces
        query = """
        MATCH (f:Face)-[:IN_CLUSTER]->(c:FaceCluster {id: $cluster_id})
        RETURN collect(f.encoding) as encodings
        """

        results = execute_query(query, {"cluster_id": cluster_id})

        if results and results[0]["encodings"]:
            encodings = np.array(results[0]["encodings"])
            avg_encoding = np.mean(encodings, axis=0).tolist()
        else:
            avg_encoding = None

        # Create person and link all faces
        create_query = """
        CREATE (p:Person {
            id: $person_id,
            name: $name,
            notes: $notes,
            face_encoding: $encoding,
            created_at: datetime()
        })
        WITH p
        MATCH (f:Face)-[:IN_CLUSTER]->(c:FaceCluster {id: $cluster_id})
        MERGE (f)-[:BELONGS_TO]->(p)
        WITH p, c, collect(f) as faces
        DETACH DELETE c
        RETURN {
            id: p.id,
            name: p.name,
            notes: p.notes,
            face_count: size(faces)
        } as person
        """

        results = execute_write(create_query, {
            "person_id": person_id,
            "name": name,
            "notes": notes,
            "encoding": avg_encoding,
            "cluster_id": cluster_id
        })

        if not results:
            return None

        return results[0]["person"]

    def merge_clusters(self, cluster_ids: list[str], new_label: Optional[str] = None) -> Optional[dict]:
        """
        Merge multiple clusters into one.

        Args:
            cluster_ids: List of cluster IDs to merge
            new_label: Optional label for the merged cluster

        Returns:
            The merged cluster info or None if failed
        """
        if len(cluster_ids) < 2:
            return None

        # Use first cluster as the target
        target_id = cluster_ids[0]
        source_ids = cluster_ids[1:]

        query = """
        MATCH (target:FaceCluster {id: $target_id})
        WITH target
        UNWIND $source_ids as source_id
        MATCH (f:Face)-[r:IN_CLUSTER]->(source:FaceCluster {id: source_id})
        DELETE r
        MERGE (f)-[:IN_CLUSTER]->(target)
        WITH target, source
        DETACH DELETE source
        WITH DISTINCT target
        SET target.updated_at = datetime()
        SET target.label = CASE WHEN $label IS NOT NULL THEN $label ELSE target.label END
        WITH target
        MATCH (f:Face)-[:IN_CLUSTER]->(target)
        SET target.face_count = count(f)
        RETURN {
            id: target.id,
            label: target.label,
            face_count: target.face_count
        } as cluster
        """

        results = execute_write(query, {
            "target_id": target_id,
            "source_ids": source_ids,
            "label": new_label
        })

        if not results:
            return None

        return results[0]["cluster"]

    def get_cluster_stats(self) -> dict:
        """Get statistics about current clustering state."""
        # Run separate queries to avoid Neo4j aggregation issues
        stats = {
            "total_clusters": 0,
            "clustered_faces": 0,
            "unclustered_faces": 0,
            "assigned_to_person": 0
        }

        queries = [
            ("total_clusters", "MATCH (c:FaceCluster) RETURN count(c) as count"),
            ("clustered_faces", "MATCH (f:Face)-[:IN_CLUSTER]->(:FaceCluster) RETURN count(f) as count"),
            ("unclustered_faces", "MATCH (f:Face) WHERE NOT (f)-[:IN_CLUSTER]->(:FaceCluster) RETURN count(f) as count"),
            ("assigned_to_person", "MATCH (f:Face)-[:BELONGS_TO]->(:Person) RETURN count(f) as count"),
        ]

        for key, query in queries:
            try:
                results = execute_query(query)
                if results:
                    stats[key] = results[0]["count"]
            except Exception as e:
                logger.warning(f"Error getting {key}: {e}")

        return stats


# Singleton instance
clustering_service = ClusteringService()
