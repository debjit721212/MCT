# global_id_service/redis_backend.py

import redis
import logging
from global_id_service.config import REDIS_URL

logger = logging.getLogger(__name__)

class RedisCache:
    def __init__(self):
        self.redis_url = REDIS_URL
        self.redis = None
        self.id_counter_key = "global_id_counter"

    def connect(self):
        self.redis = redis.Redis.from_url(self.redis_url, decode_responses=True)
        logger.info("Connected to Redis")

    def disconnect(self):
        if self.redis:
            self.redis.close()
            logger.info("Redis connection closed")

    # def get(self, key: str):
    #     val = self.redis.get(key)
    #     # print(f"[REDIS GET] {key} → {val}")
    #     return int(val) if val else None
    
    def get(self, key: str):
        val = self.redis.get(key)
        if val is None:
            return None
        try:
            # If it's an integer string (legacy format), return as int
            if val.isdigit():
                return int(val)
            # Otherwise, assume it's a JSON string
            return val  # leave parsing to calling function
        except Exception as e:
            logger.warning(f"[REDIS GET ERROR] key={key} val={val} error={e}")
            return None

    # def set(self, key: str, value, ttl: int = 3600):
    #     # print(f"[REDIS SET] {key} → {value} (TTL={ttl}s)")
    #     self.redis.set(key, value, ex=ttl)
    
    def set(self, key: str, value, ttl: int = 3600):
        if isinstance(value, dict):
            value = json.dumps(value)
        self.redis.set(key, value, ex=ttl)
    
    def push_track_id(self, global_id: int, cam_id: str, track_id: str):
        key = f"track_ids:{global_id}"
        value = f"{cam_id}:{track_id}"
        self.redis.rpush(key, value)
    
    def get_all_track_ids(self, global_id: int) -> list:
        key = f"track_ids:{global_id}"
        return self.redis.lrange(key, 0, -1)

    def increment_global_id(self) -> int:
        new_id = self.redis.incr(self.id_counter_key)
        # print(f"[REDIS INCR] New global_id: {new_id}")
        return new_id
