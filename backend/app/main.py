import uuid
import logging
import json
import time
import re
from contextvars import ContextVar
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.routes_health import router as health_router
from app.api.routes_network import router as network_router
from app.api.routes_readings import router as readings_router
from app.api.routes_rainfall import router as rainfall_router
from app.api.routes_detection import router as detection_router
from app.api.routes_simulation import router as simulation_router
from app.api.routes_replay import router as replay_router

request_id_ctx = ContextVar("request_id", default=None)

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "level": record.levelname,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(),
            "time": self.formatTime(record, self.datefmt)
        }
        if hasattr(record, "method"):
            log_obj["method"] = record.method
            log_obj["path"] = record.path
            log_obj["status"] = record.status
            log_obj["duration_ms"] = record.duration_ms
        return json.dumps(log_obj)

logger = logging.getLogger("pinnpoint.request")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)
logger.propagate = False

app = FastAPI(title="PINNpoint API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REQ_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    start_time = time.perf_counter()
    req_id = request.headers.get("X-Request-ID", "")
    if not REQ_ID_PATTERN.match(req_id):
        req_id = str(uuid.uuid4())
    
    token = request_id_ctx.set(req_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms
            }
        )
        return response
    finally:
        request_id_ctx.reset(token)

app.include_router(health_router, prefix="/api/v1")
app.include_router(network_router, prefix="/api/v1")
app.include_router(readings_router, prefix="/api/v1")
app.include_router(rainfall_router, prefix="/api/v1")
app.include_router(detection_router, prefix="/api/v1")
app.include_router(simulation_router, prefix="/api/v1")
app.include_router(replay_router, prefix="/api/v1")
