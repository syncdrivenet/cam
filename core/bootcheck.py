import subprocess
from core.state import state


def check_ntp_sync() -> dict:
    try:
        result = subprocess.run(
            ["timedatectl", "show", "--property=NTPSynchronized"],
            capture_output=True,
            text=True,
            timeout=5
        )
        synced = "yes" in result.stdout.lower()
        return {
            "ok": synced,
            "msg": "NTP synchronized" if synced else "NTP not synchronized"
        }
    except Exception as e:
        return {"ok": False, "msg": str(e)}


def check_camera_device() -> dict:
    try:
        result = subprocess.run(
            ["rpicam-hello", "--list-cameras"],
            capture_output=True,
            text=True,
            timeout=10
        )
        output = result.stdout + result.stderr
        if "Available cameras" in output or "imx" in output.lower():
            lines = output.strip().split("\n")
            cam_line = next((l for l in lines if "imx" in l.lower() or ": " in l), "camera detected")
            return {"ok": True, "msg": cam_line.strip()}
        else:
            return {"ok": False, "msg": "no camera detected"}
    except FileNotFoundError:
        return {"ok": False, "msg": "rpicam-hello not installed"}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


def run_bootcheck() -> dict:
    state.set_preflight()
    
    checks = {
        "ntp": check_ntp_sync(),
        "camera": check_camera_device(),
    }

    all_ok = all(c["ok"] for c in checks.values())
    if all_ok:
        state.set_idle()
    else:
        state.set_error("bootcheck failed")

    return checks
