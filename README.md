# Camera Node

Raspberry Pi camera node for synchronized multi-camera recording with rsync status tracking.

## Quick Start

```bash
# On a fresh Raspberry Pi:
git clone git@github.com:syncdrivenet/cam.git
cd cam
./setup.sh melb-01-cam-XX
```

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
  "level": "METRICS",
  "component": "health",
  "cpu": 25.5,
  "temp": 52.3,
  "mem": 45.2,
  "disk": 15.5,
  "load": 1.2,
  "message": "cpu=25.5% temp=52.3C mem=45.2% disk=15.5% load=1.20"
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
HTTP_PORT=8080

# Recording
SESSION_DIR=/home/pi/recordings
RECORD_BITRATE=6000000
RECORD_WIDTH=1280
RECORD_HEIGHT=720
RECORD_FPS=30
SEGMENT_SECS=120

# Sync (rsync daemon mode - no SSH keys needed)
SYNC_ENABLED=true
SYNC_TARGET_HOST=melb-01-ctlr
SYNC_MODULE=logging

# MQTT
MQTT_BROKER=melb-01-ctlr
MQTT_TOPIC_BASE=logging/melb-01-cam-01/

# Device
DEVICE=/dev/video0
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

### Automated Setup (Recommended)

```bash
git clone git@github.com:syncdrivenet/cam.git
cd cam
./setup.sh melb-01-cam-XX
```

The `setup.sh` script handles:
- System packages (git, python3-dev, python3-picamera2)
- Python venv with dependencies
- Systemd services (cam, cam-monitor)
- Generates `.env` configuration

### Manual Setup

```bash
# 1. Install system packages
sudo apt update
sudo apt install -y git python3-dev python3-picamera2 python3-venv

# 2. Clone and setup
git clone git@github.com:syncdrivenet/cam.git
cd cam
python3 -m venv .venv --system-site-packages
.venv/bin/pip install -r requirements.txt

# 3. Configure
nano .env  # Set CLIENT_ID, MQTT_BROKER, etc.

# 4. Create directories
mkdir -p ~/recordings

# 5. Install services (see setup.sh for service file contents)
sudo systemctl daemon-reload
sudo systemctl enable cam cam-monitor
sudo systemctl start cam cam-monitor
```

### Controller Setup (rsyncd)

Camera nodes sync using rsync daemon (no SSH keys needed).

On the controller (`melb-01-ctlr`):

```bash
# 1. Create /etc/rsyncd.conf
sudo tee /etc/rsyncd.conf << 'EOF'
[logging]
    path = /mnt/logging
    read only = false
    uid = pi
    gid = pi
EOF

# 2. Enable rsync daemon
sudo systemctl enable --now rsync
```

## Preventing SD Card Corruption

### 1. Read-Only Root Filesystem (Recommended)

```bash
sudo raspi-config
# Advanced Options -> Overlay FS -> Enable
```

To make changes, disable overlay temporarily, reboot, make changes, re-enable.

### 2. Safe Git Operations

```bash
# Always pull with rebase
git pull --rebase

# If corruption occurs, reset to remote:
rm -rf ~/cam
git clone git@github.com:syncdrivenet/cam.git
./setup.sh $(hostname)
```

### 3. Graceful Shutdown

```bash
sudo shutdown now
```

### 4. Quality SD Card

Use industrial/endurance-rated SD cards (SanDisk Max Endurance, Samsung PRO Endurance).

### 5. Watchdog Timer

```bash
# /boot/firmware/config.txt
dtparam=watchdog=on

# /etc/systemd/system.conf
RuntimeWatchdogSec=10
```

## Troubleshooting

### Service won't start
```bash
journalctl -u cam -n 50
/home/pi/cam/.venv/bin/python -c "import picamera2"
```

### Rsync failing
```bash
rsync rsync://melb-01-ctlr/logging/  # Test connection
ssh melb-01-ctlr "sudo systemctl status rsync"
```

### Camera not detected
```bash
libcamera-hello --list-cameras
```
