import os
import socket
import shutil
import psutil
from fastapi import FastAPI
from state import state_manager
from preflight import run_preflight

NODE_ID = os.getenv("CLIENT_ID", socket.gethostname())

app = FastAPI(title="Camera Node", version="0.1.0")


@app.get("/")
def root():
    return {"node_id": NODE_ID, "status": "ok"}


@app.get("/status")
def status():
    return {
        "node_id": NODE_ID,
        "state": state_manager.get_state(),
        "error_msg": state_manager.get_error(),
        "system": {
            "cpu": psutil.cpu_percent(interval=0.5),
            "ram": psutil.virtual_memory().percent,
            "disk_free": round(shutil.disk_usage("/").free / (1024**3), 2),
        }
    }


@app.get("/preflight")
def preflight():
    checks = run_preflight()
    return {
        "node_id": NODE_ID,
        "ok": all(c["ok"] for c in checks.values()),
        "checks": checks
    }
