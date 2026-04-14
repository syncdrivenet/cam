"""Rsync manager with status tracking for segment upload."""

import os
import time
import queue
import threading
from typing import Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

from lib.logger import log

load_dotenv()

SYNC_ENABLED = os.getenv("SYNC_ENABLED", "true").lower() == "true"
SYNC_TARGET_HOST = os.getenv("SYNC_TARGET_HOST", "pi@melb-01-ctlr")
SYNC_TARGET_DIR = os.getenv("SYNC_TARGET_DIR", "/mnt/logging")


@dataclass
class SyncStatus:
    """Current sync status."""
    status: str = "idle"  # idle, syncing
    last_sync_ts: Optional[int] = None  # unix timestamp ms
    segments_synced: int = 0
    segments_queued: int = 0
    current_segment: Optional[str] = None
    current_uuid: Optional[str] = None
    last_error: Optional[str] = None


class SyncManager:
    """Manages rsync of video segments to controller with status tracking."""

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._status = SyncStatus()
        self._node_id = os.getenv("CLIENT_ID", os.uname().nodename)

    def get_status(self) -> dict:
        """Get current sync status for API."""
        with self._lock:
            return {
                "status": self._status.status,
                "last_sync": self._status.last_sync_ts,
                "segments_synced": self._status.segments_synced,
                "segments_queued": self._queue.qsize(),
                "current_segment": self._status.current_segment,
                "error": self._status.last_error,
            }

    def queue_segment(self, segment_path: str, uuid: str):
        """Queue a segment for sync."""
        if not SYNC_ENABLED:
            return

        self._queue.put((segment_path, uuid))
        with self._lock:
            self._status.current_uuid = uuid
        log("sync", f"Queued: {os.path.basename(segment_path)}", "DEBUG")

    def _sync_loop(self):
        """Background sync loop."""
        while self._running or not self._queue.empty():
            try:
                seg_path, uuid = self._queue.get(timeout=5)
            except queue.Empty:
                continue

            if not os.path.exists(seg_path):
                log("sync", f"Skipped (not found): {seg_path}", "WARN")
                continue

            # Wait for file to finish writing
            size_before = os.path.getsize(seg_path)
            time.sleep(0.5)
            size_after = os.path.getsize(seg_path)

            if size_before != size_after:
                # File still being written, re-queue
                self._queue.put((seg_path, uuid))
                time.sleep(2)
                continue

            # Update status to syncing
            seg_name = os.path.basename(seg_path)
            with self._lock:
                self._status.status = "syncing"
                self._status.current_segment = seg_name

            log("sync", f"Syncing: {seg_name}", "INFO")

            # Build target path: /mnt/logging/{node_id}/{uuid}/
            target_dir = f"{SYNC_TARGET_HOST}:{SYNC_TARGET_DIR}/{self._node_id}/{uuid}/"
            
            ret = os.system(
                f"rsync -avz --checksum --timeout=60 "
                f"--rsync-path='mkdir -p {SYNC_TARGET_DIR}/{self._node_id}/{uuid} && rsync' "
                f"{seg_path} {target_dir} 2>/dev/null"
            )

            if ret == 0:
                log("sync", f"OK: {seg_name}", "INFO")
                with self._lock:
                    self._status.segments_synced += 1
                    self._status.last_sync_ts = int(time.time() * 1000)
                    self._status.last_error = None
                    
                # Remove local file after successful sync
                try:
                    os.remove(seg_path)
                except Exception as e:
                    log("sync", f"Failed to remove {seg_name}: {e}", "WARN")
            else:
                log("sync", f"FAILED: {seg_name} (ret={ret})", "ERROR")
                with self._lock:
                    self._status.last_error = f"rsync failed (code {ret})"
                # Re-queue for retry
                self._queue.put((seg_path, uuid))
                time.sleep(5)  # Wait before retry

            # Update status back to idle if queue empty
            with self._lock:
                if self._queue.empty():
                    self._status.status = "idle"
                    self._status.current_segment = None

    def start(self):
        """Start the sync manager."""
        if not SYNC_ENABLED:
            log("sync", "Sync disabled", "INFO")
            return

        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._thread.start()
        log("sync", f"Started (target: {SYNC_TARGET_HOST}:{SYNC_TARGET_DIR})", "INFO")

    def stop(self):
        """Stop the sync manager (waits for queue to drain)."""
        self._running = False
        log("sync", "Stopping (draining queue)...", "INFO")

    def reset(self):
        """Reset sync stats for new session."""
        with self._lock:
            self._status.segments_synced = 0
            self._status.current_uuid = None
            self._status.last_error = None
            self._status.status = "idle"
            self._status.current_segment = None


# Singleton instance
sync_manager = SyncManager()
