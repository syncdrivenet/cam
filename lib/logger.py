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


def log(component: str, message: str, level: str = "INFO"):
    """Send structured log via MQTT."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    payload = json.dumps({
        "ts": ts,
        "node": NODE,
        "component": component,
        "level": level,
        "message": message
    })
    topic = f"{MQTT_TOPIC_BASE}{component}"
    try:
        subprocess.run(
            ["mosquitto_pub", "-h", MQTT_BROKER, "-t", topic, "-m", payload],
            timeout=5, capture_output=True
        )
    except Exception as e:
        print(f"[MQTT ERROR] {e}")
    print(f"[{level}] {component}: {message}")
