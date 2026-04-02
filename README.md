# Camera Node

Raspberry Pi camera node for distributed recording system.

## Status

### Done
- [x] FastAPI + uvicorn HTTP server
- [x] Event-driven architecture with thread-safe state
- [x] Preflight checks (camera, NTP, storage, state)
- [x] REST: `/status`, `/preflight`, `/record/start`, `/record/stop`
- [x] Synchronized start via `start_at` timestamp
- [x] Recording with picamera2 (H264, segmented)

### Planned
- [ ] MJPEG live streaming `/stream`
- [ ] VFR timestamps for real-time sync
- [ ] Segment upload to remote storage

## Architecture

```
┌─────────────────┐
│   Controller    │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐      ┌─────────────┐
│   HTTP Server   │─────►│ Event Queue │
│   (FastAPI)     │      └──────┬──────┘
└─────────────────┘             │
                                ▼
                        ┌───────────────┐
                        │  Event Loop   │
                        │ (state owner) │
                        └───────┬───────┘
                                │
                                ▼
                        ┌───────────────┐
                        │   Recorder    │
                        │  (picamera2)  │
                        └───────────────┘
```

## Quick Start

```bash
cd ~/cam
source .venv/bin/activate
pip install -r requirements.txt

# Create .env
cat > .env << 'EOF'
HTTP_PORT=8080
CLIENT_ID=melb-01-cam-01
SESSION_DIR=/home/pi/recordings
RECORD_BITRATE=6000000
RECORD_WIDTH=1280
RECORD_HEIGHT=720
RECORD_FPS=30
SEGMENT_SECS=30
EOF

python main.py
```

## Files

| File | Description |
|------|-------------|
| `main.py` | Entry point, boot checks, starts event loop and HTTP |
| `net/http.py` | FastAPI REST endpoints |
| `core/state.py` | Thread-safe state manager |
| `core/event_loop.py` | Event-driven state transitions |
| `core/events.py` | Event types |
| `core/preflight.py` | Camera, NTP, storage, state checks |
| `core/bootcheck.py` | Boot-time checks with retry |
| `media/recorder.py` | picamera2 recording worker |

## Configuration

| Var | Default | Description |
|-----|---------|-------------|
| `HTTP_PORT` | 8080 | REST API port |
| `CLIENT_ID` | hostname | Node identifier |
| `SESSION_DIR` | /home/pi/recordings | Recording output directory |
| `RECORD_BITRATE` | 6000000 | H264 bitrate (6 Mbps) |
| `RECORD_WIDTH` | 1280 | Video width |
| `RECORD_HEIGHT` | 720 | Video height |
| `RECORD_FPS` | 30 | Frame rate |
| `SEGMENT_SECS` | 30 | Segment duration |

## REST API

All responses use a standard envelope:

```json
{
  "success": true,
  "node_id": "melb-01-cam-01",
  "ts": 1712045000123,
  "data": { ... },
  "error": null
}
```

### GET /status

```json
{
  "success": true,
  "node_id": "melb-01-cam-01",
  "ts": 1712045010000,
  "data": {
    "state": "recording",
    "segment": 2,
    "error": null,
    "system": { "cpu": 45.2, "ram": 62.1, "disk_free_gb": 12.4 }
  },
  "error": null
}
```

### GET /preflight

```json
{
  "success": true,
  "node_id": "melb-01-cam-01",
  "ts": 1712045000123,
  "data": {
    "ready": true,
    "checks": {
      "camera": { "ok": true, "msg": "/dev/video0 present" },
      "ntp": { "ok": true, "msg": "NTP synced" },
      "storage": { "ok": true, "msg": "12.4GB free" },
      "state": { "ok": true, "msg": "idle" }
    }
  },
  "error": null
}
```

### POST /record/start

Start recording. Use `start_at` for synchronized multi-camera start.

**Request:**
```json
{
  "uuid": "session-abc-123",
  "start_at": 1712045005000
}
```

| Field | Description |
|-------|-------------|
| `uuid` | Unique session ID |
| `start_at` | Unix timestamp in ms when recording should begin |

**Response:**
```json
{
  "success": true,
  "node_id": "melb-01-cam-01",
  "ts": 1712045000456,
  "data": { "uuid": "session-abc-123", "start_at": 1712045005000 },
  "error": null
}
```

**Errors:**
| Scenario | Error |
|----------|-------|
| Already recording | `"already recording"` |
| Timestamp in past | `"start_at is in the past"` |

### POST /record/stop

```json
{
  "success": true,
  "node_id": "melb-01-cam-01",
  "ts": 1712045060000,
  "data": null,
  "error": null
}
```

**Errors:**
| Scenario | Error |
|----------|-------|
| Not recording | `"not recording"` |

## Synchronized Recording

```python
import time
import httpx

nodes = ["melb-01-cam-01.local:8080", "melb-01-cam-02.local:8080"]
session_uuid = "session-abc-123"
start_at = int(time.time() * 1000) + 5000  # 5 seconds from now

# 1. Preflight all
for node in nodes:
    r = httpx.get(f"http://{node}/preflight")
    if not r.json()["data"]["ready"]:
        raise Exception(f"{node} not ready")

# 2. Start all with same timestamp
for node in nodes:
    httpx.post(f"http://{node}/record/start", json={
        "uuid": session_uuid,
        "start_at": start_at
    })

# 3. Wait...
time.sleep(30)

# 4. Stop all
for node in nodes:
    httpx.post(f"http://{node}/record/stop")
```

## State Machine

```
boot ──► [bootcheck] ──► pass ──► [idle]
                                    │
                                    │ /record/start
                                    ▼
                               [recording]
                                    │
                                    │ /record/stop
                                    ▼
                               [cleanup] ──► [idle]
```

| State | Description |
|-------|-------------|
| `idle` | Ready for commands |
| `recording` | Camera active, segments being written |
| `cleanup` | Finalizing recording |
| `error` | Check `error` field |

## Testing

```bash
# Check status
curl http://localhost:8080/status | jq

# Run preflight
curl http://localhost:8080/preflight | jq

# Start recording (immediate - for testing)
curl -X POST http://localhost:8080/record/start \
  -H "Content-Type: application/json" \
  -d '{"uuid": "test-123", "start_at": 1712045005000}' | jq

# Stop recording
curl -X POST http://localhost:8080/record/stop | jq
```

## Requirements

- Raspberry Pi 4/5 with camera module
- Raspberry Pi OS (Bookworm)
- Python 3.11+
- NTP time synchronization

```bash
sudo apt install -y python3-picamera2
pip install fastapi uvicorn psutil python-dotenv
```
