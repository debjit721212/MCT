"""
Qdrant Vector Database Client - qdrant_client.py

Handles vector upsert, similarity search, and metadata filtering
using Qdrant for global person re-identification.

This module wraps qdrant-client with async interface.
"""

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.models import Distance, VectorParams, PointStruct
from typing import List, Dict, Optional
import numpy as np
import uuid
import logging

from global_id_service.config import (
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_COLLECTION,
    QDRANT_VECTOR_SIZE,
    QDRANT_DISTANCE,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Distance mapping
# ─────────────────────────────────────────────────────────────
DISTANCE_MAP = {
    "Cosine": Distance.COSINE,
    "Dot": Distance.DOT,
    "Euclidean": Distance.EUCLID,
}


class QdrantClientWrapper:
    def __init__(self):
        """Initialize Qdrant client and connect."""
        self.client = QdrantClient(host="localhost", port=6333)#QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        self.collection_name = QDRANT_COLLECTION
        self.vector_size = QDRANT_VECTOR_SIZE
        self.distance = DISTANCE_MAP.get(QDRANT_DISTANCE, Distance.COSINE)

        logger.info(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")
        self._ensure_collection()

    def _ensure_collection(self):
        """Create collection if not exists with required parameters."""
        collections = self.client.get_collections().collections
        if self.collection_name not in [c.name for c in collections]:
            logger.info(f"Creating Qdrant collection: {self.collection_name}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=self.distance
                )
            )

    def upsert_embedding(
        self,
        global_id: int,
        embedding: List[float],
        metadata: Dict
    ) -> None:
        """Insert or update a vector with associated metadata."""
        point = PointStruct(
            id=global_id,
            vector=embedding,
            payload=metadata
        )
        self.client.upsert(collection_name=self.collection_name, points=[point])
        logger.debug(f"Upserted embedding for ID {global_id} with metadata: {metadata}")

    def search_similar(
        self,
        embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> List[qmodels.ScoredPoint]:
        """
        Search for top-k similar embeddings in Qdrant.
        
        :param embedding: 512-D vector
        :param top_k: Number of results
        :param filters: Optional metadata filters (Qdrant filter DSL)
        :return: List of ScoredPoint results
        """
        query_filter = self._build_filter(filters) if filters else None

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=embedding,
            limit=top_k,
            with_payload=True,
            score_threshold=None,
            query_filter=query_filter
        )
        return results

    def _build_filter(self, metadata: Dict) -> qmodels.Filter:
        """
        Build a Qdrant filter object from metadata dict.
        E.g. { "zone": "zone1", "cam_id": "camA" }
        """
        return qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key=key,
                    match=qmodels.MatchValue(value=value)
                )
                for key, value in metadata.items()
            ]
        )
    
    def debug_print_all_ids(self):
        result = self.client.scroll(
            collection_name=self.collection_name,
            limit=100,
        )
        print("==== Qdrant Global IDs in Collection ====")
        for point in result[0]:
            print("ID:", point.id)
