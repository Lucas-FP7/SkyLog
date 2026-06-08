from pydantic import BaseModel, Field
from typing import List, Optional, Any

class GSTEvent(BaseModel):
    gstID: str
    startTime: str
    allKpIndex: Optional[List[dict]] = None
    kpIndex: Optional[Any] = None

class Asteroid(BaseModel):
    id: str
    name: str
    is_potentially_hazardous_asteroid: bool

class AlertPayload(BaseModel):
    event_id: str
    severityLevel: str
    emergencyNotification: bool
    hazardous_asteroids_count: Optional[int] = None
    timestamp: str
