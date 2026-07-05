# api_assistant/views_playlist.py
# ─────────────────────────────────────────────────────────────────────────────
# Gestion des playlists créées par l'utilisateur à partir de ses fichiers
# audio LOCAUX (stockés sur le téléphone). Le backend ne stocke que les
# métadonnées (nom de playlist, titres, chemins de fichiers) — jamais les
# fichiers audio eux-mêmes.
#
# Commandes vocales gérées ici :
#   • "joue / lance la playlist <nom ou numéro>"  → PLAY_PLAYLIST
#   • "stop / arrête la musique"                  → STOP_MUSIC
#   • lancer une playlist pendant qu'une autre joue → l'ancienne s'arrête
#     automatiquement côté Flutter (champ "remplacer": true)
#
# Point d'entrée unique à appeler dans _traiter_message() de views.py :
#   traiter_commande_vocale_playlist(prompt, request.user)
#
# ─────────────────────────────────────────────────────────────────────────────
# CHANGEMENT IMPORTANT PAR RAPPORT À LA VERSION PRÉCÉDENTE
# ─────────────────────────────────────────────────────────────────────────────
# La détection du "stop" comparait des mots EXACTS ("arrête", "arrete"...).
# Problème : la reconnaissance vocale (STT) renvoie souvent des variantes
# ("arrêtes", "arrêté", "stoppez", "stoppe-la"...) qui ne matchaient PAS ces
# mots exacts → la commande "stop la musique" était parfois ignorée.
#
# La nouvelle version :
#   1. Normalise les accents (arrête / arrete / ARRÊTE → traités pareil).
#   2. Compare par RADICAL (préfixe) plutôt que par mot exact
#      → "arrêt", "arrêtes", "arrête", "arrêter" matchent tous "arret".
#   3. Garde le même double filtre anti faux-positifs :
#      (mot d'arrêt présent) ET (contexte musical OU commande très courte).
# ─────────────────────────────────────────────────────────────────────────────

import re
import unicodedata
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import Playlist, MorceauPlaylist
from .serializers import PlaylistSerializer, MorceauPlaylistSerializer


# ═══════════════════════════════════════════════════════════════════════════
#  ENDPOINTS REST — PLAYLISTS
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def playlist_list_create(request):
    """
    GET  → liste les playlists de l'utilisateur (avec leurs morceaux)
    POST → crée une nouvelle playlist, ex: {"nom": "Sport"}
    """
    if request.method == 'GET':
        playlists = Playlist.objects.filter(utilisateur=request.user)
        return Response(PlaylistSerializer(playlists, many=True).data)

    serializer = PlaylistSerializer(data=request.data)
    if serializer.is_valid():
        playlist = serializer.save(utilisateur=request.user)
        return Response(PlaylistSerializer(playlist).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def playlist_detail(request, pk):
    """
    GET    → détail d'une playlist (avec ses morceaux)
    PUT    → renomme la playlist, ex: {"nom": "Nouveau nom"}
    DELETE → supprime la playlist et ses morceaux
    """
    playlist = get_object_or_404(Playlist, pk=pk, utilisateur=request.user)

    if request.method == 'GET':
        return Response(PlaylistSerializer(playlist).data)

    if request.method == 'PUT':
        s = PlaylistSerializer(playlist, data=request.data, partial=True)
        if s.is_valid():
            s.save()
            return Response(s.data)
        return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)

    playlist.delete()
    return Response({"message": "Playlist supprimée"}, status=status.HTTP_204_NO_CONTENT)


