# Camera Node - Recording & Streaming

Raspberry Pi camera node for distributed recording system with real-time accurate timestamps.

## Features

- **720p @ 30fps** recording with hardware H.264 encoding
- **Real-time accurate timestamps** - dropped frames cause freeze, not speedup
- **Gapless segment rotation** - 60-second segments with no frame loss at boundaries
- **360p live streaming** - simultaneous low-res stream for monitoring
- **VFR (Variable Frame Rate)** - preserves real-time sync via MKV timecodes

## Architecture

```
Sensor (OV5647)
    │
    ├──► main (1280x720) ──► H264Encoder (3Mbps) ──► Segments (.mkv)
    │         ISP scaling
    └──► lores (640x360) ──► MJPEGEncoder ──► HTTP Stream (:8080)
```

## Requirements

```bash
# Install dependencies
sudo apt update
sudo apt install -y python3-picamera2 mkvmerge ffmpeg

# Python packages (if needed)
pip install flask
```

## Files

| File | Description |
|------|-------------|
| `recorder.py` | Main recording + streaming script |
| `test_10min.py` | Test script (5 min recording) |
| `combine.py` | Combine segments into single video |

## Usage

### Recording Only
```bash
python3 test_10min.py
```

### Recording + Streaming
```bash
python3 recorder.py
```
- Recording: `/home/pi/recordings/<session>/`
- Stream: `http://<pi-ip>:8080/stream`

### Combine Segments
```bash
python3 combine.py
```

## Configuration

Edit settings at top of `recorder.py`:

```python
# Recording
RECORD_RESOLUTION = (1280, 720)  # 720p
RECORD_BITRATE = 3_000_000       # 3 Mbps
SEGMENT_SECS = 60                # Segment duration

# Streaming
STREAM_RESOLUTION = (640, 360)   # 360p
STREAM_QUALITY = 70              # MJPEG quality (1-100)
STREAM_PORT = 8080
```

## How Real-Time Timestamps Work

### The Problem
Standard video recording uses sequential PTS (Presentation Timestamps). If frames drop:
- 100 frames recorded in 4 seconds (should be 120 at 30fps)
- Video plays back in 3.33 seconds (100/30)
- **Result: Video speeds up**

### The Solution
We capture sensor timestamps for each frame and create VFR (Variable Frame Rate) video:

1. **Record H.264** + capture `SensorTimestamp` metadata per frame
2. **Write timecodes file** with real timestamps (ms):
   ```
   # timecode format v2
   0
   33
   67
   150    ← gap here (frames dropped)
   183
   ```
3. **Remux with mkvmerge** to apply custom timestamps:
   ```bash
   mkvmerge -o output.mkv --timestamps 0:timecodes.txt input.h264
   ```

### Result
- Dropped frames → video freezes momentarily
- Video duration matches wall clock time
- Audio sync preserved (if added later)

## Performance

Tested on Raspberry Pi 4 (no active cooling):

| Setting | Frame Rate | Drop Rate | File Size |
|---------|------------|-----------|-----------|
| 1080p @ 6Mbps | 29.7 fps | ~2% | ~450 MB/10min |
| 720p @ 3Mbps | 29.9 fps | ~0.4% | ~225 MB/10min |

**Recommendation:** Use 720p @ 3Mbps for best balance. Add heatsink for longer recordings.

## Output Format

- **Container:** MKV (Matroska)
- **Codec:** H.264 (hardware encoded via bcm2835-codec)
- **Frame rate:** Variable (VFR), targeting 30fps
- **Timestamps:** Real-time accurate via timecode file

### Converting to MP4
```bash
ffmpeg -i input.mkv -c copy output.mp4
```

## API (when using recorder.py)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/stream` | GET | MJPEG video stream |
| `/status` | GET | Recording status JSON |
| `/snapshot` | GET | Single JPEG frame |

## Troubleshooting

### Camera not detected
```bash
libcamera-hello --list-cameras
```

### Low frame rate
- Check CPU temperature: `vcgencmd measure_temp`
- Add heatsink/fan
- Reduce resolution to 720p

### Stream not accessible
- Check firewall: `sudo ufw allow 8080`
- Verify IP: `hostname -I`

## Integration with Controller

The camera node connects to the controller via MQTT:

```
Subscribe: ctlr/command
Publish:   ctlr/node/{node_id}/health
           ctlr/node/{node_id}/ready
```

See controller README for full protocol specification.
