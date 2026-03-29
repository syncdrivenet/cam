import threading

class StateManager:
    def __init__(self):
        self._state = "idle"
        self._error_msg = ""
        self._lock = threading.Lock()

    def set_idle(self):
        with self._lock:
            self._state = "idle"
            self._error_msg = ""

    def set_preflight(self):
        with self._lock:
            self._state = "preflight"
            self._error_msg = ""

    def set_recording(self):
        with self._lock:
            self._state = "recording"
            self._error_msg = ""

    def set_finishing(self):
        with self._lock:
            self._state = "finishing"
            self._error_msg = ""

    def set_error(self, msg: str = ""):
        with self._lock:
            self._state = "error"
            self._error_msg = msg

    def get_state(self) -> str:
        with self._lock:
            return self._state

    def get_error(self) -> str:
        with self._lock:
            return self._error_msg

state_manager = StateManager()
