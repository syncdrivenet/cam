from enum import Enum, auto
from dataclasses import dataclass
from typing import Any


class EventType(Enum):
    START_RECORDING = auto()
    STOP_RECORDING = auto()
    SEGMENT_FINISHED = auto()
    RECORDING_STOPPED = auto()


@dataclass
class Event:
    type: EventType
    data: dict = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}
