# api_assistant/mqtt_client.py
# ─────────────────────────────────────────────────────────────────────────────
# Client MQTT central de WILL.
#
# Deux usages distincts :
#
#   1. PUBLICATION (depuis les vues Django, requête web normale)
#      → publish_command(appareil, commande, params)
#      Ouvre une connexion courte, publie, se déconnecte. Pas besoin de
#      process persistant pour ça.
#
#   2. ÉCOUTE (depuis la commande `manage.py run_mqtt`, process séparé qui
#      tourne en permanence sur le Raspberry Pi)
#      → start_listening()
#      S'abonne à home/+/+/etat (état remonté par tous les ESP32) et met à
#      jour EtatAppareil en base à chaque message reçu.
#
# Topics utilisés :
#   Commande (Django → ESP32)  : home/<esp32_id>/<canal>/commande
#   État     (ESP32 → Django)  : home/<esp32_id>/<canal>/etat
# ─────────────────────────────────────────────────────────────────────────────

import json
import logging

import paho.mqtt.client as mqtt
from django.conf import settings

logger = logging.getLogger("will.mqtt")

MQTT_HOST       = getattr(settings, "MQTT_BROKER_HOST", "localhost")
MQTT_PORT       = getattr(settings, "MQTT_BROKER_PORT", 1883)
MQTT_USER       = getattr(settings, "MQTT_USERNAME", None)
MQTT_PASSWORD   = getattr(settings, "MQTT_PASSWORD", None)
MQTT_KEEPALIVE  = getattr(settings, "MQTT_KEEPALIVE", 60)


def _build_client(client_id: str) -> mqtt.Client:
    # paho-mqtt >= 2.0 exige callback_api_version. VERSION1 conserve les
    # anciennes signatures de callbacks (on_connect(client, userdata, flags, rc)),
    # ce qui évite de réécrire les callbacks plus bas.
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
        client_id=client_id,
        protocol=mqtt.MQTTv311,
    )
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    return client


# ═══════════════════════════════════════════════════════════════════════════
#  1. PUBLICATION — appelée depuis les vues (requête HTTP classique)
# ═══════════════════════════════════════════════════════════════════════════

def publish_command(appareil, commande: str, params: dict) -> bool:
    """
    Publie une commande vers l'ESP32 responsable de cet appareil.
    Retourne True si la publication a réussi (ne garantit pas que l'ESP32
    l'a reçue — pour ça, voir l'accusé de réception dans EtatAppareil,
    mis à jour quand l'ESP32 republie son état).
    """
    topic = appareil.topic_mqtt
    if not topic:
        logger.warning("Appareil %s sans topic_mqtt — commande ignorée.", appareil.nom)
        return False

    payload = json.dumps({"cmd": commande, **params})

    try:
        client = _build_client(client_id=f"will-django-pub-{appareil.id}")
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=MQTT_KEEPALIVE)
        client.loop_start()
        info = client.publish(topic, payload=payload, qos=1)
        info.wait_for_publish(timeout=5)
        client.loop_stop()
        client.disconnect()
        logger.info("MQTT → %s : %s", topic, payload)
        return info.is_published()
    except Exception as e:
        logger.error("Échec publication MQTT (%s): %s", topic, e)
        return False


# ═══════════════════════════════════════════════════════════════════════════
#  2. ÉCOUTE — appelée uniquement depuis `manage.py run_mqtt`
# ═══════════════════════════════════════════════════════════════════════════

ETAT_TOPIC_FILTER = "home/+/+/etat"


def _appliquer_etat_recu(esp32_id: str, canal: str, payload: dict):
    """
    Met à jour EtatAppareil en base à partir d'un message d'état reçu
    d'un ESP32. Fait l'import ici (pas en haut du fichier) pour éviter
    les soucis d'app registry quand ce module est chargé hors contexte Django.
    """
    from .models import AppareilConnecte, EtatAppareil

    try:
        appareil = AppareilConnecte.objects.get(
            piece__esp32_id=esp32_id, canal=canal,
        )
    except AppareilConnecte.DoesNotExist:
        logger.warning("État reçu pour esp32_id=%s canal=%s : aucun appareil correspondant.",
                        esp32_id, canal)
        return
    except AppareilConnecte.MultipleObjectsReturned:
        logger.warning("Plusieurs appareils correspondent à esp32_id=%s canal=%s — ignoré.",
                        esp32_id, canal)
        return

    etat, _ = EtatAppareil.objects.get_or_create(appareil=appareil)

    if "allume" in payload:
        etat.allume = bool(payload["allume"])
    if "temperature" in payload:
        etat.temperature = payload["temperature"]
    if "mode_clim" in payload:
        etat.mode_clim = payload["mode_clim"]
    if "luminosite" in payload:
        etat.luminosite = payload["luminosite"]
    if "couleur" in payload:
        etat.couleur = payload["couleur"]
    if "volume" in payload:
        etat.volume = payload["volume"]
    if "chaine" in payload:
        etat.chaine = payload["chaine"]

    etat.save()
    logger.info("État mis à jour pour %s depuis ESP32 %s/%s", appareil.nom, esp32_id, canal)


def _on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connecté au broker MQTT %s:%s", MQTT_HOST, MQTT_PORT)
        client.subscribe(ETAT_TOPIC_FILTER, qos=1)
        logger.info("Abonné à %s", ETAT_TOPIC_FILTER)
    else:
        logger.error("Connexion MQTT échouée, code=%s", rc)


def _on_message(client, userdata, msg):
    # topic attendu : home/<esp32_id>/<canal>/etat
    parts = msg.topic.split("/")
    if len(parts) != 4 or parts[0] != "home" or parts[3] != "etat":
        logger.debug("Topic ignoré (format inattendu) : %s", msg.topic)
        return

    esp32_id, canal = parts[1], parts[2]

    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("Payload MQTT non-JSON reçu sur %s : %r", msg.topic, msg.payload)
        return

    _appliquer_etat_recu(esp32_id, canal, payload)


def _on_disconnect(client, userdata, rc):
    logger.warning("Déconnecté du broker MQTT (code=%s) — reconnexion automatique...", rc)


def start_listening():
    """
    Boucle bloquante. À appeler uniquement depuis `manage.py run_mqtt`.
    Reste connectée et traite les messages d'état entrants en continu.
    """
    client = _build_client(client_id="will-django-listener")
    client.on_connect    = _on_connect
    client.on_message    = _on_message
    client.on_disconnect = _on_disconnect

    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=MQTT_KEEPALIVE)

    logger.info("WILL MQTT listener démarré — en attente des états ESP32...")
    client.loop_forever()  # bloquant, gère la reconnexion automatique