from django.db import models
from django.contrib.auth.models import User

class Message(models.Model):
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE)
    message_utilisateur = models.TextField()
    reponse_ia = models.TextField()
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat de {self.utilisateur.username} le {self.date}"

class Alarme(models.Model):
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE)
    heure = models.TimeField()
    message = models.CharField(max_length=255)
    activee = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.message} ({self.heure}) - {self.utilisateur.username}"

class AssistantStatus(models.Model):
    utilisateur = models.OneToOneField(User, related_name='assistant_status', on_delete=models.CASCADE)
    # est_actif : C'est le switch sur ton appli (ON/OFF)
    est_actif = models.BooleanField(default=False) 
    # est_reveille : C'est l'état temporaire (après avoir dit "Will")
    est_reveille = models.BooleanField(default=False)
    derniere_detection = models.DateTimeField(auto_now=True)

    def __str__(self):
        statut = "Activé" if self.est_actif else "Désactivé"
        return f"Statut de Will pour {self.utilisateur.username} : {statut}"
# Create your models here.
