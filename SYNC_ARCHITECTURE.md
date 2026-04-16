# Camera Sync Architecture

## Overview

Video segments are synced from cameras to the controller using a simple, reliable periodic rsync approach.

## Services

Each camera runs two systemd services:

| Service | Script | Purpose |
|---------|--------|---------|
| cam.service | main.py | Recording, HTTP API, event loop |
| cam-monitor.service | script/monitor.py | Health metrics, rsync sync |

## Sync Flow

1. **Recording** (cam.service):
   - Writes segments as `_tmp_seg_XXXX.mp4` (in progress)
   - Renames to `seg_XXXX.mp4` when complete
   - No sync logic - just recording

2. **Sync** (cam-monitor.service):
   - Runs rsync every 120 seconds
   - Uses rsync daemon protocol: `rsync://controller/logging/node/`
   - Excludes `_tmp_*` files (in-progress segments)
   - Removes source files after successful transfer
   - Catches orphans (segments from crashed sessions)

## Why This Design

- **Simple**: No queue state to manage or lose
- **Reliable**: Disk is source of truth, catches orphans
- **Crash-safe**: If service restarts, next sweep catches everything
- **Separation of concerns**: Recording and sync are independent

## Rsync Daemon

Controller runs rsyncd with module `logging` pointing to `/mnt/logging`.

Config: `/etc/rsyncd.conf`
Service: `rsync.service` (systemd)

## Sync Status

The `/status` API returns sync info:

```json
{
  "sync": {
    "status": "idle" or "syncing",
    "segments_queued": 3,  // pending files on camera
    "segments_synced": 0   // use segments_on_ctlr from controller
  }
}
```

- `status`: Detected by checking if rsync process is running
- `segments_queued`: Count of `seg_*.mp4` files in session dir
- `segments_synced`: Not tracked locally; controller counts files via `segments_on_ctlr`

## Changes (2026-04-16)

- Removed queue-based sync_manager from cam.service
- Updated monitor.py to use rsync daemon (not SSH)
- Enabled cam-monitor.service on all cameras
- Set up rsyncd on controller

