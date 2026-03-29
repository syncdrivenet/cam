#!/usr/bin/env python3
"""
Test script for Pi Camera REST API.

Usage:
    python test_api.py                    # Test single camera
    python test_api.py --cameras cam1 cam2  # Test multiple cameras
    python test_api.py --sync             # Test synchronized start
"""

import argparse
import asyncio
import time
import uuid
from datetime import datetime

import httpx

DEFAULT_CAMERAS = ["melb-01-cam-01"]
DEFAULT_PORT = 8080
TIMEOUT = 10.0


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {msg}")


async def get_status(client: httpx.AsyncClient, cam: str, port: int) -> dict:
    """Get camera status."""
    url = f"http://{cam}:{port}/status"
    resp = await client.get(url, timeout=TIMEOUT)
    return resp.json()


async def run_preflight(client: httpx.AsyncClient, cam: str, port: int) -> dict:
    """Run preflight checks."""
    url = f"http://{cam}:{port}/preflight"
    resp = await client.get(url, timeout=TIMEOUT)
    return resp.json()


async def start_recording(
    client: httpx.AsyncClient,
    cam: str,
    port: int,
    session_uuid: str,
    timestamp: int | None = None,
) -> dict:
    """Start recording."""
    url = f"http://{cam}:{port}/record/start"
    body = {"uuid": session_uuid}
    if timestamp:
        body["timestamp"] = timestamp
    resp = await client.post(url, json=body, timeout=TIMEOUT)
    return resp.json()


async def stop_recording(client: httpx.AsyncClient, cam: str, port: int) -> dict:
    """Stop recording."""
    url = f"http://{cam}:{port}/record/stop"
    resp = await client.post(url, timeout=TIMEOUT)
    return resp.json()


async def test_single_camera(cam: str, port: int, record_duration: int = 10):
    """Test a single camera through all operations."""
    log(f"Testing camera: {cam}")

    async with httpx.AsyncClient() as client:
        # 1. Check status
        log(f"[{cam}] Getting status...")
        status = await get_status(client, cam, port)
        log(f"[{cam}] Status: state={status['state']}, cpu={status['system']['cpu']}%")

        # 2. Run preflight
        log(f"[{cam}] Running preflight...")
        preflight = await run_preflight(client, cam, port)
        log(f"[{cam}] Preflight: ok={preflight['ok']}")
        for check, result in preflight["checks"].items():
            status_icon = "✓" if result["ok"] else "✗"
            log(f"[{cam}]   {status_icon} {check}: {result['msg']}")

        if not preflight["ok"]:
            log(f"[{cam}] Preflight failed, skipping recording test")
            return False

        # 3. Start recording
        session_uuid = f"test-{uuid.uuid4().hex[:8]}"
        log(f"[{cam}] Starting recording (uuid={session_uuid})...")
        start_result = await start_recording(client, cam, port, session_uuid)
        log(f"[{cam}] Start result: {start_result}")

        if not start_result.get("ok"):
            log(f"[{cam}] Failed to start recording: {start_result.get('error')}")
            return False

        # 4. Check status while recording
        await asyncio.sleep(2)
        status = await get_status(client, cam, port)
        log(f"[{cam}] Status while recording: state={status['state']}")
        if status.get("recording", {}).get("recording"):
            log(f"[{cam}]   duration={status['recording']['duration']:.1f}s")

        # 5. Wait then stop
        log(f"[{cam}] Recording for {record_duration}s...")
        await asyncio.sleep(record_duration - 2)

        log(f"[{cam}] Stopping recording...")
        stop_result = await stop_recording(client, cam, port)
        log(f"[{cam}] Stop result: {stop_result}")

        if stop_result.get("ok"):
            log(f"[{cam}] Recording saved: {stop_result.get('output_dir')}")
            log(f"[{cam}] Duration: {stop_result.get('duration', 0):.1f}s")

        # 6. Final status
        status = await get_status(client, cam, port)
        log(f"[{cam}] Final status: state={status['state']}")

        return True


