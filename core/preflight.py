import os
import shutil
import subprocess

from core.state import state

MIN_DISK_GB = float(os.getenv("MIN_DISK_GB", 1.0))


def check_camera() -> dict:
    """Check if camera device is available."""
    exists = os.path.exists("/dev/video0")
    return {
        "ok": exists,
        "msg": "/dev/video0 present" if exists else "/dev/video0 not found"
    }


def check_ntp() -> dict:
    """Check if NTP is synchronized."""
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
    """Check if sufficient disk space is available."""
    disk = shutil.disk_usage("/")
    free_gb = disk.free / (1024**3)
    ok = free_gb >= MIN_DISK_GB
    return {
        "ok": ok,
        "msg": f"{free_gb:.1f}GB free" if ok else f"Low disk: {free_gb:.1f}GB"
    }


def check_state() -> dict:
    """Check if state is idle."""
    current = state.get()["state"]
    ok = current == "idle"
    return {
        "ok": ok,
        "msg": "idle" if ok else f"state is {current}"
    }


def run_preflight() -> tuple[bool, dict]:
    """Run all preflight checks. Read-only, does not modify state."""
    checks = {
        "camera": check_camera(),
        "ntp": check_ntp(),
        "storage": check_storage(),
        "state": check_state(),
    }

    success = all(c.get("ok", False) for c in checks.values())

    if not success:
        print(f"[PREFLIGHT] Failed: {checks}")

    return success, checks
