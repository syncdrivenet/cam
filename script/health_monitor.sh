#!/bin/bash
export PATH=/usr/local/bin:/usr/bin:/bin

. /home/pi/cam/.env

NODE_NAME="${CLIENT_ID:-$(hostname)}"
COMPONENT="health"

log_msg() {
    local message="$1"
    local level="${2:-INFO}"
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

# Get CPU (POSIX compatible using temp file)
awk '/^cpu / {print $2+$4, $5}' /proc/stat > /tmp/cpu1
sleep 0.2
awk '/^cpu / {print $2+$4, $5}' /proc/stat > /tmp/cpu2
read c1 i1 < /tmp/cpu1
read c2 i2 < /tmp/cpu2
CPU=$((100 * (c2 - c1) / (c2 - c1 + i2 - i1)))
rm -f /tmp/cpu1 /tmp/cpu2

TEMP=$(awk '{printf "%.1f", $1/1000}' /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo "N/A")
MEM=$(free | awk 'NR==2{printf "%.1f", $3*100/$2}')
DISK=$(df / | awk 'NR==2{printf "%.1f", $3*100/($3+$4)}')
LOAD=$(cut -d" " -f1 /proc/loadavg)

# Determine level
LEVEL="INFO"
[ "${TEMP%.*}" -ge 75 ] 2>/dev/null && LEVEL="ERROR"
[ "${TEMP%.*}" -ge 65 ] 2>/dev/null && [ "$LEVEL" = "INFO" ] && LEVEL="WARN"
[ "${MEM%.*}" -ge 95 ] 2>/dev/null && LEVEL="ERROR"
[ "${MEM%.*}" -ge 80 ] 2>/dev/null && [ "$LEVEL" = "INFO" ] && LEVEL="WARN"
[ "${DISK%.*}" -ge 95 ] 2>/dev/null && LEVEL="ERROR"
[ "${DISK%.*}" -ge 80 ] 2>/dev/null && [ "$LEVEL" = "INFO" ] && LEVEL="WARN"

MSG="cpu=${CPU}% | temp=${TEMP}C | memory=${MEM}% | disk=${DISK}% | load=${LOAD}"
log_msg "$MSG" "$LEVEL"
echo "[$LEVEL] $NODE_NAME: $MSG"
