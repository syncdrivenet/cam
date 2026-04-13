#!/bin/bash

# Run health_monitor.sh every 5 seconds
(
  while true; do
    /home/pi/cam/script/health_monitor.sh
    sleep 5
  done
) &

# Run rsync_to_central.sh every 2 minutes
(
  while true; do
    /home/pi/cam/script/rsync_to_central.sh
    sleep 120
  done
) &

# Wait for background processes (optional, keeps script alive)
wait
