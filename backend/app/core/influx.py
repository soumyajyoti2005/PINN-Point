from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
from app.config import settings

def get_influx_client():
    url = f"http://{settings.influxdb_host}:{settings.influxdb_port}"
    return InfluxDBClientAsync(url=url, token=settings.influx_token, org=settings.influx_org)

async def check_influx():
    client = get_influx_client()
    try:
        ping = await client.ping()
        return ping
    except Exception:
        return False
    finally:
        await client.close()
