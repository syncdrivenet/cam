import os
import json
import socket
import paho.mqtt.client as mqtt
from state import state_manager

NODE_ID = os.getenv("CLIENT_ID", socket.gethostname())
BROKER = os.getenv("MQTT_BROKER", "localhost")
PORT = int(os.getenv("MQTT_PORT", 1883))

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)


# --- publish helpers ---

def publish(topic: str, payload: dict):
    full_topic = f"cam/node/{NODE_ID}/{topic}"
    client.publish(full_topic, json.dumps(payload))


def ack(cmd_id: str, cmd: str, ok: bool, error: str = None):
    publish("ack", {
        "id": cmd_id,
        "cmd": cmd,
        "ok": ok,
        "error": error
    })


def publish_state():
    publish("state", {
        "state": state_manager.get_state(),
        "error": state_manager.get_error()
    })


# --- command handlers ---

def handle_start(cmd_id: str, payload: dict):
    start_at = payload.get("start_at")
    # TODO: schedule recording at start_at
    print(f"[MQTT] start at {start_at}")
    state_manager.set_recording()
    ack(cmd_id, "start", ok=True)
    publish_state()


def handle_stop(cmd_id: str, payload: dict):
    # TODO: stop recording
    print("[MQTT] stop")
    state_manager.set_idle()
    ack(cmd_id, "stop", ok=True)
    publish_state()


def handle_preflight(cmd_id: str, payload: dict):
    from preflight import run_preflight
    checks = run_preflight()
    ok = all(c["ok"] for c in checks.values())
    ack(cmd_id, "preflight", ok=ok, error=None if ok else "preflight failed")
    publish_state()


HANDLERS = {
    "cam/cmd/start": handle_start,
    "cam/cmd/stop": handle_stop,
    "cam/cmd/preflight": handle_preflight,
}


# --- mqtt callbacks ---

def on_connect(client, userdata, flags, reason_code, properties):
    print(f"[MQTT] connected to {BROKER}:{PORT}")
    client.subscribe("cam/cmd/#")
    publish_state()


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload)
        cmd_id = payload.get("id", "")
        handler = HANDLERS.get(msg.topic)
        if handler:
            handler(cmd_id, payload)
    except Exception as e:
        print(f"[MQTT] error: {e}")


# --- start ---

def start():
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT)
    client.loop_start()
    print(f"[MQTT] connecting to {BROKER}:{PORT}...")
