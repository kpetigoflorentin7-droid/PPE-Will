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


class AppareilConnecte(models.Model):
    """Représente un appareil domotique lié à un utilisateur."""

    TYPE_CHOICES = [
        ('television',  'Télévision'),
        ('climatiseur', 'Climatiseur'),
        ('microonde',   'Micro-ondes'),
        ('led',         'LED / Ampoule'),
        ('autre',       'Autre'),
    ]

    PROTOCOLE_CHOICES = [
        ('wifi',   'WiFi (HTTP local)'),
        ('mqtt',   'MQTT'),
        ('ble',    'Bluetooth BLE'),
        ('ir',     'Infrarouge (via hub)'),
        ('zigbee', 'Zigbee (via hub)'),
    ]

    utilisateur   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appareils')
    nom           = models.CharField(max_length=100)
    type_appareil = models.CharField(max_length=20, choices=TYPE_CHOICES)
    protocole     = models.CharField(max_length=10, choices=PROTOCOLE_CHOICES, default='wifi')
    adresse_ip    = models.GenericIPAddressField(null=True, blank=True)
    adresse_mac   = models.CharField(max_length=17, null=True, blank=True)
    topic_mqtt    = models.CharField(max_length=200, null=True, blank=True)
    est_actif     = models.BooleanField(default=True)
    date_ajout    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Appareil connecté"
        verbose_name_plural = "Appareils connectés"
        unique_together = ('utilisateur', 'nom')

    def __str__(self):
        return f"{self.nom} ({self.type_appareil}) — {self.utilisateur.username}"


class EtatAppareil(models.Model):
    """Dernier état connu de chaque appareil."""

    appareil    = models.OneToOneField(AppareilConnecte, on_delete=models.CASCADE, related_name='etat')
    allume      = models.BooleanField(default=False)
    temperature = models.IntegerField(null=True, blank=True)
    mode_clim   = models.CharField(max_length=20, null=True, blank=True)
    luminosite  = models.IntegerField(null=True, blank=True)
    couleur     = models.CharField(max_length=7, null=True, blank=True)
    volume      = models.IntegerField(null=True, blank=True)
    chaine      = models.CharField(max_length=50, null=True, blank=True)
    mis_a_jour  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "État appareil"
        verbose_name_plural = "États appareils"

    def __str__(self):
        return f"État de {self.appareil.nom}"


class CommandeAppareil(models.Model):
    """Historique de toutes les commandes envoyées à un appareil."""

    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('envoyee',    'Envoyée'),
        ('succes',     'Succès'),
        ('echec',      'Échec'),
    ]

    appareil      = models.ForeignKey(AppareilConnecte, on_delete=models.CASCADE, related_name='commandes')
    utilisateur   = models.ForeignKey(User, on_delete=models.CASCADE)
    commande      = models.CharField(max_length=50)
    parametres    = models.JSONField(default=dict, blank=True)
    statut        = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    source        = models.CharField(max_length=10, default='vocal')
    date_commande = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Commande appareil"
        verbose_name_plural = "Commandes appareils"
        ordering = ['-date_commande']

    def __str__(self):
        return f"{self.commande} → {self.appareil.nom} ({self.statut})"