async def test_preflight_all(cameras: list[str], port: int) -> dict[str, bool]:
    """Run preflight on all cameras in parallel."""
    log(f"Running preflight on {len(cameras)} camera(s)...")

    async with httpx.AsyncClient() as client:
        tasks = [run_preflight(client, cam, port) for cam in cameras]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    status = {}
    for cam, result in zip(cameras, results):
        if isinstance(result, Exception):
            log(f"[{cam}] Preflight error: {result}")
            status[cam] = False
        else:
            ok = result.get("ok", False)
            log(f"[{cam}] Preflight: {'PASS' if ok else 'FAIL'}")
            status[cam] = ok

    return status


async def test_synchronized_start(
    cameras: list[str], port: int, record_duration: int = 10
):
    """Test synchronized recording start across multiple cameras."""
    log(f"Testing synchronized start on {len(cameras)} camera(s)")

    async with httpx.AsyncClient() as client:
        # 1. Preflight all
        preflight_status = await test_preflight_all(cameras, port)

        ready_cameras = [cam for cam, ok in preflight_status.items() if ok]
        if len(ready_cameras) < len(cameras):
            failed = [cam for cam, ok in preflight_status.items() if not ok]
            log(f"Warning: {len(failed)} camera(s) failed preflight: {failed}")

        if not ready_cameras:
            log("No cameras ready, aborting")
            return

        # 2. Calculate start timestamp (3 seconds from now)
        start_timestamp = int((time.time() + 3) * 1000)
        session_uuid = f"sync-{uuid.uuid4().hex[:8]}"
        log(f"Session UUID: {session_uuid}")
        log(f"Scheduled start: {datetime.fromtimestamp(start_timestamp/1000).strftime('%H:%M:%S.%f')[:-3]}")

        # 3. Send start command to all cameras
        log("Sending start commands...")
        tasks = [
            start_recording(client, cam, port, session_uuid, start_timestamp)
            for cam in ready_cameras
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for cam, result in zip(ready_cameras, results):
            if isinstance(result, Exception):
                log(f"[{cam}] Start error: {result}")
            else:
                log(f"[{cam}] Start result: {result}")

        # 4. Wait for recording to start
        await asyncio.sleep(4)

        # 5. Check status on all
        log("Checking recording status...")
        tasks = [get_status(client, cam, port) for cam in ready_cameras]
        statuses = await asyncio.gather(*tasks, return_exceptions=True)

        for cam, status in zip(ready_cameras, statuses):
            if isinstance(status, Exception):
                log(f"[{cam}] Status error: {status}")
            else:
                state = status.get("state", "unknown")
                rec = status.get("recording", {})
                log(f"[{cam}] State: {state}, recording: {rec.get('recording', False)}")

        # 6. Record for duration
        log(f"Recording for {record_duration}s...")
        await asyncio.sleep(record_duration)

        # 7. Stop all
        log("Stopping all recordings...")
        tasks = [stop_recording(client, cam, port) for cam in ready_cameras]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for cam, result in zip(ready_cameras, results):
            if isinstance(result, Exception):
                log(f"[{cam}] Stop error: {result}")
            else:
                log(f"[{cam}] Stopped: duration={result.get('duration', 0):.1f}s")


async def main():
    parser = argparse.ArgumentParser(description="Test Pi Camera REST API")
    parser.add_argument(
        "--cameras",
        nargs="+",
        default=DEFAULT_CAMERAS,
        help="Camera hostnames",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="HTTP port",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Test synchronized start",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Only run preflight checks",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="Recording duration in seconds",
    )
    args = parser.parse_args()

    log(f"Cameras: {args.cameras}")
    log(f"Port: {args.port}")
    print("-" * 50)

    try:
        if args.preflight_only:
            await test_preflight_all(args.cameras, args.port)
        elif args.sync:
            await test_synchronized_start(args.cameras, args.port, args.duration)
        elif len(args.cameras) == 1:
            await test_single_camera(args.cameras[0], args.port, args.duration)
        else:
            # Multiple cameras without sync - test each sequentially
            for cam in args.cameras:
                await test_single_camera(cam, args.port, args.duration)
                print("-" * 50)
    except httpx.ConnectError as e:
        log(f"Connection error: {e}")
        log("Is the camera running and reachable?")
    except KeyboardInterrupt:
        log("Interrupted")


if __name__ == "__main__":
    asyncio.run(main())
