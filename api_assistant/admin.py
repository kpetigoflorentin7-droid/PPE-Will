from django.contrib import admin
from .models import Message, Alarme

# On enregistre les modèles sans options compliquées pour l'instant
# Cela permet à Django de démarrer sans erreur
admin.site.register(Message)
admin.site.register(Alarme)