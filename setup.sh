#!/bin/bash
# Camera Node Setup Script
# Usage: ./setup.sh <node-name>
# Example: ./setup.sh melb-01-cam-01

set -e

NODE_NAME=${1:-$(hostname)}
MQTT_BROKER=${2:-melb-01-ctlr}
SYNC_HOST=${3:-melb-01-ctlr}

echo "=== Camera Node Setup ==="
echo "Node: $NODE_NAME"
echo "MQTT Broker: $MQTT_BROKER"
echo "Sync Host: $SYNC_HOST"
echo ""

# Install system dependencies
echo "[1/6] Installing system packages..."
sudo apt update
sudo apt install -y git python3-dev python3-picamera2 python3-venv

# Create venv with system site-packages (for picamera2)
echo "[2/6] Creating Python virtual environment..."
cd ~/cam
python3 -m venv .venv --system-site-packages
.venv/bin/pip install -r requirements.txt

# Create recordings directory
echo "[3/6] Creating recordings directory..."
mkdir -p ~/recordings

# Generate .env file
echo "[4/6] Generating .env configuration..."
cat > .env << EOF
# Camera Node Configuration
CLIENT_ID=${NODE_NAME}
HTTP_PORT=8080

# Recording Settings
SEGMENT_SECS=120
SESSION_DIR=/home/pi/recordings
RECORD_BITRATE=6000000
RECORD_WIDTH=1280
RECORD_HEIGHT=720
RECORD_FPS=30

# Streaming Settings
STREAM_ENABLED=true
STREAM_TARGET_IP=${MQTT_BROKER}
STREAM_TARGET_PORT=5000
STREAM_BITRATE=600000
STREAM_WIDTH=480
STREAM_HEIGHT=270

# Sync Settings (rsync daemon mode)
SYNC_ENABLED=true
SYNC_TARGET_HOST=${SYNC_HOST}
SYNC_MODULE=logging

# MQTT Logging
MQTT_BROKER=${MQTT_BROKER}
MQTT_TOPIC_BASE=logging/${NODE_NAME}/

# Device
DEVICE=/dev/video0
EOF

# Install systemd services
echo "[5/6] Installing systemd services..."
sudo tee /etc/systemd/system/cam.service > /dev/null << 'EOF'
[Unit]
Description=Camera Recording Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/cam
ExecStart=/home/pi/cam/.venv/bin/python main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/cam-monitor.service > /dev/null << 'EOF'
[Unit]
Description=Camera Health Monitor
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/cam
ExecStart=/home/pi/cam/.venv/bin/python script/monitor.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable cam cam-monitor

echo "[6/6] Setup complete!"
echo ""
echo "=== Next Steps ==="
echo "1. Verify .env configuration: nano ~/cam/.env"
echo "2. Start services: sudo systemctl start cam cam-monitor"
echo "3. Check status: sudo systemctl status cam"
echo "4. View logs: journalctl -u cam -f"
echo ""
echo "=== Controller Setup Required ==="
echo "On ${SYNC_HOST}, ensure rsyncd is configured with:"
echo ""
echo "  /etc/rsyncd.conf:"
echo "  [logging]"
echo "      path = /mnt/logging"
echo "      read only = false"
echo "      uid = pi"
echo "      gid = pi"
echo ""
echo "  Then: sudo systemctl enable --now rsync"
