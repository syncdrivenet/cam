import threading

class StateManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = "idle"       # "idle", "recording", "cleanup"
        self._segment = None
        self._stop_event = threading.Event()
        self._cleanup_event = threading.Event()

    # ------------------ STATE SETTERS ------------------
    def set_idle(self):
        with self._lock:
            self._state = "idle"
            self._segment = None
            self._stop_event.clear()
            self._cleanup_event.clear()

    def set_preflight(self):
        with self._lock:
            self._state = "preflight"

    def set_recording(self):
        with self._lock:
            self._state = "recording"
            self._segment = 0
            self._stop_event.clear()
            self._cleanup_event.clear()

    def set_segment(self, n: int):
        with self._lock:
            self._segment = n

    def stop_recording(self):
        """Signal recording should stop (called by stop API)."""
        self._stop_event.set()
        # do not set idle yet; cleanup may be in progress

    def set_cleanup(self):
        """Set state to cleanup while finalizing files."""
        with self._lock:
            self._state = "cleanup"
            self._cleanup_event.set()

    # ------------------ STATE CHECKERS ------------------
    def is_recording(self) -> bool:
        with self._lock:
            return self._state == "recording"

    def is_cleanup(self) -> bool:
        with self._lock:
            return self._state == "cleanup"

    def get(self) -> dict:
        with self._lock:
            return {
                "state": self._state,
                "segment": self._segment
            }

    # ------------------ WAIT UTILS ------------------
    def wait_stop(self, timeout=None) -> bool:
        """Wait until stop is requested. Returns True if stop triggered."""
        return self._stop_event.wait(timeout=timeout)

    def wait_cleanup(self, timeout=None) -> bool:
        """Wait until cleanup is started. Returns True if cleanup triggered."""
        return self._cleanup_event.wait(timeout=timeout)


# Singleton instance
state = StateManager()
