from typing import Literal
from pydantic import BaseModel
import threading

class PiState(BaseModel):
    state: Literal["ready", "preflight", "recording", "finishing", "error"]
    error_msg: str = ""

class StateManager:
    def __init__(self):
        self._state = PiState(state="ready")
        self._lock = threading.Lock()

    def set_ready(self):
        with self._lock:
            self._state = PiState(state="ready")

    def set_preflight(self):
        with self._lock:
            self._state = PiState(state="preflight")

    def set_recording(self):
        with self._lock:
            self._state = PiState(state="recording")

    def set_finishing(self):
        with self._lock:
            self._state = PiState(state="finishing")

    def set_error(self, msg: str = ""):
        with self._lock:
            self._state = PiState(state="error", error_msg=msg)

    def get_state(self) -> str:
        with self._lock:
            return self._state.state

    def get_error(self) -> str:
        with self._lock:
            return self._state.error_msg

state_manager = StateManager()
