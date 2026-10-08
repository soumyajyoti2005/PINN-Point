# PINN-Point Gateway

The Gateway component pushes real-time events to frontend clients via WebSockets.

## Environment Variables
The gateway reads only the following environment variables:
- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_CHANNEL`
- `GATEWAY_PORT`
- `WS_TOKEN`
- `CONTRACTS_DIR` (used by tests and the smoke script only)
