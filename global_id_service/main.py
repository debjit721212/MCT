"""
Global ID Microservice - main.py

Launches an asynchronous FastAPI app for handling identity assignment
in a multi-camera tracking (MCT) system. This service receives person ReID
embeddings from multiple DeepStream zone pipelines and assigns a consistent
global ID using Redis and Qdrant vector matching.

Scalable for 1000+ concurrent camera feeds.
"""

import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from global_id_service.redis_backend import RedisGlobalIDManager
from global_id_service.schemas import AssignIDRequest, AssignIDResponse

# ─────────────────────────────────────────────────────────────
# Logger Setup
# ─────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ─────────────────────────────────────────────────────────────
# FastAPI Initialization
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="Global ID Service",
    version="1.0",
    description="Assigns consistent global IDs across multiple zones and cameras",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────
# Identity Manager Initialization
# ─────────────────────────────────────────────────────────────
id_manager = RedisGlobalIDManager()

@app.on_event("startup")
async def startup_event():
    """Initialize backend connections (Redis, Qdrant, etc)."""
    logger.info("🚀 Starting Global ID Manager...")
    await id_manager.connect()

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanly shutdown backend connections."""
    logger.info("🛑 Shutting down Global ID Manager...")
    await id_manager.disconnect()

# ─────────────────────────────────────────────────────────────
# Endpoint: Assign Global ID
# ─────────────────────────────────────────────────────────────
@app.post("/assign_id", response_model=AssignIDResponse, summary="Assign Global ID")
async def assign_id(req: AssignIDRequest):
    """
    Endpoint to assign a consistent global ID to a detected person.

    - Accepts: cam_id, track_id, 512D embedding, timestamp
    - Returns: Global person ID
    """
    try:
        global_id = await id_manager.assign_global_id_async(
            cam_id=req.cam_id,
            track_id=req.track_id,
            embedding=req.embedding,
            timestamp=req.timestamp
        )
        return AssignIDResponse(global_id=global_id)
    except Exception as e:
        logger.exception("❌ Global ID assignment failed")
        raise HTTPException(status_code=500, detail=f"Global ID assignment failed: {e}")

# ─────────────────────────────────────────────────────────────
# Run Locally (Optional for dev)
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("global_id_service.main:app", host="0.0.0.0", port=8000, reload=True)
