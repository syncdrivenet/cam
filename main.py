# main.py
import os
import socket
import threading
from dotenv import load_dotenv
from state import state_manager
from preflight import run_preflight
from http_server import start_http

load_dotenv()

HTTP_PORT = int(os.getenv("HTTP_PORT", 8080))
CLIENT_ID = os.getenv("CLIENT_ID", socket.gethostname())

if __name__ == "__main__":
    print(f"[INFO] Starting {CLIENT_ID}")

    # start HTTP server in background thread
    threading.Thread(target=start_http, args=(HTTP_PORT,), daemon=True).start()

    # run preflight on startup
    run_preflight()
    print(f"[INFO] State: {state_manager.get_state()}")

    # block main thread — MQTT will go here next
    threading.Event().wait()
