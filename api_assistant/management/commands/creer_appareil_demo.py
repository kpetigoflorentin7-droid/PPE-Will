"""
Commande de gestion : crée (ou met à jour) l'appareil de démo "Lampe Salon"
pour un utilisateur donné, avec le bon topic MQTT.

Usage :
    python manage.py creer_appareil_demo --user enoch
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from api_assistant.models import AppareilConnecte, EtatAppareil


class Command(BaseCommand):
    help = "Crée l'appareil de démo (lampe du salon) pour le prototype concours."

    def add_arguments(self, parser):
        parser.add_argument('--user', type=str, required=True,
                             help="Nom d'utilisateur Django propriétaire de l'appareil")
        parser.add_argument('--nom', type=str, default="Lampe Salon")
        parser.add_argument('--topic', type=str, default="will/salon/lumiere")

    def handle(self, *args, **options):
        username = options['user']
        nom      = options['nom']
        topic    = options['topic']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Utilisateur '{username}' introuvable."))
            return

        appareil, created = AppareilConnecte.objects.update_or_create(
            utilisateur=user,
            nom=nom,
            defaults={
                "type_appareil": "led",
                "protocole": "mqtt",
                "topic_mqtt": topic,
                "est_actif": True,
            },
        )
        EtatAppareil.objects.get_or_create(appareil=appareil)

        verbe = "créé" if created else "mis à jour"
        self.stdout.write(self.style.SUCCESS(
            f"✅ Appareil '{appareil.nom}' {verbe} pour {username} (topic : {topic})"
        ))
