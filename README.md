# Camera Node (melb-01-cam-01)

## Services

| Service | Description | Script |
|---------|-------------|--------|
| `cam.service` | Main camera app (HTTP, recording, streaming) | `main.py` |
| `cam-monitor.service` | Health metrics + rsync | `script/monitor.py` |

## Commands

```bash
# Start/stop services
sudo systemctl start cam cam-monitor
sudo systemctl stop cam cam-monitor
sudo systemctl restart cam cam-monitor

# View status
sudo systemctl status cam cam-monitor

# View logs
journalctl -u cam -f
journalctl -u cam-monitor -f
```

## Logging

All logs sent via MQTT to controller, then forwarded to Loki/Grafana.

| Component | Description |
|-----------|-------------|
| `cam` | Main app events (startup, bootcheck) |
| `health` | System metrics every 5s (cpu, temp, mem, disk) |
| `rsync` | File sync status every 2min |

## Rsync Behavior

- Runs every 2 minutes
- Syncs `/home/pi/recordings/` → `ctlr:/mnt/logging/melb-01-cam-01/`
- **Deletes files after successful sync** (saves disk space)
- Retries 3x on failure
- Logs: `Started` → `Completed in Xs | N files | SIZE`

## Config

Edit `.env`:

```bash
CLIENT_ID=melb-01-cam-01          # Node identifier
SESSION_DIR=/home/pi/recordings   # Recording storage
MQTT_BROKER=192.168.8.145         # Controller IP
MQTT_TOPIC_BASE=logging/melb-01-cam-01/
SYNC_TARGET_HOST=pi@192.168.8.145
SYNC_TARGET_DIR=/mnt/logging/melb-01-cam-01/
```

## File Structure

```
/home/pi/cam/
├── main.py              # Main camera app
├── .env                 # Configuration
├── lib/
│   └── logger.py        # Shared MQTT logging
├── script/
│   └── monitor.py       # Health + rsync service
├── core/                # Camera core modules
└── net/                 # HTTP server
```
