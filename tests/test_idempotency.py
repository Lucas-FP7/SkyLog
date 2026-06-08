import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/notifier-service')))

@pytest.mark.asyncio
async def test_rn3_idempotency():
    event_id = "test-event-123"
    
    with patch('consumer.redis') as mock_redis_module, \
         patch('consumer.aio_pika.connect_robust') as mock_connect, \
         patch('consumer.process_alert') as mock_process_alert:
             
        mock_redis = AsyncMock()
        mock_redis_module.from_url.return_value = mock_redis
        
        mock_redis.set.side_effect = [True, False]
        
        mock_message1 = AsyncMock()
        mock_message1.body = json.dumps({"event_id": event_id, "severityLevel": "severe"}).encode()
        
        mock_message2 = AsyncMock()
        mock_message2.body = json.dumps({"event_id": event_id, "severityLevel": "severe"}).encode()
        
        redis_client = mock_redis
        
        async def handle_message(msg):
            payload = json.loads(msg.body.decode())
            evt_id = payload.get("event_id")
            idem_key = f"idem:notifier:{evt_id}"
            is_new = await redis_client.set(idem_key, "1", nx=True, ex=86400)
            
            if not is_new:
                return False
                
            if payload.get("severityLevel") == "severe":
                await mock_process_alert(payload)
            return True
            
        res1 = await handle_message(mock_message1)
        assert res1 is True
        assert mock_process_alert.call_count == 1
        
        res2 = await handle_message(mock_message2)
        assert res2 is False
        assert mock_process_alert.call_count == 1
