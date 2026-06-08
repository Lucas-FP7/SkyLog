import asyncio
import logging
import json
import os
import aio_pika
import redis.asyncio as redis

logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

async def process_alert(payload: dict):
    logger.warning(f"🚨 EMERGENCY NOTIFICATION TRIGGERED 🚨")
    logger.warning(f"Event ID: {payload.get('event_id')}")
    logger.warning(f"Severity: {payload.get('severityLevel')}")
    logger.warning(f"Hazardous Asteroids nearby: {payload.get('hazardous_asteroids_count')}")

async def consume_alerts():
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    
    while True:
        try:
            connection = await aio_pika.connect_robust(RABBITMQ_URL)
            break
        except Exception as e:
            logger.info(f"Waiting for RabbitMQ... {e}")
            await asyncio.sleep(2)
            
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        
        exchange = await channel.declare_exchange("space.events", aio_pika.ExchangeType.TOPIC)
        
        queue = await channel.declare_queue("notifier.alerts", durable=True)
        await queue.bind(exchange, routing_key="space.weather.alert")
        
        logger.info("Waiting for alerts on notifier.alerts queue...")
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process(ignore_processed=True):
                    try:
                        payload = json.loads(message.body.decode())
                        event_id = payload.get("event_id")
                        
                        if not event_id:
                            logger.error("Message missing event_id. Discarding.")
                            await message.ack()
                            continue
                        
                        idem_key = f"idem:notifier:{event_id}"
                        is_new = await redis_client.set(idem_key, "1", nx=True, ex=86400)
                        
                        if not is_new:
                            logger.info(f"Duplicate event ignored (Idempotency): {event_id}")
                            await message.ack()
                            continue
                            
                        if payload.get("severityLevel") == "severe" or payload.get("emergencyNotification"):
                            await process_alert(payload)
                        else:
                            logger.info(f"Non-severe event processed: {event_id}")
                            
                        await message.ack()
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
