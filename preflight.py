# preflight.py
import os
import shutil
import socket
from state import state_manager

def check_camera() -> tuple[bool, str]:
    import subprocess
    try:
        result = subprocess.run(
            ["rpicam-hello", "--list-cameras"],
            capture_output=True,
            timeout=3
        )
        if result.returncode != 0:
            return False, "no camera found"

        for line in result.stdout.decode().splitlines():
            if "[" in line and "]" in line:
                return True, line.strip()

        return False, "no camera found"
    except Exception as e:
        return False, str(e)

def check_disk() -> tuple[bool, str]:
    _, _, free = shutil.disk_usage("/")
    free_gb = free / (1024 ** 3)
    return (True, f"{free_gb:.1f}GB free") if free_gb > 1.0 else (False, f"only {free_gb:.1f}GB free")

def check_network() -> tuple[bool, str]:
    broker = os.getenv("MQTT_BROKER")
    port = os.getenv("MQTT_PORT")
    if not broker or not port:
        return False, "MQTT_BROKER or MQTT_PORT not set"
    try:
        socket.create_connection((broker, int(port)), timeout=3)
        return True, f"{broker}:{port}"
    except Exception as e:
        return False, str(e)

def run_preflight() -> dict:
    print("[PREFLIGHT] Running checks...")
    state_manager.set_preflight()

    checks = {
        "camera":  check_camera(),
        "disk":    check_disk(),
        "network": check_network(),
    }

    failed = {k: v[1] for k, v in checks.items() if not v[0]}

    if failed:
        msg = ", ".join(failed.values())
        print(f"[PREFLIGHT] Failed: {msg}")
        state_manager.set_error(msg)
    else:
        print("[PREFLIGHT] All checks passed")
        state_manager.set_idle()

    return {k: {"ok": v[0], "msg": v[1]} for k, v in checks.items()}
