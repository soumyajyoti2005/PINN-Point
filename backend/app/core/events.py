import redis.asyncio as redis
import json
from app.config import settings

redis_client = redis.from_url(f"redis://{settings.redis_host}:{settings.redis_port}/0")

async def publish_event(event_data: dict):
    await redis_client.publish(settings.redis_channel, json.dumps(event_data))

async def check_redis():
    try:
        return await redis_client.ping()
    except Exception:
        return False
