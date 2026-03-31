import os
from typing import Optional

from dotenv import load_dotenv
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput

load_dotenv()

STREAM_ENABLED = os.getenv("STREAM_ENABLED", "true").lower() == "true"
STREAM_TARGET_IP = os.getenv("STREAM_TARGET_IP", "172.20.10.2")
STREAM_TARGET_PORT = int(os.getenv("STREAM_TARGET_PORT", 5000))
STREAM_BITRATE = int(os.getenv("STREAM_BITRATE", 600000))


class Streamer:
    def __init__(self):
        self.picam2: Optional[Picamera2] = None
        self.stream_encoder: Optional[H264Encoder] = None
        self.streaming = False

    def _make_output(self) -> FfmpegOutput:
        return FfmpegOutput(
            f"-loglevel error "
            f"-f mpegts "
            f"-muxdelay 0 "
            f"-muxpreload 0 "
            f"udp://{STREAM_TARGET_IP}:{STREAM_TARGET_PORT}"
        )

    def start(self, picam2: Picamera2):
        if not STREAM_ENABLED:
            print("[STREAMER] Streaming disabled")
            return

        self.picam2 = picam2
        self.streaming = True

        self.stream_encoder = H264Encoder(
            bitrate=STREAM_BITRATE,
            repeat=True,
            iperiod=10
        )

        self.picam2.start_recording(
            self.stream_encoder,
            self._make_output(),
            name="lores"
        )
        print(f"[STREAMER] Streaming to udp://{STREAM_TARGET_IP}:{STREAM_TARGET_PORT}")

    def stop(self):
        if not self.streaming:
            return
        
        self.streaming = False
        if self.picam2:
            self.picam2.stop_recording(name="lores")
        print("[STREAMER] Streaming stopped")
