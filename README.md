# Camera Node

Raspberry Pi camera node for synchronized multi-camera recording with rsync status tracking.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Camera Node (melb-01-cam-01 / melb-01-cam-02)              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  HTTP API   │    │  Recorder   │    │    Sync     │     │
│  │  (FastAPI)  │◄───│  (picam2)   │───►│  (rsync)    │     │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘     │
│         │                  │                  │             │
│         │           ┌──────▼──────┐           │             │
│         └──────────►│ Event Loop  │◄──────────┘             │
│                     └──────┬──────┘                         │
│                            │                                │
│                     ┌──────▼──────┐                         │
│                     │    State    │                         │
│                     │   Manager   │                         │
│                     └─────────────┘                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ rsync + HTTP
                            ▼
                     ┌─────────────┐
                     │   ctlr      │
                     │  (Pi 4)     │
                     └─────────────┘
```

## Data Flow

### Recording Flow
1. ctlr sends `POST /record/start` with UUID + timestamp
2. Camera waits until `start_at` timestamp (synchronized start)
3. Recorder creates segments every 30s: `seg_0000.mp4`, `seg_0001.mp4`, ...
4. Each segment completion emits `SEGMENT_FINISHED` event
5. Event loop queues segment for rsync to ctlr
6. ctlr sends `POST /record/stop`
7. Final segment saved, sync manager drains queue

### Sync Flow
```
Camera                                   Controller
───────                                  ──────────
seg_0000.mp4 ──rsync──► /mnt/logging/cam-01/{uuid}/seg_0000.mp4
seg_0001.mp4 ──rsync──► /mnt/logging/cam-01/{uuid}/seg_0001.mp4
    ...                     ...
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | State, segment, system stats, **sync status** |
| `/preflight` | GET | System readiness checks |
| `/record/start` | POST | Start recording with UUID + start_at |
| `/record/stop` | POST | Stop recording |

### GET /status Response

```json
{
  "success": true,
  "node_id": "melb-01-cam-01",
  "ts": 1713100000000,
  "data": {
    "state": "recording",
    "segment": 5,
    "error": null,
    "sync": {
      "status": "idle",           // idle | syncing
      "last_sync": 1713099900000, // unix ms
      "segments_synced": 4,
      "segments_queued": 1,
      "current_segment": null,
      "error": null
    },
    "system": {
      "cpu": 25.5,
      "ram": 45.2,
      "disk_free_gb": 28.5,
      "temp": 52.3
    }
  }
}
```

## File Structure

```
/home/pi/cam/
├── main.py              # Entry point - starts HTTP + event loop
├── .env                 # Configuration
│
├── core/
│   ├── state.py         # Thread-safe state manager
│   ├── events.py        # Event types
│   ├── event_loop.py    # Central event handler
│   └── preflight.py     # System readiness checks
│
├── media/
│   ├── recorder.py      # picamera2 recording worker
│   ├── sync.py          # rsync manager with status tracking
│   └── streamer.py      # (optional) live streaming
│
├── net/
│   └── http.py          # FastAPI endpoints
│
├── lib/
│   └── logger.py        # MQTT logging
│
└── script/
    └── monitor.py       # Health metrics service
```

## Configuration (.env)

```bash
CLIENT_ID=melb-01-cam-01

# Recording
SESSION_DIR=/home/pi/recordings
RECORD_BITRATE=6000000
RECORD_WIDTH=1280
RECORD_HEIGHT=720
RECORD_FPS=30
SEGMENT_SECS=30

# Sync
SYNC_ENABLED=true
SYNC_TARGET_HOST=pi@melb-01-ctlr
SYNC_TARGET_DIR=/mnt/logging

# MQTT
MQTT_BROKER=192.168.8.145
```

## Services

```bash
# Start camera service
sudo systemctl start cam

# View logs
journalctl -u cam -f

# Restart after code changes
sudo systemctl restart cam
```

## States

| State | Description |
|-------|-------------|
| `idle` | Ready for recording |
| `recording` | Actively recording |
| `cleanup` | Finalizing session |
| `error` | Error occurred |

## Sync Status

| Status | Description |
|--------|-------------|
| `idle` | No active rsync |
| `syncing` | rsync in progress |

The sync manager:
- Queues segments as they complete
- Waits for file to finish writing (size check)
- rsync with checksum verification
- Removes local file after successful sync
- Retries failed transfers
