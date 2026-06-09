from django.db import models
from django.contrib.auth.models import User


class Message(models.Model):
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE)
    message_utilisateur = models.TextField()
    reponse_ia = models.TextField()
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat de {self.utilisateur.username} le {self.date}"

    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ['-date']


class Alarme(models.Model):
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE)
    heure = models.TimeField()
    message = models.CharField(max_length=255)
    activee = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.message} ({self.heure}) - {self.utilisateur.username}"

    class Meta:
        verbose_name = "Alarme"
        verbose_name_plural = "Alarmes"


class AssistantStatus(models.Model):
    utilisateur = models.OneToOneField(User, related_name='assistant_status', on_delete=models.CASCADE)
    est_actif = models.BooleanField(default=False)
    est_reveille = models.BooleanField(default=False)
    derniere_detection = models.DateTimeField(auto_now=True)

    def __str__(self):
        statut = "Activé" if self.est_actif else "Désactivé"
        return f"Statut de Will pour {self.utilisateur.username} : {statut}"

    class Meta:
        verbose_name = "Statut Assistant"
        verbose_name_plural = "Statuts Assistant"


class Evaluation(models.Model):
    NOTE_CHOICES = [(i, str(i)) for i in range(1, 6)]  # 1 à 5 étoiles

    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE)
    note = models.IntegerField(choices=NOTE_CHOICES)
    commentaire = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Évaluation {self.note}/5 par {self.utilisateur.username}"

    class Meta:
        verbose_name = "Évaluation"
        verbose_name_plural = "Évaluations"
        ordering = ['-date']