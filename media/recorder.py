import os
import time
import queue
import threading
from dotenv import load_dotenv
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import PyavOutput, SplittableOutput
from core.state import state

load_dotenv()

SESSION_DIR = os.getenv("SESSION_DIR", "/home/pi/recordings")
BITRATE = int(os.getenv("RECORD_BITRATE", 6000000))
WIDTH = int(os.getenv("RECORD_WIDTH", 1920))
HEIGHT = int(os.getenv("RECORD_HEIGHT", 1080))
FPS = int(os.getenv("RECORD_FPS", 30))
SEGMENT_SECS = int(os.getenv("SEGMENT_SECS", 30))

os.makedirs(SESSION_DIR, exist_ok=True)

picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(
    main={"size": (WIDTH, HEIGHT)},
    controls={"FrameDurationLimits": (1000000 // FPS, 1000000 // FPS)}
))

encoder = H264Encoder(bitrate=BITRATE)
splitter = SplittableOutput()
command_queue = queue.Queue()


def path(n):
    return f"{SESSION_DIR}/seg_{n:04d}.mp4"


def _run():
    while True:
        start_at = command_queue.get()
        
        now_ms = int(time.time() * 1000)
        if start_at < now_ms:
            state.set_error("start_at is in the past")
            continue
        
        wait_secs = (start_at - now_ms) / 1000
        time.sleep(wait_secs)
        
        state.set_recording()
        
        splitter.split_output(PyavOutput(path(0)))
        picam2.start_recording(encoder, splitter, name="main")
        print("[RECORDER] Started")
        
        seg = 0
        while state.is_recording():
            time.sleep(SEGMENT_SECS)
            if not state.is_recording():
                break
            seg += 1
            state.set_segment(seg)
            splitter.split_output(PyavOutput(path(seg)))
            print(f"[RECORDER] Split to seg_{seg:04d}.mp4")
        
        picam2.stop_recording(name="main")
        state.set_idle()
        print("[RECORDER] Stopped")


threading.Thread(target=_run, daemon=True).start()


def start(start_at_ms: int):
    command_queue.put(start_at_ms)


def stop():
    state.set_idle()
