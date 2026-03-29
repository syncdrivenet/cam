import os
import socket
import uvicorn
from dotenv import load_dotenv

load_dotenv()

from state import state_manager
from preflight import run_preflight
from http_server import app
import mqtt_client

HTTP_PORT = int(os.getenv("HTTP_PORT", 8080))
NODE_ID = os.getenv("CLIENT_ID", socket.gethostname())


if __name__ == "__main__":
    print(f"[NODE] {NODE_ID} starting...")

    # connect to mqtt broker (background thread)
    mqtt_client.start()

    # run preflight checks
    run_preflight()
    print(f"[NODE] state: {state_manager.get_state()}")

    # start http server (blocks)
    print(f"[HTTP] listening on :{HTTP_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT, log_level="warning")
