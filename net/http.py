import os
import socket
import shutil
import time
import psutil
from fastapi import FastAPI
from pydantic import BaseModel

from core.state import state
from core.preflight import run_preflight
from media import recorder

NODE_ID = os.getenv("CLIENT_ID", socket.gethostname())

app = FastAPI(title="Camera Node")


class StartRequest(BaseModel):
    start_at: int
    uuid: str


@app.get("/status")
def status():
    return {
        "node_id": NODE_ID,
        **state.get(),
        "system": {
            "cpu": psutil.cpu_percent(interval=0.5),
            "ram": psutil.virtual_memory().percent,
            "disk_free": round(shutil.disk_usage("/").free / (1024**3), 2),
        }
    }


@app.get("/preflight")
def preflight():
    success, checks = run_preflight()
    return {
        "node_id": NODE_ID,
        "ready": success,
        "checks": checks
    }


@app.post("/record/start")
def record_start(req: StartRequest):
    if state.is_recording():
        return {"ready": False, "error": "already recording"}
    
    now = int(time.time() * 1000)
    if req.start_at < now:
        return {"ready": False, "error": "start_at is in the past"}
    
    recorder.start(req.start_at, req.uuid)
    return {"ready": True, "uuid": req.uuid}


@app.post("/record/stop")
def record_stop():
    if not state.is_recording():
        return {"ready": False, "error": "not recording"}
    
    recorder.stop()
    return {"ready": True}
