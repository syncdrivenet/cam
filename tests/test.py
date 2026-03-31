#!/usr/bin/env python3
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput
import os, time, threading, queue

PI4_IP       = "172.20.10.2"   # replace with Pi 4 IP
SEGMENT_SECS = 30
SESSION_DIR  = "/home/pi/recordings"
os.makedirs(SESSION_DIR, exist_ok=True)

seg_num    = 0
recording  = True
sync_queue = queue.Queue()

def segment_path(n):
    return f"{SESSION_DIR}/seg_{n:04d}.h264"

def make_record_output(n):
    return FfmpegOutput(f"-loglevel error {segment_path(n)}")

def make_stream_output():
    return FfmpegOutput(
        f"-loglevel error "
        f"-f mpegts "
        f"-muxdelay 0 "
        f"-muxpreload 0 "
        f"udp://{PI4_IP}:5000"
    )

picam2 = Picamera2()
config = picam2.create_video_configuration(
    main    ={"size": (1920, 1080)},
    lores   ={"size": (480, 270)},
    raw     =None,
    buffer_count=2,
    controls={"FrameDurationLimits": (33333, 33333)}
)
picam2.configure(config)

record_encoder = H264Encoder(bitrate=6000000, repeat=True, iperiod=15)
stream_encoder = H264Encoder(bitrate=600000,  repeat=True, iperiod=10)

picam2.start_recording(record_encoder, make_record_output(0), name="main")
picam2.start_recording(stream_encoder, make_stream_output(),  name="lores")
print("Recording + streaming started")

def rotate():
    global seg_num
    while recording:
        time.sleep(SEGMENT_SECS)
        if not recording:
            break
        completed = segment_path(seg_num)
        seg_num  += 1
        new_output = make_record_output(seg_num)
        record_encoder.output.stop()
        record_encoder.output = new_output
        record_encoder.output.start()
        record_encoder.force_key_frame()
        sync_queue.put(completed)
        print(f"Rotated — queued {completed}")

threading.Thread(target=rotate, daemon=True).start()

def rsync_loop():
    while recording or not sync_queue.empty():
        try:
            seg_path = sync_queue.get(timeout=5)
        except queue.Empty:
            continue
        if not os.path.exists(seg_path):
            print(f"rsync skipped — not found: {seg_path}")
            continue
        size_before = os.path.getsize(seg_path)
        time.sleep(0.5)
        size_after = os.path.getsize(seg_path)
        if size_before != size_after:
            sync_queue.put(seg_path)
            time.sleep(2)
            continue
        ret = os.system(
            f"rsync -avz --checksum --remove-source-files "
            f"{seg_path} pi@{PI4_IP}:/home/pi/received/"
        )
        if ret == 0:
            print(f"rsync OK — {os.path.basename(seg_path)}")
        else:
            print(f"rsync FAILED — {os.path.basename(seg_path)}")
            sync_queue.put(seg_path)

threading.Thread(target=rsync_loop, daemon=True).start()

try:
    input("Press Enter to stop...\n")
finally:
    recording = False
    picam2.stop_recording(name="main")
    picam2.stop_recording(name="lores")
    print("Stopped")
