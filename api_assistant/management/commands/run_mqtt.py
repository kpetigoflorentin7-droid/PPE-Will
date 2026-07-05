# api_assistant/management/commands/run_mqtt.py
#
# Lance le listener MQTT de WILL en process séparé et permanent.
# Usage :
#   python manage.py run_mqtt
#
# En production sur le Raspberry Pi, ce process est géré par systemd
# (voir will-mqtt.service) pour redémarrer automatiquement en cas de
# crash ou de reboot du Pi.

import logging

from django.core.management.base import BaseCommand

from api_assistant.mqtt_client import start_listening

logger = logging.getLogger("will.mqtt")


class Command(BaseCommand):
    help = "Démarre le listener MQTT qui écoute les états remontés par les ESP32."

    def handle(self, *args, **options):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        self.stdout.write(self.style.SUCCESS("Démarrage du listener MQTT WILL..."))
        try:
            start_listening()
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Listener MQTT arrêté (Ctrl+C)."))