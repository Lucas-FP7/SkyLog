from fastapi import APIRouter, Response, HTTPException
import json
import os
import httpx
import redis.asyncio as redis
from services import get_gst_events, process_and_publish, get_neo_feed, calculate_severity

router = APIRouter()
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

@router.get("/api/space-weather/current")
async def get_current_space_weather(response: Response):
    cache_key = "cache:donki:current"
    cached_data = await redis_client.get(cache_key)
    
    if cached_data:
        response.headers["X-Cache"] = "HIT"
        return json.loads(cached_data)
        
    response.headers["X-Cache"] = "MISS"
    
    try:
        gst_data = await get_gst_events()
        if not gst_data:
            return {"message": "No GST events found"}
        
        latest_event = gst_data[0]
        severity, emergency = calculate_severity(latest_event)
        
        result = {
            "event": latest_event,
            "classification": {
                "severityLevel": severity,
                "emergencyNotification": emergency
            }
        }
        
        await redis_client.setex(cache_key, 60, json.dumps(result))
        
        return result
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="NASA API Rate Limit (DEMO_KEY) excedido. Configure uma NASA_API_KEY no arquivo .env ou aguarde 1 hora.")
        raise HTTPException(status_code=502, detail=f"Erro na API da NASA: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/space-weather/ingest", status_code=202)
async def ingest_space_weather():
    try:
        payload = await process_and_publish()
        if payload:
            return {"message": "Ingestion accepted", "event_id": payload["event_id"]}
        return {"message": "No data to ingest"}
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="NASA API Rate Limit (DEMO_KEY) excedido. Configure uma NASA_API_KEY no arquivo .env ou aguarde 1 hora.")
        raise HTTPException(status_code=502, detail=f"Erro na API da NASA: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/neo/feed")
async def neo_feed(start_date: str, end_date: str):
    try:
        data = await get_neo_feed(start_date, end_date)
        return data
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="NASA API Rate Limit (DEMO_KEY) excedido. Configure uma NASA_API_KEY no arquivo .env ou aguarde 1 hora.")
        raise HTTPException(status_code=502, detail=f"Erro na API da NASA: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
