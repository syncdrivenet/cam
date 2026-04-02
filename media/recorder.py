import os
import time
import threading
import queue
from dotenv import load_dotenv

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import PyavOutput, SplittableOutput

from core.events import Event, EventType

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
        print(f"[RECORDER] Finalized segment {seg} -> {final_path}")


# ------------------ WORKER ------------------
def run_worker(
    session_uuid: str,
    start_at: int,
    stop_signal: threading.Event,
    event_queue: queue.Queue
):
    """
    Recording worker thread.
    
    - Waits until start_at timestamp (interruptible by stop signal)
    - Records video, splitting into segments
    - Emits SEGMENT_FINISHED events
    - Emits RECORDING_STOPPED when done
    - Does NOT modify state directly
    """
    try:
        # Wait until start time (interruptible)
        now_ms = int(time.time() * 1000)
        if start_at > now_ms:
            wait_secs = (start_at - now_ms) / 1000
            print(f"[RECORDER] Waiting {wait_secs:.1f}s until start")
            # Use stop_signal.wait() instead of time.sleep() so we can be interrupted
            if stop_signal.wait(timeout=wait_secs):
                print(f"[RECORDER] Cancelled during wait")
                return  # Stop signal received during wait, exit without recording

        # Check again in case stop was called
        if stop_signal.is_set():
            print(f"[RECORDER] Stop requested before recording started")
            return

        print(f"[RECORDER] Starting session {session_uuid}")

        seg = 0
        tmp_path = _segment_path(session_uuid, seg, tmp=True)
        final_path = _segment_path(session_uuid, seg, tmp=False)

        splitter = SplittableOutput(output=PyavOutput(tmp_path))
        picam2.start_recording(encoder, splitter, name="main")

        print(f"[RECORDER] Started segment {seg}")

        # Recording loop
        while not stop_signal.wait(timeout=SEGMENT_SECS):
            # Segment timeout reached, finalize and start new segment
            _finalize_segment(tmp_path, final_path, seg)

            # Emit segment finished event
            event_queue.put(Event(
                type=EventType.SEGMENT_FINISHED,
                data={"segment": seg, "path": final_path, "uuid": session_uuid}
            ))

            seg += 1
            tmp_path = _segment_path(session_uuid, seg, tmp=True)
            final_path = _segment_path(session_uuid, seg, tmp=False)

            splitter.split_output(PyavOutput(tmp_path))
            print(f"[RECORDER] Started segment {seg}")

        # Stop signal received
        print(f"[RECORDER] Stop signal received, cleaning up")
        picam2.stop_recording()

        # Finalize last segment
        _finalize_segment(tmp_path, final_path, seg)

        # Emit final segment finished
        event_queue.put(Event(
            type=EventType.SEGMENT_FINISHED,
            data={"segment": seg, "path": final_path, "uuid": session_uuid}
        ))

        print(f"[RECORDER] Session {session_uuid} complete")

    except Exception as e:
        print(f"[RECORDER] Error: {e}")

    finally:
        # Always emit recording stopped
        event_queue.put(Event(
            type=EventType.RECORDING_STOPPED,
            data={"uuid": session_uuid}
        ))
