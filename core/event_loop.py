import queue
import threading

from core.events import Event, EventType
from core.state import state
from lib.logger import log

# Global event queue - thread-safe FIFO
event_queue: queue.Queue[Event] = queue.Queue()

# Stop signal for current recording worker
_worker_stop_signal: threading.Event = None
_worker_thread: threading.Thread = None


def _handle_start_recording(event: Event):
    """Handle START_RECORDING event."""
    global _worker_stop_signal, _worker_thread

    if state.get()["state"] != "idle":
        log("recording", "Ignoring START_RECORDING: not idle", "WARN")
        return

    # Import here to avoid circular import
    from media.recorder import run_worker

    session_uuid = event.data.get("uuid")
    start_at = event.data.get("start_at")

    log("recording", f"Session starting: {session_uuid}", "INFO")
    state.set_recording()

    # Create stop signal for this worker
    _worker_stop_signal = threading.Event()

    # Spawn worker thread
    _worker_thread = threading.Thread(
        target=run_worker,
        args=(session_uuid, start_at, _worker_stop_signal, event_queue),
        daemon=True
    )
    _worker_thread.start()


def _handle_stop_recording(event: Event):
    """Handle STOP_RECORDING event."""
    global _worker_stop_signal

    if state.get()["state"] != "recording":
        log("recording", "Ignoring STOP_RECORDING: not recording", "WARN")
        return

    log("recording", "Stop signal sent", "INFO")
    if _worker_stop_signal:
        _worker_stop_signal.set()


def _handle_segment_finished(event: Event):
    """Handle SEGMENT_FINISHED event."""
    segment = event.data.get("segment", 0)
    log("recording", f"Segment {segment} complete", "INFO")
    state.set_segment(segment)


def _handle_recording_stopped(event: Event):
    """Handle RECORDING_STOPPED event."""
    global _worker_stop_signal, _worker_thread

    session_uuid = event.data.get("uuid", "unknown")
    log("recording", f"Session stopped: {session_uuid}", "INFO")

    state.set_cleanup()
    state.set_idle()

    _worker_stop_signal = None
    _worker_thread = None


def _loop():
    """Main event loop - single source of truth for state transitions."""
    log("recording", "Event loop started", "INFO")

    handlers = {
        EventType.START_RECORDING: _handle_start_recording,
        EventType.STOP_RECORDING: _handle_stop_recording,
        EventType.SEGMENT_FINISHED: _handle_segment_finished,
        EventType.RECORDING_STOPPED: _handle_recording_stopped,
    }

    while True:
        event = event_queue.get()
        handler = handlers.get(event.type)

        if handler:
            try:
                handler(event)
            except Exception as e:
                log("recording", f"Error handling {event.type}: {e}", "ERROR")
                state.set_error(str(e))
        else:
            log("recording", f"Unknown event type: {event.type}", "WARN")


def start():
    """Start the event loop thread."""
    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    return thread
