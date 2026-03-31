import os
import time
import queue
import threading
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

SYNC_ENABLED = os.getenv("SYNC_ENABLED", "true").lower() == "true"
SYNC_TARGET_HOST = os.getenv("SYNC_TARGET_HOST", "pi@172.20.10.2")
SYNC_TARGET_DIR = os.getenv("SYNC_TARGET_DIR", "/home/pi/received/")


class SyncManager:
    def __init__(self):
        self.sync_queue: queue.Queue = queue.Queue()
        self.running = False
        self._thread: Optional[threading.Thread] = None

    def queue_segment(self, segment_path: str):
        if SYNC_ENABLED:
            self.sync_queue.put(segment_path)
            print(f"[SYNC] Queued {os.path.basename(segment_path)}")

    def _sync_loop(self):
        while self.running or not self.sync_queue.empty():
            try:
                seg_path = self.sync_queue.get(timeout=5)
            except queue.Empty:
                continue

            if not os.path.exists(seg_path):
                print(f"[SYNC] Skipped (not found): {seg_path}")
                continue

            # Wait for file to finish writing
            size_before = os.path.getsize(seg_path)
            time.sleep(0.5)
            size_after = os.path.getsize(seg_path)

            if size_before != size_after:
                # File still being written, re-queue
                self.sync_queue.put(seg_path)
                time.sleep(2)
                continue

            ret = os.system(
                f"rsync -avz --checksum --remove-source-files "
                f"{seg_path} {SYNC_TARGET_HOST}:{SYNC_TARGET_DIR}"
            )

            if ret == 0:
                print(f"[SYNC] OK: {os.path.basename(seg_path)}")
            else:
                print(f"[SYNC] FAILED: {os.path.basename(seg_path)}")
                self.sync_queue.put(seg_path)

    def start(self):
        if not SYNC_ENABLED:
            print("[SYNC] Sync disabled")
            return

        self.running = True
        self._thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._thread.start()
        print(f"[SYNC] Started (target: {SYNC_TARGET_HOST}:{SYNC_TARGET_DIR})")

    def stop(self):
        self.running = False
        print("[SYNC] Stopping...")
