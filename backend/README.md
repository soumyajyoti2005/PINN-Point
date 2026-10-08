# PINNpoint Backend

This component provides the REST API, ML inference, and simulation logic.
It connects to Postgres, InfluxDB, Redis, and Mosquitto MQTT.
It accesses data via the `DATA_DIR` environment variable.

constraints.txt pins the working dependency set. Regenerate it with: `docker compose exec -T api pip freeze | Set-Content -Encoding ascii backend/constraints.txt` (PowerShell). Regenerate whenever dependencies change.
