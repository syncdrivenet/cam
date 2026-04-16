"""HTTP API endpoints for camera node."""

import os
import glob
import socket
import shutil
import time
import psutil
from fastapi import FastAPI
from pydantic import BaseModel

from core.state import state
from core.preflight import run_preflight
from core.events import Event, EventType
from core.event_loop import event_queue

NODE_ID = os.getenv("CLIENT_ID", socket.gethostname())
SESSION_DIR = os.getenv("SESSION_DIR", "/home/pi/recordings")

app = FastAPI(title="Camera Node")


# ------------------ REQUEST MODELS ------------------
class StartRequest(BaseModel):
    start_at: int
    uuid: str


# ------------------ RESPONSE HELPERS ------------------
def response(success: bool, data=None, error=None) -> dict:
    """Build consistent response envelope."""
    return {
        "success": success,
        "node_id": NODE_ID,
        "ts": int(time.time() * 1000),
        "data": data,
        "error": error,
    }


def ok(data=None) -> dict:
    return response(True, data=data)


def fail(error: str) -> dict:
    return response(False, error=error)


def _get_temp() -> float:
    """Get CPU temperature."""
    try:
        return round(int(open("/sys/class/thermal/thermal_zone0/temp").read()) / 1000, 1)
    except Exception:
        return 0.0


def _get_sync_status() -> dict:
    """Get sync status by scanning disk (no queue state)."""
    # Count pending segments (completed files not yet synced)
    pending = len(glob.glob(f"{SESSION_DIR}/**/seg_*.mp4", recursive=True))
    
    # Check if rsync is currently running
    is_syncing = False
    try:
        result = os.popen("pgrep -x rsync").read().strip()
        is_syncing = len(result) > 0
    except:
        pass
    
    return {
        "status": "syncing" if is_syncing else "idle",
        "segments_synced": 0,  # Not tracked locally, use segments_on_ctlr from controller
        "segments_queued": pending,
        "last_sync": None,
        "error": None,
    }


# ------------------ ENDPOINTS ------------------
@app.get("/status")
def status():
    return ok({
        **state.get(),
        "sync": _get_sync_status(),
        "system": {
            "cpu": psutil.cpu_percent(interval=0.5),
            "ram": psutil.virtual_memory().percent,
            "disk_free_gb": round(shutil.disk_usage("/").free / (1024**3), 2),
            "temp": _get_temp(),
        }
    })


@app.get("/preflight")
def preflight():
    success, checks = run_preflight()
    return ok({
        "ready": success,
        "checks": checks,
    })


@app.post("/record/start")
def record_start(req: StartRequest):
    if state.is_recording():
        return fail("already recording")

    now = int(time.time() * 1000)
    if req.start_at < now:
        return fail("start_at is in the past")

    # Queue the start event
    event_queue.put(Event(
        type=EventType.START_RECORDING,
        data={"uuid": req.uuid, "start_at": req.start_at}
    ))

    return ok({"uuid": req.uuid, "start_at": req.start_at})


@app.post("/record/stop")
def record_stop():
    if not state.is_recording():
        return fail("not recording")

    # Queue the stop event
    event_queue.put(Event(type=EventType.STOP_RECORDING))

    return ok()
