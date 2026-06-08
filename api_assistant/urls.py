from django.urls import path
from .views import *

urlpatterns = [
    # Authentification & Profil
    path('register/', register, name='register'),
    path('login/', login, name='login'),
    path('profile/', profile, name='profile'),

    # Chat & Assistant
    path('chat/', chat, name='chat'),
    path('voice_command/', voice_command, name='voice-command'),

    # Alarmes
    path('alarms/', alarm_list_create, name='alarm-list-create'),
    path('alarms/<int:pk>/', alarm_delete, name='alarm-delete'),

    # Appel & Météo
    path('call/', make_call, name='make-call'),
    path('weather/', get_weather, name='get-weather'),

    # Statut de Will
    path('check-will/', check_will, name='check-will'),

    # Synchronisation des apps installées
    path('sync-apps/', sync_apps, name='sync-apps'),
]