from fastapi import APIRouter
from app.core.db import check_postgres
from app.core.influx import check_influx
from app.core.events import check_redis
import aiomqtt
from app.config import settings

router = APIRouter()

async def check_mqtt():
    try:
        async with aiomqtt.Client(hostname=settings.mqtt_broker, port=settings.mqtt_port) as client:
            return True
    except Exception:
        return False

@router.get("/health")
async def health_check():
    pg_ok = await check_postgres()
    influx_ok = await check_influx()
    redis_ok = await check_redis()
    mqtt_ok = await check_mqtt()
    
    status = "ok" if (pg_ok and influx_ok and redis_ok and mqtt_ok) else "degraded"
    
    return {
        "status": status,
        "postgres": "ok" if pg_ok else "down",
        "influx": "ok" if influx_ok else "down",
        "redis": "ok" if redis_ok else "down",
        "mqtt": "ok" if mqtt_ok else "down",
    }
