#!/bin/bash

# -----------------------------
# Node logging script for rsync
# -----------------------------
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
source /home/pi/cam/.env  # MQTT_BROKER, MQTT_TOPIC_BASE, etc.

# Ensure jq is installed: sudo apt install jq

NODE_NAME="${CLIENT_ID:-melb-01-cam-01}"   # unique node ID
COMPONENT="rsync"

# Function to publish structured JSON to MQTT
log_msg() {
    local message="$1"
    local level="${2:-INFO}"  # default to INFO

    TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.%6NZ")

    PAYLOAD=$(jq -n \
        --arg ts "$TIMESTAMP" \
        --arg node "$NODE_NAME" \
        --arg component "$COMPONENT" \
        --arg level "$level" \
        --arg message "$message" \
        '{ts: $ts, node: $node, component: $component, level: $level, message: $message}')

    mosquitto_pub -h "$MQTT_BROKER" -t "${MQTT_TOPIC_BASE}${COMPONENT}" -m "$PAYLOAD"
}

# -----------------------------
# Start rsync operation
# -----------------------------
log_msg "Rsync started" "INFO"
start_time=$(date +%s)

# Temporary log file for capturing rsync output
LOGFILE=$(mktemp)

# Run rsync
rsync -av --ignore-existing --exclude='_tmp_*' --info=stats2 "$SESSION_DIR/" "${SYNC_TARGET_HOST}:${SYNC_TARGET_DIR}" > "$LOGFILE" 2>&1
exit_code=$?

# Parse rsync log and send summary lines only
while IFS= read -r line; do
    if [[ "$line" =~ ^sent\ .* || "$line" =~ ^Number\ of\ files\ transferred ]]; then
        log_msg "$line" "INFO"
    fi
done < "$LOGFILE"

# Compute duration
end_time=$(date +%s)
duration=$((end_time - start_time))

# Send final completion message
if [ $exit_code -eq 0 ]; then
    log_msg "Rsync completed successfully in ${duration}s" "INFO"
else
    log_msg "Rsync failed after ${duration}s (exit code $exit_code)" "ERROR"
fi

# Clean up temporary log file
rm "$LOGFILE"
