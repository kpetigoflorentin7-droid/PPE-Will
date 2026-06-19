"""
Client MQTT — le pont entre Django (sur le PC) et les ESP32.

Le PC fait tourner le broker Mosquitto (ou se connecte à un broker
distant). Ce module publie les ordres ("allume", "éteins"...) sur le
topic MQTT de l'appareil concerné. C'est l'équivalent logiciel du fil
qui relie Will à la lampe.
"""
import json
import threading
import paho.mqtt.client as mqtt
from django.conf import settings

_client = None
_lock = threading.Lock()


def _on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("✅ MQTT connecté au broker", settings.MQTT_BROKER_HOST)
    else:
        print(f"❌ MQTT connexion refusée (code {rc})")


def _on_disconnect(client, userdata, rc, properties=None):
    print(f"⚠️ MQTT déconnecté (code {rc})")


def get_client():
    """Retourne un client MQTT connecté, en le créant si besoin (singleton)."""
    global _client
    with _lock:
        if _client is not None:
            return _client
        client = mqtt.Client(client_id="will_django_server")
        if getattr(settings, "MQTT_USERNAME", None):
            client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
        client.on_connect = _on_connect
        client.on_disconnect = _on_disconnect
        try:
            client.connect(
                settings.MQTT_BROKER_HOST,
                settings.MQTT_BROKER_PORT,
                keepalive=30,
            )
            client.loop_start()  # thread d'arrière-plan, ne bloque pas Django
        except Exception as e:
            print(f"❌ Impossible de se connecter au broker MQTT : {e}")
        _client = client
        return _client


def publish_command(topic: str, payload: dict) -> bool:
    """
    Publie un ordre JSON sur un topic MQTT.
    Exemple : publish_command("will/salon/lumiere", {"action": "on"})
    Retourne True si la publication a été envoyée, False sinon.
    """
    if not topic:
        print("⚠️ Aucun topic_mqtt défini pour cet appareil.")
        return False
    try:
        client = get_client()
        result = client.publish(topic, json.dumps(payload), qos=1)
        return result.rc == mqtt.MQTT_ERR_SUCCESS
    except Exception as e:
        print(f"❌ Erreur de publication MQTT sur {topic} : {e}")
        return False
