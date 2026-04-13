import os
import socket
import time
import uvicorn
from dotenv import load_dotenv

load_dotenv()

from lib.logger import log
from core.state import state
from core.bootcheck import run_bootcheck
from core import event_loop
from net.http import app

HTTP_PORT = int(os.getenv("HTTP_PORT", 8080))
NODE_ID = os.getenv("CLIENT_ID", socket.gethostname())
BOOTCHECK_INTERVAL = int(os.getenv("BOOTCHECK_INTERVAL", 5))


if __name__ == "__main__":
    log("cam", f"Node {NODE_ID} starting", "INFO")

    # Run boot checks with retry
    while True:
        log("cam", "Running boot checks", "INFO")
        checks = run_bootcheck()

        failed = []
        for name, result in checks.items():
            status = "OK" if result["ok"] else "FAIL"
            print(f"  {name}: {status} - {result[msg]}")
            if not result["ok"]:
                failed.append(name)

        if not failed:
            log("cam", "Boot checks passed", "INFO")
            break

        log("cam", f"Boot checks failed: {', '.join(failed)}", "WARN")
        time.sleep(BOOTCHECK_INTERVAL)

    # Start event loop thread
    event_loop.start()
    log("cam", "Event loop started", "INFO")

    # Start HTTP server
    log("cam", f"HTTP server starting on :{HTTP_PORT}", "INFO")
    uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT, log_level="warning")
