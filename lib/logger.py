"""Shared MQTT logger for camera services."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Load config once
_config = {}
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            _config[k.strip()] = v.strip()

NODE = _config.get("CLIENT_ID", "unknown")
MQTT_BROKER = _config.get("MQTT_BROKER", "localhost")


def _publish(topic: str, payload: dict):
    """Publish JSON payload to MQTT topic."""
    try:
        subprocess.run(
            ["mosquitto_pub", "-h", MQTT_BROKER, "-t", topic, "-m", json.dumps(payload)],
            timeout=5, capture_output=True
        )
    except Exception as e:
        print(f"[MQTT ERROR] {e}")


def log(component: str, message: str, level: str = "INFO"):
    """Send app log to logging/{node} topic."""
    payload = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "node": NODE,
        "component": component,
        "level": level,
        "message": message
    }
    _publish(f"logging/{NODE}", payload)
    print(f"[{level}] {component}: {message}")


def metric(cpu: float, temp: float, mem: float, disk: float, load: float):
    """Send health metrics to metrics/{node} topic."""
    payload = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "node": NODE,
        "cpu": cpu,
        "temp": temp,
        "mem": mem,
        "disk": disk,
        "load": load
    }
    _publish(f"metrics/{NODE}", payload)
