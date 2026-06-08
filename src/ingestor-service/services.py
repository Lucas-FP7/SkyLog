import httpx
import json
import logging
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception
from datetime import datetime, timedelta
import os
import aio_pika

logger = logging.getLogger(__name__)

NASA_API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

class TransientError(Exception):
    pass

def is_transient_error(e):
    if isinstance(e, httpx.HTTPStatusError):
        # Retry ONLY on 5xx errors (server errors).
        # A 429 from NASA means quota exhausted (hourly or daily), so retrying immediately is useless.
        return e.response.status_code >= 500
    if isinstance(e, httpx.RequestError):
        return True
    return False

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception(is_transient_error),
    reraise=True
)
async def fetch_nasa_data(client: httpx.AsyncClient, url: str, params: dict = None):
    if params is None:
        params = {}
    params['api_key'] = NASA_API_KEY
    response = await client.get(url, params=params, timeout=10.0)
    
    response.raise_for_status()
    return response.json()

async def get_gst_events():
    url = "https://api.nasa.gov/DONKI/GST"
    async with httpx.AsyncClient() as client:
        return await fetch_nasa_data(client, url)

async def get_neo_feed(start_date: str, end_date: str):
    url = "https://api.nasa.gov/neo/rest/v1/feed"
    params = {"start_date": start_date, "end_date": end_date}
    async with httpx.AsyncClient() as client:
        return await fetch_nasa_data(client, url, params)

def calculate_severity(gst_event: dict):
    kp = 0
    if "kpIndex" in gst_event and gst_event["kpIndex"] is not None:
        try:
            kp = float(gst_event["kpIndex"])
        except ValueError:
            pass
    elif "allKpIndex" in gst_event and gst_event["allKpIndex"]:
        kps = []
        for item in gst_event["allKpIndex"]:
            if "kpIndex" in item and item["kpIndex"] is not None:
                try:
                    kps.append(float(item["kpIndex"]))
                except ValueError:
                    pass
        if kps:
            kp = max(kps)
    
    severity_level = "low"
    emergency_notification = False

    if kp <= 4:
        severity_level = "low"
        emergency_notification = False
    elif 5 <= kp <= 7:
        severity_level = "moderate"
        emergency_notification = False
    elif kp >= 8:
        severity_level = "severe"
        emergency_notification = True
        
    return severity_level, emergency_notification

async def process_and_publish():

    gst_data = await get_gst_events()
    if not gst_data:
        return None
    
    latest_event = gst_data[0]
    gst_id = latest_event.get("gstID", "unknown")
    start_time_str = latest_event.get("startTime")
    
    severity_level, emergency_notification = calculate_severity(latest_event)
    
    hazardous_asteroids_count = None
    
    if emergency_notification and start_time_str:
        try:
            date_str = start_time_str.split("T")[0]
            event_date = datetime.strptime(date_str, "%Y-%m-%d")
            start_date = (event_date - timedelta(days=1)).strftime("%Y-%m-%d")
            end_date = (event_date + timedelta(days=1)).strftime("%Y-%m-%d")
            
            neo_data = await get_neo_feed(start_date, end_date)
            
            count = 0
            if "near_earth_objects" in neo_data:
                for date_key, asteroids in neo_data["near_earth_objects"].items():
                    for ast in asteroids:
                        if ast.get("is_potentially_hazardous_asteroid"):
                            count += 1
            hazardous_asteroids_count = count
        except Exception as e:
            logger.error(f"Error enriching NEO data: {e}")
            
    payload = {
        "event_id": gst_id,
        "severityLevel": severity_level,
        "emergencyNotification": emergency_notification,
        "hazardous_asteroids_count": hazardous_asteroids_count,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await publish_alert(payload)
    return payload

async def publish_alert(payload: dict):
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("space.events", aio_pika.ExchangeType.TOPIC)
        
        message_body = json.dumps(payload).encode()
        message = aio_pika.Message(
            body=message_body,
            headers={
                "x-event-id": payload["event_id"],
                "message_id": payload["event_id"]
            }
        )
        
        await exchange.publish(message, routing_key="space.weather.alert")
