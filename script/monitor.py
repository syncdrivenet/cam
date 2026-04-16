#!/usr/bin/env python3
"""Combined health monitor and rsync service."""

import os
import re
import subprocess
import time
import threading
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.logger import log, metric, _config, NODE

SESSION_DIR = _config.get("SESSION_DIR", "/home/pi/recordings")
SYNC_HOST = _config.get("SYNC_TARGET_HOST", "")
SYNC_MODULE = _config.get("SYNC_MODULE", "logging")


def get_health():
    """Collect system metrics."""
    with open("/proc/stat") as f:
        c1 = [int(x) for x in f.readline().split()[1:]]
    time.sleep(0.2)
    with open("/proc/stat") as f:
        c2 = [int(x) for x in f.readline().split()[1:]]
    cpu = 100 * (1 - (c2[3] - c1[3]) / (sum(c2) - sum(c1)))

    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            temp = int(f.read()) / 1000
    except:
        temp = 0

    with open("/proc/meminfo") as f:
        mem = {}
        for line in f:
            parts = line.split()
            mem[parts[0].rstrip(":")] = int(parts[1])
    mem_pct = 100 * (1 - mem["MemAvailable"] / mem["MemTotal"])

    st = os.statvfs("/")
    disk_pct = 100 * (1 - st.f_bavail / st.f_blocks)

    with open("/proc/loadavg") as f:
        load = f.read().split()[0]

    return cpu, temp, mem_pct, disk_pct, load


def health_loop():
    """Report health every 5 seconds."""
    while True:
        try:
            cpu, temp, mem, disk, load = get_health()
            level = "INFO"
            if temp >= 75 or mem >= 95 or disk >= 95:
                level = "ERROR"
            elif temp >= 65 or mem >= 80 or disk >= 80:
                level = "WARN"
            metric(cpu, temp, mem, disk, float(load))
        except Exception as e:
            log("health", f"Error: {e}", "ERROR")
        time.sleep(5)


def parse_rsync_stats(output):
    """Parse rsync --stats output for summary."""
    files = bytes_sent = 0
    for line in output.splitlines():
        if m := re.search(r"Number of regular files transferred:\s*(\d+)", line):
            files = int(m.group(1))
        elif m := re.search(r"Total transferred file size:\s*([\d,]+)", line):
            bytes_sent = int(m.group(1).replace(",", ""))
    
    # Format bytes
    if bytes_sent >= 1_000_000_000:
        size = f"{bytes_sent/1_000_000_000:.1f}GB"
    elif bytes_sent >= 1_000_000:
        size = f"{bytes_sent/1_000_000:.1f}MB"
    elif bytes_sent >= 1_000:
        size = f"{bytes_sent/1_000:.1f}KB"
    else:
        size = f"{bytes_sent}B"
    
    return files, size


def do_rsync():
    """Run rsync to daemon with retries."""
    if not SYNC_HOST:
        return False, "Sync not configured", 0, "0B"
    
    # Use rsync daemon protocol: rsync://host/module/node/
    target = f"rsync://{SYNC_HOST}/{SYNC_MODULE}/{NODE}/"
    
    for attempt in range(3):
        try:
            result = subprocess.run(
                ["rsync", "-av", "--stats", 
                 "--remove-source-files", "--exclude=_tmp_*",
                 f"{SESSION_DIR}/", target],
                capture_output=True, text=True, timeout=600
            )
            if result.returncode == 0:
                files, size = parse_rsync_stats(result.stdout)
                return True, "OK", files, size
            if attempt < 2:
                time.sleep(5)
        except subprocess.TimeoutExpired:
            return False, "Timeout", 0, "0B"
        except Exception as e:
            return False, str(e), 0, "0B"
    return False, "Failed after 3 attempts", 0, "0B"


def rsync_loop():
    """Run rsync every 2 minutes."""
    time.sleep(10)
    while True:
        try:
            log("rsync", "Started", "INFO")
            start = time.time()
            ok, msg, files, size = do_rsync()
            duration = int(time.time() - start)
            
            if ok:
                log("rsync", f"Completed in {duration}s | {files} files | {size}", "INFO")
            else:
                log("rsync", f"Failed after {duration}s: {msg}", "ERROR")
        except Exception as e:
            log("rsync", f"Error: {e}", "ERROR")
        time.sleep(120)


if __name__ == "__main__":
    print(f"Starting monitor for {NODE}")
    threading.Thread(target=health_loop, daemon=True).start()
    rsync_loop()