# ═══════════════════════════════════════════════════════════════════════════
#  ENDPOINTS REST — MORCEAUX D'UNE PLAYLIST
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def morceau_add(request, playlist_pk):
    """
    Ajoute un morceau (fichier local) à une playlist.
    Body attendu :
    {
        "titre": "Ma chanson",
        "chemin_local": "/storage/emulated/0/Music/chanson.mp3",
        "ordre": 0   ← optionnel
    }
    Le fichier audio lui-même n'est PAS envoyé au backend — seulement son
    chemin sur le téléphone, choisi par l'utilisateur via un sélecteur de
    fichiers côté Flutter (ex: file_picker).
    """
    playlist = get_object_or_404(Playlist, pk=playlist_pk, utilisateur=request.user)

    titre        = request.data.get('titre', '').strip()
    chemin_local = request.data.get('chemin_local', '').strip()
    ordre        = request.data.get('ordre', playlist.morceaux.count())

    if not titre or not chemin_local:
        return Response({"error": "titre et chemin_local sont requis"}, status=400)

    morceau = MorceauPlaylist.objects.create(
        playlist=playlist, titre=titre, chemin_local=chemin_local, ordre=ordre,
    )
    return Response(MorceauPlaylistSerializer(morceau).data, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def morceau_delete(request, playlist_pk, morceau_pk):
    """Retire un morceau d'une playlist (ne supprime pas le fichier du téléphone)."""
    morceau = get_object_or_404(
        MorceauPlaylist, pk=morceau_pk, playlist__pk=playlist_pk,
        playlist__utilisateur=request.user,
    )
    morceau.delete()
    return Response({"message": "Morceau retiré de la playlist"}, status=status.HTTP_204_NO_CONTENT)


# ═══════════════════════════════════════════════════════════════════════════
#  NORMALISATION DU TEXTE VOCAL
# ═══════════════════════════════════════════════════════════════════════════

def _normaliser(texte: str) -> str:
    """
    Met en minuscule et retire les accents.
    Ex: "Arrête la Musique !" → "arrete la musique !"

    Indispensable car le STT peut renvoyer "arrête", "arrete", "ARRÊTE"...
    selon le moteur de reconnaissance, et on veut traiter ces variantes
    de façon identique.
    """
    texte = texte.lower().strip()
    texte = unicodedata.normalize('NFKD', texte)
    texte = ''.join(c for c in texte if not unicodedata.combining(c))
    return texte


# ═══════════════════════════════════════════════════════════════════════════
#  VOCABULAIRE DE DÉTECTION VOCALE
# ═══════════════════════════════════════════════════════════════════════════
# Les listes ci-dessous contiennent des RADICAUX (préfixes), pas des mots
# exacts. Ça permet d'attraper automatiquement les conjugaisons et variantes
# que peut produire le STT : "arrete", "arretes", "arreter", "arretez" sont
# tous capturés par le radical "arret".

MOTS_LECTURE = [
    "joue", "jouer", "lance", "lancer", "ecoute", "ecouter",
    "mets", "mettre", "play",
]

# Radicaux d'arrêt — un mot du texte "commence par" un de ces radicaux
RADICAUX_STOP = [
    "stop",          # stop, stoppe, stopper, stoppez...
    "top",           # le STT avale souvent le "s" de "stop" → "top la musique"
    "arret",         # arrête, arrêtes, arrêter, arrêtez... (accents retirés)
    "pause",         # pause, pauser...
    "coup",          # coupe, couper, coupez... (attention: "coup" seul seul est rare en usage courant ici)
    "silence",
    "papa",
]

# Radicaux/mots qui confirment qu'on parle bien de musique (et pas de
# domotique, d'un appel, etc.)
RADICAUX_MUSIQUE = [
    "musique", "son", "playlist", "playliste",
    "chanson", "morceau", "lecture", "audio", "titre",
]


def _contient_radical(mots: list[str], radicaux: list[str]) -> bool:
    """Retourne True si au moins un mot du texte commence par un des radicaux."""
    for mot in mots:
        for radical in radicaux:
            if mot.startswith(radical):
                return True
    return False


# ═══════════════════════════════════════════════════════════════════════════
#  DÉTECTION — STOP DE LA MUSIQUE
# ═══════════════════════════════════════════════════════════════════════════

def _detecter_commande_stop(prompt: str) -> dict | None:
    """
    Détecte une commande d'arrêt de la musique/playlist en cours.
    Retourne {'reponse_ia', 'action_to_do'} ou None.

    Déclenche si un radical d'arrêt est présent ET :
      - soit un mot lié à la musique est cité ("arrête la musique",
        "stop la playlist"),
      - soit la commande vocale est très courte ("stop", "pause").

    Ce double filtre évite de couper la musique sur des phrases comme
    "arrête de parler" ou "coupe le chauffage" (domotique), tout en restant
    tolérant aux variantes de conjugaison renvoyées par le STT.
    """
    p = _normaliser(prompt)
    mots = p.split()

    if not mots:
        return None

    # 1. Un radical d'arrêt est-il présent ?
    a_stop = _contient_radical(mots, RADICAUX_STOP)
    if not a_stop:
        return None

    # 2. Contexte musical explicite OU commande très courte
    a_contexte_musique = _contient_radical(mots, RADICAUX_MUSIQUE)
    est_commande_courte = len(mots) <= 2  # "stop", "pause", "arrete stp"

    if not (a_contexte_musique or est_commande_courte):
        return None

    return {
        "reponse_ia":   "J'arrête la musique.",
        "action_to_do": {"action": "STOP_MUSIC"},
    }


# ═══════════════════════════════════════════════════════════════════════════
#  DÉTECTION — LECTURE D'UNE PLAYLIST
# ═══════════════════════════════════════════════════════════════════════════

def _trouver_playlist_par_voix(p_norm: str, user):
    """
    Cherche la playlist visée dans le texte vocal normalisé (sans accents).
    Supporte :
      - "playlist 2"       → 2ème playlist créée (ordre de création)
      - "playlist sport"   → playlist nommée "sport" (recherche partielle)
    Retourne le Playlist ou None.
    """
    if "playlist" not in p_norm:
        return None

    # Cherche un numéro après "playlist" (tolère "playliste" avec un e)
    m_num = re.search(r'playlist[e]?\s+(\d+)', p_norm)
    if m_num:
        index = int(m_num.group(1)) - 1  # "playlist 1" = la première créée
        playlists = list(Playlist.objects.filter(utilisateur=user).order_by('date_creation'))
        if 0 <= index < len(playlists):
            return playlists[index]
        return None

    # Sinon, cherche par nom (ex: "playlist sport" → nom__icontains "sport")
    m_nom = re.search(r'playlist[e]?\s+(.+)$', p_norm)
    if m_nom:
        nom_recherche = m_nom.group(1).strip()
        playlist = Playlist.objects.filter(
            utilisateur=user, nom__icontains=nom_recherche,
        ).first()
        if playlist:
            return playlist

    return None


def _detecter_commande_lecture(prompt: str, user) -> dict | None:
    """
    Détecte une commande de lecture de playlist.
    Retourne {'reponse_ia', 'action_to_do'} ou None.

    La présence du mot "playlist" (ou "playliste") suffit à déclencher, même
    sans verbe d'action — ça évite que "play" (caché dans "playliste") soit
    intercepté par la détection YouTube générique qui s'exécute après.

    Le champ "remplacer": True indique à Flutter d'ARRÊTER la lecture en cours
    avant de démarrer celle-ci → si une playlist joue déjà, elle s'arrête
    automatiquement et la nouvelle prend le relais.
    """
    p = _normaliser(prompt)

    if "playlist" not in p:
        return None

    playlist = _trouver_playlist_par_voix(p, user)
    if not playlist:
        return {
            "reponse_ia":   "Je n'ai pas trouvé cette playlist. Vérifie le nom ou le numéro.",
            "action_to_do": {},
        }

    morceaux = list(playlist.morceaux.order_by('ordre', 'date_ajout'))
    if not morceaux:
        return {
            "reponse_ia":   f"La playlist {playlist.nom} est vide.",
            "action_to_do": {},
        }

    tracks = [
        {"titre": m.titre, "chemin_local": m.chemin_local}
        for m in morceaux
    ]

    return {
        "reponse_ia":   f"Je lance la playlist {playlist.nom}.",
        "action_to_do": {
            "action":      "PLAY_PLAYLIST",
            "playlist_id": playlist.id,
            "remplacer":   True,   # ← Flutter stoppe la lecture en cours avant de démarrer
            "tracks":      tracks,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE UNIQUE — à appeler depuis _traiter_message() de views.py
# ═══════════════════════════════════════════════════════════════════════════

def traiter_commande_vocale_playlist(prompt: str, user) -> dict | None:
    """
    Aiguille le prompt vocal vers la bonne commande playlist.

    Ordre IMPORTANT :
      1. STOP d'abord → "stop la playlist" arrête au lieu de relancer.
      2. LECTURE ensuite.

    Retourne un dict {'reponse_ia', 'action_to_do'} si une commande playlist
    est reconnue, sinon None (le traitement continue : domotique, YouTube,
    _detecter_intention()...).

    À appeler AVANT _detecter_intention() dans _traiter_message() pour que
    "playliste X" ne soit jamais intercepté par la détection YouTube, et
    "stop la musique" ne soit jamais intercepté par une autre commande stop.
    """
    res_stop = _detecter_commande_stop(prompt)
    if res_stop:
        return res_stop

    res_lecture = _detecter_commande_lecture(prompt, user)
    if res_lecture:
        return res_lecture

    return None