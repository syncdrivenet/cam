import os
import time
import queue
import threading
from dotenv import load_dotenv

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import PyavOutput, SplittableOutput
from core.state import state

# ------------------ CONFIG ------------------
load_dotenv()
SESSION_DIR = os.getenv("SESSION_DIR", "/home/pi/recordings")
BITRATE = int(os.getenv("RECORD_BITRATE", 6000000))
WIDTH = int(os.getenv("RECORD_WIDTH", 1280))
HEIGHT = int(os.getenv("RECORD_HEIGHT", 720))
FPS = int(os.getenv("RECORD_FPS", 30))
SEGMENT_SECS = int(os.getenv("SEGMENT_SECS", 30))

# ------------------ CAMERA SETUP ------------------
os.makedirs(SESSION_DIR, exist_ok=True)
picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(
    main={"size": (WIDTH, HEIGHT)},
    controls={
        "FrameDurationLimits": (1_000_000 // FPS, 1_000_000 // FPS)
    }
))
encoder = H264Encoder(bitrate=BITRATE)

# ------------------ STATE & COMMANDS ------------------
commands = queue.Queue()
_started = False  # ensures loop thread only starts once

# ------------------ PATH HELPERS ------------------
def _segment_path(session_uuid, seg, tmp=True):
    session_dir = os.path.join(SESSION_DIR, session_uuid)
    os.makedirs(session_dir, exist_ok=True)
    filename = f"seg_{seg:04d}"
    if tmp:
        filename = f"_tmp_{filename}.mp4"  # valid container
    else:
        filename = f"{filename}.mp4"
    return os.path.join(session_dir, filename)

# ------------------ SEGMENT HELPERS ------------------
def _start_segment(splitter, session_uuid, seg):
    """Start a new segment and split output."""
    curr_path = _segment_path(session_uuid, seg, tmp=True)
    final_path = _segment_path(session_uuid, seg, tmp=False)
    splitter.split_output(PyavOutput(curr_path))
    print(f"[RECORDER] Started segment {seg}")
    return curr_path, final_path

def _finalize_segment(curr_path, final_path, seg):
    """Rename TMP segment to final .mp4 file."""
    if os.path.exists(curr_path):
        os.rename(curr_path, final_path)
        print(f"[RECORDER] Finalized segment {seg} → {final_path}")

# ------------------ MAIN RECORDING LOOP ------------------
def _loop():
    while True:
        start_at, session_uuid = commands.get()

        # Wait until start time
        now = int(time.time() * 1000)
        if start_at > now:
            time.sleep((start_at - now) / 1000)

        # Start recording
        state.set_recording()
        seg = 0

        splitter = SplittableOutput(output=PyavOutput(_segment_path(session_uuid, seg, tmp=True)))
        picam2.start_recording(encoder, splitter, name="main")
        print(f"[RECORDER] Started session {session_uuid}")

        curr_path, final_path = _start_segment(splitter, session_uuid, seg)

        # Recording loop, split segments every SEGMENT_SECS or until stop
        while not state.wait_stop(timeout=SEGMENT_SECS):
            _finalize_segment(curr_path, final_path, seg)
            seg += 1
            state.set_segment(seg)
            curr_path, final_path = _start_segment(splitter, session_uuid, seg)

        # Stop requested → cleanup
        state.set_cleanup()
        picam2.stop_recording()
        _finalize_segment(curr_path, final_path, seg)
        state.set_idle()
        print(f"[RECORDER] Stopped session {session_uuid}")

# ------------------ API TO START / STOP ------------------
def start(start_at_ms: int, session_uuid: str):
    """Queue a recording session to start at a given timestamp."""
    global _started
    if not _started:
        threading.Thread(target=_loop, daemon=True).start()
        _started = True
    commands.put((start_at_ms, session_uuid))

def stop():
    """Signal the current recording to stop."""
    state.stop_recording()
