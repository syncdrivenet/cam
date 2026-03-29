# Camera Node

Raspberry Pi camera node for distributed recording system.

## Status: MVP In Progress

### Done
- [x] FastAPI + uvicorn HTTP server
- [x] MQTT client (paho-mqtt)
- [x] State machine (ready, preflight, recording, finishing, error)
- [x] Preflight checks (camera, disk, network)
- [x] REST: `/status`, `/preflight`
- [x] MQTT: `start`, `stop`, `preflight` commands with ACK

### Planned
- [ ] Recording with picamera2
- [ ] NTP sync start (schedule recording at future timestamp)
- [ ] MJPEG live streaming `/stream`
- [ ] VFR timestamps for real-time sync

## Architecture

```
                     ┌──────────────┐
                     │  Controller  │
                     └──────┬───────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
         REST (query)              MQTT (commands)
              │                           │
              │                    ┌──────┴──────┐
              │                    │   Broker    │
              │                    └──────┬──────┘
              │                           │
        ┌─────┴─────┬─────────────────────┼─────────────────┐
        │           │                     │                 │
        ▼           ▼                     ▼                 ▼
   ┌─────────┐ ┌─────────┐           ┌─────────┐       ┌─────────┐
   │  Cam 1  │ │  Cam 2  │           │  Cam 1  │       │  Cam 2  │
   │  :8080  │ │  :8080  │           │  (mqtt) │       │  (mqtt) │
   └─────────┘ └─────────┘           └─────────┘       └─────────┘
```

## Quick Start

```bash
# On Pi
cd ~/cam
pip install -r requirements.txt

# Create .env
cat > .env << EOF
HTTP_PORT=8080
CLIENT_ID=cam1
MQTT_BROKER=192.168.1.100
MQTT_PORT=1883
EOF

python main.py
```

## Files

| File | Description |
|------|-------------|
| `main.py` | Entry point |
| `http_server.py` | FastAPI REST endpoints |
| `mqtt_client.py` | MQTT command handlers |
| `state.py` | Thread-safe state manager |
| `preflight.py` | Camera, disk, network checks |

## Configuration

| Var | Default | Description |
|-----|---------|-------------|
| `HTTP_PORT` | 8080 | REST API port |
| `CLIENT_ID` | hostname | Node identifier |
| `MQTT_BROKER` | localhost | Broker address |
| `MQTT_PORT` | 1883 | Broker port |

## REST API

### GET /
```json
{"node_id": "cam1", "status": "ok"}
```

### GET /status
```json
{
  "node_id": "cam1",
  "state": "idle",
  "error_msg": "",
  "system": {"cpu": 12.5, "ram": 34.2, "disk_free": 28.5}
}
```

### GET /preflight
```json
{
  "node_id": "cam1",
  "ok": true,
  "checks": {
    "camera": {"ok": true, "msg": "imx219 [4608x2592]"},
    "disk": {"ok": true, "msg": "28.5GB free"},
    "network": {"ok": true, "msg": "192.168.1.100:1883"}
  }
}
```

### GET /docs
Auto-generated FastAPI docs.

## MQTT

### Topics

| Direction | Topic | Payload |
|-----------|-------|---------|
| Controller → Nodes | `cam/cmd/start` | `{id, start_at}` |
| Controller → Nodes | `cam/cmd/stop` | `{id}` |
| Controller → Nodes | `cam/cmd/preflight` | `{id}` |
| Node → Controller | `cam/node/{id}/ack` | `{id, cmd, ok, error}` |
| Node → Controller | `cam/node/{id}/state` | `{state, error}` |

### Command Flow

```
Controller                    Broker                     Node
    │                           │                          │
    │  cam/cmd/start            │                          │
    │  {id:"x", start_at:123}   │                          │
    ├──────────────────────────►│                          │
    │                           ├─────────────────────────►│
    │                           │                          │
    │                           │  cam/node/cam1/ack       │
    │                           │◄─────────────────────────┤
    │◄──────────────────────────┤  {id:"x", ok:true}       │
    │                           │                          │
    │                           │  cam/node/cam1/state     │
    │◄──────────────────────────┤  {state:"recording"}     │
```

## State Machine

```
boot
  │
  ▼
[preflight] ──► pass ──► [idle]
  │                         │
  │                         │ cmd/start
  │                         ▼
  │                     [recording]
  │                         │
  │                         │ cmd/stop
  │                         ▼
  │                     [finishing] ──► [idle]
  │
  └──► fail ──► [error]
```

| State | Description |
|-------|-------------|
| `idle` | Idle, waiting for commands |
| `preflight` | Running checks |
| `recording` | Camera active |
| `finishing` | Finalizing segment |
| `error` | Check `error_msg` |

## Testing

```bash
# Terminal 1: Run broker
mosquitto

# Terminal 2: Run node
python main.py

# Terminal 3: Watch MQTT messages
mosquitto_sub -t "cam/#" -v

# Terminal 4: Send commands
mosquitto_pub -t "cam/cmd/start" -m '{"id":"test1","start_at":1234567890}'
mosquitto_pub -t "cam/cmd/stop" -m '{"id":"test2"}'

# Terminal 5: REST
curl http://localhost:8080/status
curl http://localhost:8080/preflight
```

## Requirements

- Raspberry Pi OS (tested on Raspbian 13 trixie)
- Python 3.11+
- MQTT broker (mosquitto)

```bash
sudo apt install -y python3-picamera2 mosquitto mosquitto-clients
pip install -r requirements.txt
```
