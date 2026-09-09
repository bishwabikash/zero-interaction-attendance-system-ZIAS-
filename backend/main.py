"""ZIAS FastAPI entrypoint."""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Set

import redis.asyncio as redis
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api.config import settings
from api.database import close_db, engine, init_db
from api.routes import attendance, auth, devices, students
from mqtt.client import mqtt_client

redis_pool = None
_ws_clients: Set[WebSocket] = set()
_ws_task: asyncio.Task | None = None


async def _ws_broadcaster():
    """Fan out Redis pub/sub events to connected websocket clients."""
    global redis_pool
    client = redis.Redis(connection_pool=redis_pool)
    pubsub = client.pubsub()
    await pubsub.subscribe("zias:events")
    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            data = message["data"]
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")
            dead = []
            for ws in list(_ws_clients):
                try:
                    await ws.send_text(data)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                _ws_clients.discard(ws)
    finally:
        try:
            await pubsub.unsubscribe("zias:events")
            await pubsub.close()
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_pool, _ws_task
    init_db()
    redis_pool = redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=False)
    mqtt_client.start()
    _ws_task = asyncio.create_task(_ws_broadcaster())
    print(f"ZIAS API listening on {settings.API_HOST}:{settings.API_PORT}")
    try:
        yield
    finally:
        if _ws_task:
            _ws_task.cancel()
        mqtt_client.stop()
        close_db()
        if redis_pool:
            await redis_pool.disconnect()


app = FastAPI(
    title="ZIAS API",
    description="Zero Interaction Attendance System — REST + WebSocket",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(devices.router, prefix="/api/v1/devices", tags=["devices"])
app.include_router(attendance.router, prefix="/api/v1/attendance", tags=["attendance"])
app.include_router(students.router, prefix="/api/v1/students", tags=["students"])


@app.get("/")
async def root():
    return {"name": "ZIAS API", "version": app.version, "docs": "/docs"}


@app.get("/health")
async def health():
    checks = {"api": "ok"}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc.__class__.__name__}"

    try:
        r = redis.Redis(connection_pool=redis_pool)
        await r.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc.__class__.__name__}"

    checks["mqtt"] = "ok" if mqtt_client.is_connected() else "disconnected"
    all_ok = all(v == "ok" for k, v in checks.items() if k != "mqtt")
    return {"status": "healthy" if all_ok else "degraded", "checks": checks}


@app.websocket("/ws")
async def websocket_events(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    try:
        await ws.send_text(json.dumps({"type": "hello", "msg": "connected"}))
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )
