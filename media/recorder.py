import os
import time
import threading
import queue
from dotenv import load_dotenv

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import PyavOutput, SplittableOutput

from core.events import Event, EventType
from lib.logger import log

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


# ------------------ PATH HELPERS ------------------
def _segment_path(session_uuid: str, seg: int, tmp: bool = True) -> str:
    """Generate path for segment file."""
    session_dir = os.path.join(SESSION_DIR, session_uuid)
    os.makedirs(session_dir, exist_ok=True)
    filename = f"_tmp_seg_{seg:04d}.mp4" if tmp else f"seg_{seg:04d}.mp4"
    return os.path.join(session_dir, filename)


def _finalize_segment(tmp_path: str, final_path: str, seg: int):
    """Rename tmp segment to final path."""
    if os.path.exists(tmp_path):
        os.rename(tmp_path, final_path)


# ------------------ WORKER ------------------
def run_worker(
    session_uuid: str,
    start_at: int,
    stop_signal: threading.Event,
    event_queue: queue.Queue
):
    """
    Recording worker thread.
    """
    try:
        # Wait until start time (interruptible)
        now_ms = int(time.time() * 1000)
        if start_at > now_ms:
            wait_secs = (start_at - now_ms) / 1000
            log("recording", f"Waiting {wait_secs:.1f}s until start", "INFO")
            if stop_signal.wait(timeout=wait_secs):
                log("recording", "Cancelled during wait", "WARN")
                return

        if stop_signal.is_set():
            log("recording", "Stop requested before start", "WARN")
            return

        log("recording", f"Recording started: {session_uuid}", "INFO")

        seg = 0
        tmp_path = _segment_path(session_uuid, seg, tmp=True)
        final_path = _segment_path(session_uuid, seg, tmp=False)

        splitter = SplittableOutput(output=PyavOutput(tmp_path))
        picam2.start_recording(encoder, splitter, name="main")

        log("recording", f"Segment {seg} started", "INFO")

        # Recording loop
        while not stop_signal.wait(timeout=SEGMENT_SECS):
            _finalize_segment(tmp_path, final_path, seg)

            event_queue.put(Event(
                type=EventType.SEGMENT_FINISHED,
                data={"segment": seg, "path": final_path, "uuid": session_uuid}
            ))

            seg += 1
            tmp_path = _segment_path(session_uuid, seg, tmp=True)
            final_path = _segment_path(session_uuid, seg, tmp=False)

            splitter.split_output(PyavOutput(tmp_path))
            log("recording", f"Segment {seg} started", "INFO")

        # Stop signal received
        log("recording", "Stopping recording", "INFO")
        picam2.stop_recording()

        _finalize_segment(tmp_path, final_path, seg)

        event_queue.put(Event(
            type=EventType.SEGMENT_FINISHED,
            data={"segment": seg, "path": final_path, "uuid": session_uuid}
        ))

        log("recording", f"Session complete: {session_uuid} ({seg+1} segments)", "INFO")

    except Exception as e:
        log("recording", f"Error: {e}", "ERROR")

    finally:
        event_queue.put(Event(
            type=EventType.RECORDING_STOPPED,
            data={"uuid": session_uuid}
        ))
