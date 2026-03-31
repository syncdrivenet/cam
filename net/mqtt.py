import os
import json
import socket
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

NODE_ID = os.getenv("CLIENT_ID", socket.gethostname())
BROKER = os.getenv("MQTT_BROKER", "localhost")
PORT = int(os.getenv("MQTT_PORT", 1883))

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)


def publish(topic: str, payload: dict):
    full_topic = f"cam/node/{NODE_ID}/{topic}"
    client.publish(full_topic, json.dumps(payload))


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"[MQTT] connected to {BROKER}:{PORT}")


def start():
    client.on_connect = on_connect
    client.connect(BROKER, PORT)
    client.loop_start()
    print(f"[MQTT] connecting to {BROKER}:{PORT}...")
