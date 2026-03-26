# http_server.py
import json
import shutil
import http.server
import psutil
from state import state_manager
from preflight import run_preflight

class Handler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/status":
            body = json.dumps({
                "state":     state_manager.get_state(),
                "error_msg": state_manager.get_error(),
                "system": {
                    "cpu":       psutil.cpu_percent(interval=0.5),
                    "ram":       psutil.virtual_memory().percent,
                    "disk_free": round(shutil.disk_usage("/").free / (1024**3), 2),
                }
            }, indent=2).encode()

        elif self.path == "/preflight":
            body = json.dumps(run_preflight(), indent=2).encode()

        else:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # silence default HTTP logs

def start_http(port: int):
    server = http.server.HTTPServer(("0.0.0.0", port), Handler)
    print(f"[HTTP] Listening on :{port}")
    server.serve_forever()
