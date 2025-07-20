"""
Embedding Matcher - embedding_matcher.py

Encapsulates logic to:
- Search top-k vectors from Qdrant
- Apply cosine similarity threshold
- Return best-matching global ID (if any)

Used by GlobalIDManager to assign consistent IDs.
"""

from typing import List, Optional, Tuple
from global_id_service.qdrant_backend.qdrant_client import QdrantClientWrapper
from global_id_service.config import EMBEDDING_MATCH_THRESHOLD
import logging

logger = logging.getLogger(__name__)


class EmbeddingMatcher:
    def __init__(self):
        self.qdrant = QdrantClientWrapper()
    
    
    def find_best_match(
    self,
    embedding: List[float],
    zone_filter: Optional[str] = None,
    cam_id: Optional[str] = None
    ) -> Tuple[Optional[int], Optional[float]]:
        """
        Find best matching global ID above threshold.
        """
        filters = {}
        if zone_filter:
            filters["zone"] = zone_filter
        if cam_id:
            filters["cam_id"] = cam_id

        results = self.qdrant.search_similar(
            embedding=embedding,
            top_k=5,
            filters=filters
        )

        if not results:
            logger.debug("No similar vectors found")
            return None, None

        print("🔍 Qdrant Search Results:")
        for r in results:
            print(f"ID: {r.id}, Score: {r.score:.6f}")

        best = results[0]
        score = best.score
        global_id = best.id

        # ✅ Match status print (add this block)
        if score >= EMBEDDING_MATCH_THRESHOLD:
            print(f"[✅ QDRANT MATCH] ID: {global_id} Score: {score:.6f} >= Threshold: {EMBEDDING_MATCH_THRESHOLD}")
            logger.debug(f"✔ Match found: global_id={global_id} with score={score:.4f}")
            return global_id, score
        else:
            print(f"[❌ NEW ID] Best score = {score:.6f} < Threshold: {EMBEDDING_MATCH_THRESHOLD}")
            logger.debug(f"✘ No match above threshold (best={score:.4f})")
            return None, None

    # def find_best_match(
    #     self,
    #     embedding: List[float],
    #     zone_filter: Optional[str] = None,
    #     cam_id: Optional[str] = None
    # ) -> Tuple[Optional[int], Optional[float]]:
    #     """
    #     Find best matching global ID above threshold.

    #     Args:
    #         embedding (List[float]): 512-dim input vector
    #         zone_filter (str): Optional zone restriction
    #         cam_id (str): Optional camera filter

    #     Returns:
    #         (global_id, similarity_score) or (None, None) if no match
    #     """
    #     filters = {}
    #     if zone_filter:
    #         filters["zone"] = zone_filter
    #     if cam_id:
    #         filters["cam_id"] = cam_id

    #     results = self.qdrant.search_similar(
    #         embedding=embedding,
    #         top_k=5,
    #         filters=filters
    #     )

    #     if not results:
    #         logger.debug("No similar vectors found")
    #         return None, None
    #     print("🔍 Qdrant Search Results:")
    #     for r in results:
    #         print(f"ID: {r.id}, Score: {r.score:.6f}")
    #     best = results[0]
    #     score = best.score
    #     global_id = best.id

    #     if score >= EMBEDDING_MATCH_THRESHOLD:
    #         logger.debug(f"✔ Match found: global_id={global_id} with score={score:.4f}")
    #         return global_id, score
    #     else:
    #         logger.debug(f"✘ No match above threshold (best={score:.4f})")
    #         return None, None
