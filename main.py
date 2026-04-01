import os
import socket
import time
import uvicorn
from dotenv import load_dotenv

load_dotenv()

from core.state import state
from core.bootcheck import run_bootcheck
from net.http import app

HTTP_PORT = int(os.getenv("HTTP_PORT", 8080))
NODE_ID = os.getenv("CLIENT_ID", socket.gethostname())
BOOTCHECK_INTERVAL = int(os.getenv("BOOTCHECK_INTERVAL", 5))


if __name__ == "__main__":
    print(f"[NODE] {NODE_ID} starting...")

    while True:
        print("[NODE] Running boot checks...")
        checks = run_bootcheck()
        
        for name, result in checks.items():
            status = "OK" if result["ok"] else "FAIL"
            print(f"[NODE]   {name}: {status} - {result['msg']}")
        
        if all(c["ok"] for c in checks.values()):
            print("[NODE] Boot checks passed")
            break
        
        print(f"[NODE] Retrying in {BOOTCHECK_INTERVAL}s...")
        time.sleep(BOOTCHECK_INTERVAL)

    print(f"[NODE] state: {state.get()['state']}")
    print(f"[HTTP] listening on :{HTTP_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT, log_level="warning")
