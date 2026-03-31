import os
import shutil
import subprocess
from core.state import state

MIN_DISK_GB = float(os.getenv("MIN_DISK_GB", 1.0))


def check_video0() -> dict:
    exists = os.path.exists("/dev/video0")
    return {
        "ok": exists,
        "msg": "/dev/video0 present" if exists else "/dev/video0 not found"
    }


def check_ntp() -> dict:
    try:
        result = subprocess.run(
            ["timedatectl", "show", "--property=NTPSynchronized"],
            capture_output=True,
            text=True,
            timeout=2
        )
        synced = "yes" in result.stdout.lower()
        return {
            "ok": synced,
            "msg": "NTP synced" if synced else "NTP not synced"
        }
    except Exception as e:
        return {"ok": False, "msg": str(e)}


def check_storage() -> dict:
    disk = shutil.disk_usage("/")
    free_gb = disk.free / (1024**3)
    ok = free_gb >= MIN_DISK_GB
    return {
        "ok": ok,
        "msg": f"{free_gb:.1f}GB free" if ok else f"Low disk: {free_gb:.1f}GB"
    }


def check_state() -> dict:
    current = state.get()
    ok = current["state"] != "error"
    return {
        "ok": ok,
        "msg": "No errors" if ok else current["error"]
    }


def run_preflight() -> dict:
    checks = {
        "camera": check_video0(),
        "ntp": check_ntp(),
        "storage": check_storage(),
        "state": check_state(),
    }

    if not all(c["ok"] for c in checks.values()):
        state.set_error("preflight failed")

    return checks
