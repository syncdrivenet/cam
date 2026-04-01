import threading


class StateManager:
    """Thread-safe state manager. Only modified by event loop."""

    def __init__(self):
        self._lock = threading.Lock()
        self._state = "idle"
        self._segment = None
        self._error_msg = None

    # ------------------ STATE SETTERS ------------------
    def set_idle(self):
        with self._lock:
            self._state = "idle"
            self._segment = None
            self._error_msg = None

    def set_recording(self):
        with self._lock:
            self._state = "recording"
            self._segment = 0
            self._error_msg = None

    def set_cleanup(self):
        with self._lock:
            self._state = "cleanup"

    def set_segment(self, n: int):
        with self._lock:
            self._segment = n

    def set_error(self, msg: str):
        with self._lock:
            self._state = "error"
            self._error_msg = msg

    # ------------------ STATE GETTERS ------------------
    def get(self) -> dict:
        with self._lock:
            return {
                "state": self._state,
                "segment": self._segment,
                "error": self._error_msg,
            }

    def is_recording(self) -> bool:
        with self._lock:
            return self._state == "recording"

    def is_idle(self) -> bool:
        with self._lock:
            return self._state == "idle"


# Singleton instance
state = StateManager()
