import threading


class StateManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = "idle"
        self._error = None
        self._segment = None

    def set_idle(self):
        with self._lock:
            self._state = "idle"
            self._error = None
            self._segment = None

    def set_preflight(self):
        with self._lock:
            self._state = "preflight"
            self._error = None

    def set_recording(self):
        with self._lock:
            self._state = "recording"
            self._error = None
            self._segment = 0

    def set_error(self, msg: str):
        with self._lock:
            self._state = "error"
            self._error = msg

    def set_segment(self, n: int):
        with self._lock:
            self._segment = n

    def is_recording(self) -> bool:
        with self._lock:
            return self._state == "recording"

    def get(self) -> dict:
        with self._lock:
            return {
                "state": self._state,
                "error": self._error,
                "segment": self._segment
            }


state = StateManager()
