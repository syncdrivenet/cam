#!/bin/bash
# sync_recordings.sh
# Syncs finalized .mp4 recordings, ignoring active TMP segments (_tmp_*.mp4)

SOURCE_DIR="/home/pi/recordings/"
DEST_DIR="pi@172.20.10.2:/home/pi/recordings"

# Use rsync to sync only files that don't start with _tmp_
rsync -av --exclude='_tmp_*.mp4' "$SOURCE_DIR" "$DEST_DIR"

#remove local copies after successful transfer
#rsync -avz --remove-source-files --exclude='_tmp_*.mp4' "$SOURCE_DIR" "$DEST_DIR"
