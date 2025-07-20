"""
App Configuration - config.py

Centralized config for Global ID Service.
Loads thresholds, Qdrant/Redis URLs, collection names, etc.
"""

import os
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# ─────────────────────────────────────────────────────────────
# Redis Config
# ─────────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ─────────────────────────────────────────────────────────────
# Qdrant Config
# ─────────────────────────────────────────────────────────────
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "global_id_embeddings")
QDRANT_VECTOR_SIZE = int(os.getenv("QDRANT_VECTOR_SIZE", 256))
QDRANT_DISTANCE = os.getenv("QDRANT_DISTANCE", "Cosine")  # or "Dot", "Euclidean"

# ─────────────────────────────────────────────────────────────
# Global ID Config
# ─────────────────────────────────────────────────────────────
EMBEDDING_MATCH_THRESHOLD = float(os.getenv("EMBEDDING_MATCH_THRESHOLD", 0.90))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", 3600))  # Redis mapping ttl

# ─────────────────────────────────────────────────────────────
# Service Config
# ─────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
SERVICE_NAME = os.getenv("SERVICE_NAME", "GlobalIDManager")
