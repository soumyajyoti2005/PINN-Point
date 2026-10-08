import os

# Set dummy environment variables before any app module imports them.
# This isolates unit tests from the host environment per R6.

os.environ.setdefault("POSTGRES_HOST", "dummy-db")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_USER", "test_user")
os.environ.setdefault("POSTGRES_PASSWORD", "test_pass")
os.environ.setdefault("POSTGRES_DB", "test_db")

os.environ.setdefault("INFLUXDB_HOST", "dummy-influx")
os.environ.setdefault("INFLUXDB_PORT", "8086")
os.environ.setdefault("INFLUX_TOKEN", "dummy-token")
os.environ.setdefault("INFLUX_ORG", "test_org")
os.environ.setdefault("INFLUX_BUCKET", "test_bucket")

os.environ.setdefault("REDIS_HOST", "dummy-redis")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("REDIS_CHANNEL", "test.events")

os.environ.setdefault("MQTT_BROKER", "dummy-mqtt")
os.environ.setdefault("MQTT_PORT", "1883")

os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("API_PORT", "8000")
os.environ.setdefault("DATA_DIR", "/tmp/data")
os.environ.setdefault("CONTRACTS_DIR", "/nonexistent-contracts")
