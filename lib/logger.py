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
MQTT_TOPIC_BASE = _config.get("MQTT_TOPIC_BASE", f"logging/{NODE}/")


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
    """Send structured log via MQTT."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    payload = {
        "ts": ts,
        "node": NODE,
        "component": component,
        "level": level,
        "message": message
    }
    topic = f"logging/{NODE}"
    _publish(topic, payload)
    print(f"[{level}] {component}: {message}")


def metric(cpu: float, temp: float, mem: float, disk: float, load: float):
    """Send health metrics via MQTT with level=METRICS for Grafana filtering."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    payload = {
        "ts": ts,
        "node": NODE,
        "level": "METRICS",
        "component": "health",
        "cpu": round(cpu, 1),
        "temp": round(temp, 1),
        "mem": round(mem, 1),
        "disk": round(disk, 1),
        "load": float(load),
        "message": f"cpu={cpu:.1f}% temp={temp:.1f}C mem={mem:.1f}% disk={disk:.1f}% load={load:.2f}"
    }
    topic = f"logging/{NODE}"
    _publish(topic, payload)
    print(f"[METRICS] cpu={cpu:.0f}% temp={temp:.1f}C mem={mem:.1f}% disk={disk:.1f}%")
