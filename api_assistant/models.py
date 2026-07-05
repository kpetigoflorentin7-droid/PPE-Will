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
    
    # ─── À AJOUTER dans ton models.py existant ───────────────────────────────────




class Piece(models.Model):
    """Une pièce de la maison (salon, chambre, cuisine...) reliée à un hub ESP32."""

    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pieces')
    nom         = models.CharField(max_length=100)            # ex: "Salon"
    # Identifiant du module ESP32 qui couvre cette pièce — utilisé pour
    # construire les topics MQTT (ex: home/<esp32_id>/...)
    esp32_id    = models.CharField(max_length=50, unique=True, null=True, blank=True)
    date_ajout  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pièce"
        unique_together = ('utilisateur', 'nom')

    def __str__(self):
        return f"{self.nom} — {self.utilisateur.username}"


class AppareilConnecte(models.Model):
    """Représente un appareil domotique lié à un utilisateur."""

    TYPE_CHOICES = [
        ('television', 'Télévision'),
        ('climatiseur', 'Climatiseur'),
        ('microonde', 'Micro-ondes'),
        ('led', 'LED / Ampoule'),
        ('autre', 'Autre'),
    ]

    PROTOCOLE_CHOICES = [
        ('wifi',   'WiFi (HTTP local)'),
        ('mqtt',   'MQTT'),
        ('ble',    'Bluetooth BLE'),
        ('ir',     'Infrarouge (via hub)'),
        ('zigbee', 'Zigbee (via hub)'),
        ('unity',  'Maison virtuelle Unity'),
    ]

    utilisateur  = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appareils')
    piece        = models.ForeignKey(Piece, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='appareils')
    nom          = models.CharField(max_length=100)          # ex: "Télé du salon"
    type_appareil = models.CharField(max_length=20, choices=TYPE_CHOICES)
    protocole    = models.CharField(max_length=10, choices=PROTOCOLE_CHOICES, default='mqtt')
    adresse_ip   = models.GenericIPAddressField(null=True, blank=True)  # pour WiFi/MQTT
    adresse_mac  = models.CharField(max_length=17, null=True, blank=True)  # ex: AA:BB:CC:DD:EE:FF
    # Identifiant du relais/canal sur le module ESP32 de la pièce (ex: "relais_1", "ir_tv")
    canal        = models.CharField(max_length=50, null=True, blank=True)
    topic_mqtt   = models.CharField(max_length=200, null=True, blank=True)  # auto-généré si vide
    est_actif    = models.BooleanField(default=True)
    date_ajout   = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Auto-génère le topic MQTT si non renseigné manuellement :
        # home/<esp32_id>/<canal>
        if not self.topic_mqtt and self.piece and self.piece.esp32_id and self.canal:
            self.topic_mqtt = f"home/{self.piece.esp32_id}/{self.canal}"
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Appareil connecté"
        unique_together = ('utilisateur', 'nom')

    def __str__(self):
        return f"{self.nom} ({self.type_appareil}) — {self.utilisateur.username}"


class EtatAppareil(models.Model):
    """Dernier état connu de chaque appareil (mis à jour à chaque commande)."""

    appareil    = models.OneToOneField(AppareilConnecte, on_delete=models.CASCADE, related_name='etat')
    allume      = models.BooleanField(default=False)
    # Climatiseur
    temperature = models.IntegerField(null=True, blank=True)   # en °C
    mode_clim   = models.CharField(max_length=20, null=True, blank=True)  # froid/chaud/ventilation
    # LED / Ampoule
    luminosite  = models.IntegerField(null=True, blank=True)   # 0-100 %
    couleur     = models.CharField(max_length=7, null=True, blank=True)   # ex: #FF6600
    # Télé
    volume      = models.IntegerField(null=True, blank=True)   # 0-100
    chaine      = models.CharField(max_length=50, null=True, blank=True)
    # Timestamp
    mis_a_jour  = models.DateTimeField(auto_now=True)

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
    commande      = models.CharField(max_length=50)   # ex: power_on, set_temp, set_brightness
    parametres    = models.JSONField(default=dict, blank=True)  # ex: {"temperature": 22}
    statut        = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    source        = models.CharField(max_length=10, default='vocal')  # vocal / manuel
    date_commande = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_commande']

    def __str__(self):
        return f"{self.commande} → {self.appareil.nom} ({self.statut})"


# ═══════════════════════════════════════════════════════════════════════════
#  PLAYLISTS — créées par l'utilisateur à partir de ses propres audios
#  (fichiers stockés sur le téléphone, le backend ne garde que les métadonnées)
# ═══════════════════════════════════════════════════════════════════════════

class Playlist(models.Model):
    """Une playlist créée par l'utilisateur à partir de ses fichiers audio locaux."""

    utilisateur    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='playlists')
    nom            = models.CharField(max_length=100)   # ex: "Playlist 1", "Sport", "Chill"
    date_creation  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Playlist"
        ordering = ['date_creation']
        unique_together = ('utilisateur', 'nom')

    def __str__(self):
        return f"{self.nom} — {self.utilisateur.username}"


class MorceauPlaylist(models.Model):
    """
    Un morceau dans une playlist. Le fichier audio reste sur le téléphone —
    on ne stocke ici que le chemin local et un titre affiché.
    """

    playlist     = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='morceaux')
    titre        = models.CharField(max_length=200)            # ex: "Ma chanson préférée"
    chemin_local = models.CharField(max_length=500)             # chemin du fichier sur le téléphone
    ordre        = models.PositiveIntegerField(default=0)       # position dans la playlist
    date_ajout   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Morceau"
        ordering = ['ordre', 'date_ajout']

    def __str__(self):
        return f"{self.titre} ({self.playlist.nom})"


class AppInstallee(models.Model):
    """
    Une application installée sur le téléphone de l'utilisateur, synchronisée
    via /api/sync-apps/. Stockée en base (pas en mémoire) pour survivre aux
    redémarrages du serveur, et propre à chaque utilisateur.
    """
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='apps_installees')
    nom         = models.CharField(max_length=150)   # ex: "whatsapp" (en minuscules)
    package     = models.CharField(max_length=200)   # ex: "com.whatsapp"
    date_sync   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Application installée"
        unique_together = ('utilisateur', 'nom')

    def __str__(self):
        return f"{self.nom} ({self.utilisateur.username})"
    
# Create your models here.