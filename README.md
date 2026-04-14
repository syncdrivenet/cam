# Camera Node

Raspberry Pi camera node for synchronized multi-camera recording with rsync status tracking.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Camera Node (melb-01-cam-XX)                               │
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
                            │ rsync + HTTP + MQTT
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
3. Recorder creates segments every 120s: `seg_0000.mp4`, `seg_0001.mp4`, ...
4. Each segment completion emits `SEGMENT_FINISHED` event
5. Event loop queues segment for rsync to ctlr
6. ctlr sends `POST /record/stop`
7. Final segment saved, sync manager drains queue

### Sync Flow
```
Camera                                   Controller
───────                                  ──────────
seg_0000.mp4 ──rsync──► /mnt/logging/{cam-id}/{uuid}/seg_0000.mp4
seg_0001.mp4 ──rsync──► /mnt/logging/{cam-id}/{uuid}/seg_0001.mp4
    ...                     ...
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | State, segment, system stats, **sync status** |
| `/preflight` | GET | System readiness checks |
| `/record/start` | POST | Start recording with UUID + start_at |
| `/record/stop` | POST | Stop recording |

## MQTT Logging

Logs and metrics are published to MQTT broker on ctlr:

| Topic | Content |
|-------|---------|
| `metrics/{node}` | Health stats: cpu, temp, mem, disk, load (every 5s) |
| `logging/{node}` | App logs: component, level, message |

Example metrics payload:
```json
{
  "ts": "2026-04-14T05:00:00.000Z",
  "node": "melb-01-cam-01",
  "cpu": 25.5,
  "temp": 52.3,
  "mem": 45.2,
  "disk": 15.5,
  "load": 1.2
}
```

Example log payload:
```json
{
  "ts": "2026-04-14T05:00:00.000Z",
  "node": "melb-01-cam-01",
  "component": "sync",
  "level": "INFO",
  "message": "Syncing: seg_0000.mp4"
}
```

## File Structure

```
/home/pi/cam/
├── main.py              # Entry point - starts HTTP + event loop
├── .env                 # Configuration (not in git)
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
│   └── logger.py        # MQTT logging (log + metric functions)
│
└── script/
    └── monitor.py       # Health metrics service (cam-monitor.service)
```

## Configuration (.env)

Each node has its own `.env` (not tracked in git):

```bash
CLIENT_ID=melb-01-cam-01

# Recording
SESSION_DIR=/home/pi/recordings
RECORD_BITRATE=6000000
RECORD_WIDTH=1280
RECORD_HEIGHT=720
RECORD_FPS=30
SEGMENT_SECS=120

# Sync
SYNC_ENABLED=true
SYNC_TARGET_HOST=pi@melb-01-ctlr
SYNC_TARGET_DIR=/mnt/logging

# MQTT
MQTT_BROKER=192.168.8.145
MQTT_TOPIC_BASE=logging/melb-01-cam-01/
```

## Services

```bash
# Camera service (recording + HTTP API)
sudo systemctl start cam
sudo systemctl status cam
journalctl -u cam -f

# Monitor service (health metrics + rsync)
sudo systemctl start cam-monitor
sudo systemctl status cam-monitor
journalctl -u cam-monitor -f

# Restart after code changes
sudo systemctl restart cam cam-monitor
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

## Setup New Camera Node

1. Clone repo: `git clone git@github.com:syncdrivenet/cam.git`
2. Create venv: `python -m venv .venv --system-site-packages`
3. Install deps: `.venv/bin/pip install -r requirements.txt`
4. Create `.env` with correct CLIENT_ID and MQTT_TOPIC_BASE
5. Add ctlr SSH key: `ssh-keyscan -H melb-01-ctlr >> ~/.ssh/known_hosts`
6. Generate SSH key: `ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa`
7. Add pubkey to ctlr: copy `~/.ssh/id_rsa.pub` to ctlr `~/.ssh/authorized_keys`
8. Create systemd services (cam.service, cam-monitor.service)
9. Add node to ctlr config.py NODES list
