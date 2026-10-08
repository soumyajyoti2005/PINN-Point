# Contracts: The Single Source of Truth

This directory defines the cross-component formats and communication protocols for the PINNpoint system.

## The Isolation Architecture (Rules R1-R8)

To ensure components remain independent and scalable, PINNpoint follows strict isolation rules:

1. **No cross-imports (R1)**: Components (`backend/`, `gateway/`, `frontend/`) never import code from one another. There are no relative paths like `../gateway/...` crossing component boundaries.
2. **Network-only communication (R2)**: Components communicate strictly through network interfaces using the formats defined here: MQTT topics/payloads, Redis channels (e.g., `pinnpoint.events`), internal HTTP endpoints, WebSockets, and the REST OpenAPI.
3. **Specs only (R3)**: This `contracts/` directory contains specifications (JSON Schemas, READMEs) and examples. It never contains executable shared code. Each component implements its own validation logic (e.g., Pydantic in Python, custom JS in Node) and tests against the examples provided here to prevent drift.
4. **Data isolation (R4)**: The `data/` folder is mounted into components, not imported. Code accesses data only via paths from environment variables (e.g., `DATA_DIR`), never hardcoded relative paths.
5. **Component ownership (R5)**: Each component owns its own `Dockerfile`, dependency definitions, `.dockerignore`, tests, and documentation. Build contexts are strictly scoped to the component's directory.
6. **Environment configuration (R6)**: Configuration is handled exclusively via environment variables defined in the root `.env` (documented in `.env.example`). Components read only what they need and do not snoop on other components' files.
7. **Versioned contracts (R7)**: Every contract carries an `"x-version": "1.0.0"`. Messages sent over MQTT/Redis/WebSocket must include `"v": 1`. Components must reject unknown major versions with a clear log entry.
8. **Abstracted infrastructure (R8)**: Infrastructure service names (e.g., `postgres`, `mosquitto`, `redis`) are defined only in `docker-compose.yml` and are injected into application code via environment variables.

## Naming Conventions
- IDs: `node_id`, `zone_id`, `pipe_id`, `detection_id`. All string IDs follow the pattern `^[A-Za-z0-9_-]{1,50}$`.
- Timestamps: `ts` in ISO 8601 UTC.
- Measurements: `level_m` in metres, `intensity_mm_hr` in mm/hr.
