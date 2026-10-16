import paho.mqtt.client as mqtt

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[SUCCESS] Connected to HiveMQ Broker!")
    else:
        print(f"[ERROR] Failed with code {rc}")

client = mqtt.Client(client_id="test_client")
client.on_connect = on_connect
client.connect("broker.hivemq.com", 1883, 60)
client.loop_start()
import time; time.sleep(2)
client.loop_stop()
client.disconnect()
