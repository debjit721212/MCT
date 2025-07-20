"""
API Schemas - schemas.py

Defines the request and response models used by the Global ID FastAPI service.
Utilizes Pydantic for data validation and OpenAPI documentation.
"""

from pydantic import BaseModel, Field
from typing import List

class AssignIDRequest(BaseModel):
    """
    Request model for assigning a global ID.
    """
    cam_id: str = Field(..., description="Unique camera ID (e.g., 'camA')")
    track_id: str = Field(..., description="Track ID from DeepStream tracker")
    embedding: List[float] = Field(..., description="512D ReID vector embedding")
    timestamp: float = Field(..., description="Unix timestamp (float)")

class AssignIDResponse(BaseModel):
    """
    Response model with the assigned global ID.
    """
    global_id: int = Field(..., description="Assigned unique global ID")
