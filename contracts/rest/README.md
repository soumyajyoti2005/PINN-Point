# REST API Endpoints

This document lists the REST API endpoints provided by the backend service. All endpoints are prefixed with `/api/v1`.

> **Note:** The definitive source of truth for the REST API is the backend's `/openapi.json` (Swagger UI available at `/docs` when the API is running). This list serves as a high-level overview.

- `GET /health` : Returns system health status (Postgres, InfluxDB, MQTT, Redis).
- `GET /network` : Returns the sewer network layout as a GeoJSON FeatureCollection.
- `GET /nodes/{id}/readings` : Retrieves historical readings for a specific manhole sensor node.
- `POST /readings` : Manually ingest or backfill sensor readings.
- `POST /rainfall` : Manually ingest or backfill rainfall data.
- `GET /rainfall` : Retrieves historical rainfall data.
- `POST /detect` : Manually trigger an anomaly/blockage detection run.
- `GET /detections` : List past detection events.
- `GET /detections/{id}` : Get details of a specific detection event.
- `PATCH /detections/{id}` : Update a detection event (e.g., mark as confirmed or false alarm).
- `POST /simulation/run` : Trigger a full SWMM simulation.
- `POST /simulation/replay` : Start replaying a past event for testing or demonstration.
- `POST /simulation/replay/stop` : Stop an active replay.
