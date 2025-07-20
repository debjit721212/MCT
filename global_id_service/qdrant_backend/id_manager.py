"""
Global ID Manager - id_manager.py

Core logic to:
- Match incoming embeddings using Qdrant
- Assign new global IDs when needed
- Cache track_id ↔ global_id in Redis
"""

from typing import List, Optional
import logging
import json

from global_id_service.qdrant_backend.embedding_matcher import EmbeddingMatcher
from global_id_service.qdrant_backend.qdrant_client import QdrantClientWrapper
# from global_id_service.redis_backend import RedisCache
from global_id_service.cache_instance import redis_cache
from global_id_service.config import CACHE_TTL_SECONDS

logger = logging.getLogger(__name__)


class GlobalIDManager:
    def __init__(self):
        self.qdrant = QdrantClientWrapper()
        self.matcher = EmbeddingMatcher()
        self.cache = redis_cache#RedisCache()
        # self.cache.connect()

    def assign_global_id(self, cam_id: str, track_id: str, embedding: List[float], timestamp: float, zone: Optional[str] = None) -> int:
        try:
            # cache_key = f"{cam_id}:{track_id}"
            cache_key = f"global_id:{cam_id}:{track_id}"
            # print("cache_key:", cache_key)
            
            # STEP 0: Inspect Qdrant database
            # self.qdrant.debug_print_all_ids()

            # Step 1: Check cache
            # cached_id = self.cache.get(cache_key)
            # # print("[CHECK] Redis Cache Hit:", cached_id)
            # if cached_id is not None:
            #     logger.debug(f"Found cached global_id={cached_id} for {cache_key}")
            #     return int(cached_id)
            cached_value = self.cache.get(cache_key)
            if cached_value is not None:
                try:
                    # Case 1: direct int from Redis (old cache)
                    if isinstance(cached_value, int):
                        logger.debug(f"[REDIS HIT] Found legacy int global_id={cached_value} for {cache_key}")
                        return cached_value
                    # Case 2: valid JSON
                    if isinstance(cached_value, str) and cached_value.startswith("{"):
                        parsed = json.loads(cached_value)
                        global_id = parsed.get("global_id")
                        if global_id is not None:
                            logger.debug(f"[REDIS HIT] Found global_id={global_id} for {cache_key}")
                            return int(global_id)
                    logger.warning(f"[REDIS WARNING] Unexpected format for cached value: {cached_value}")
                except Exception as e:
                    logger.warning(f"[REDIS ERROR] Failed to parse cached value for {cache_key}: {e}")

            global_id = None
            # Step 2: Qdrant match
            global_id, score = self.matcher.find_best_match(
                embedding=embedding,
                zone_filter=zone,
                cam_id=cam_id
            )
            # print("[QDRANT MATCH] ID:", global_id, "Score:", score)

            # Step 3: Assign if needed
            if global_id is None:
                global_id = self.cache.increment_global_id()
                logger.info(f"[NEW ID] Assigned new global_id={global_id} for person")
            # print(f"[REDIS SET] Setting new ID: {cache_key} → {global_id}")
            # Step 4: Qdrant upsert
            metadata = {
                "cam_id": cam_id,
                "track_id": track_id,
                "zone": zone or "unknown",
                "timestamp": timestamp
            }
            self.qdrant.upsert_embedding(global_id, embedding, metadata)
            # print("[QDRANT UPSERT] Done for global_id:", global_id)

            # Step 5: Save to Redis
            # self.cache.set(cache_key, global_id, ttl=CACHE_TTL_SECONDS)
            self.cache.set(cache_key, json.dumps({
            "global_id": global_id,
            "camera_id": cam_id,
            "track_id": track_id,
            "zone": zone or "unknown",
            "timestamp": timestamp
            }), ttl=CACHE_TTL_SECONDS)
            # print("[REDIS SET] cache_key:", cache_key, "→", global_id)
            # NEW: Append this track ID to the global_id's history list
            self.cache.push_track_id(global_id, cam_id, track_id)
            logger.debug(f"[REDIS LOG] Added {cam_id}:{track_id} to history for global_id={global_id}")

            return int(global_id)

        except Exception as e:
            print("🔥 ERROR in assign_global_id:", e)