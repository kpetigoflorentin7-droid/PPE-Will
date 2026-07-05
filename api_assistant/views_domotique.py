# ─── views_domotique.py ──────────────────────────────────────────────────────
# Colle ce contenu dans ton views.py existant, ou importe-le avec :
#   from .views_domotique import (
#       device_list_create, device_detail, device_control, device_state,
#       _detecter_commande_domotique
#   )
# ─────────────────────────────────────────────────────────────────────────────

import re
import requests as req_lib
from django.core.cache import cache
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import AppareilConnecte, EtatAppareil, CommandeAppareil, Piece
from .serializers import AppareilConnecteSerializer, CommandeAppareilSerializer, PieceSerializer


# ═══════════════════════════════════════════════════════════════════════════
#  DICTIONNAIRE DES COMMANDES VOCALES DOMOTIQUE
# ═══════════════════════════════════════════════════════════════════════════

MOTS_ALLUMER = [
    "allume", "allumer", "active", "activer", "ouvre", "ouvrir",
    "mets en marche", "démarre", "demarrer", "power on", "turn on"
]
MOTS_ETEINDRE = [
    "éteins", "eteins", "éteindre", "eteindre", "coupe", "couper",
    "arrête", "arrete", "désactive", "desactive", "power off", "turn off"
]
MOTS_APPAREILS = {
    "television":  ["télé", "tele", "télévision", "television", "tv"],
    "climatiseur": ["clim", "climatiseur", "climatisation", "air conditionné", "ac"],
    "microonde":   ["micro-onde", "microonde", "micro onde", "four micro-onde"],
    "led":         ["led", "lumière", "lumiere", "ampoule", "lampe", "éclairage", "eclairage", "lampe"],
}


def _trouver_appareil_par_voix(p_low: str, user):
    """
    Cherche dans le texte vocal quel appareil est visé.
    Retourne l'AppareilConnecte ou None.
    """
    for type_app, mots in MOTS_APPAREILS.items():
        for mot in mots:
            if mot in p_low:
                # Cherche d'abord par nom exact, puis par type
                appareil = (
                    AppareilConnecte.objects
                    .filter(utilisateur=user, est_actif=True, nom__icontains=mot)
                    .first()
                ) or (
                    AppareilConnecte.objects
                    .filter(utilisateur=user, est_actif=True, type_appareil=type_app)
                    .first()
                )
                if appareil:
                    return appareil, type_app
    return None, None


def _detecter_commande_domotique(prompt: str, user) -> dict | None:
    """
    Analyse le prompt vocal pour détecter une commande domotique.
    Retourne un dict avec 'action_to_do' et 'reponse_ia', ou None.

    Intègre cette fonction dans _traiter_message() de ton views.py,
    AVANT le bloc de détection des intentions système (étape 0).

    Exemple d'intégration dans _traiter_message() :
        commande_dom = _detecter_commande_domotique(prompt, user)
        if commande_dom:
            reponse_ia  = commande_dom['reponse_ia']
            action_data = commande_dom['action_to_do']
            cache.set(f"will_pending_action_{user.id}", action_data, timeout=30)
            # puis sauvegarde Message et return Response(...)
    """
    p = prompt.lower().strip()
    appareil, type_app = _trouver_appareil_par_voix(p, user)

    if not appareil:
        return None

    etat, _ = EtatAppareil.objects.get_or_create(appareil=appareil)
    nom = appareil.nom

    # ── ALLUMER ──────────────────────────────────────────────────────────
    if any(m in p for m in MOTS_ALLUMER):
        _envoyer_commande(appareil, 'power_on', {}, user)
        etat.allume = True
        etat.save()
        return {
            "reponse_ia":   f"J'allume {nom} !",
            "action_to_do": {"action": "DEVICE_CONTROL", "device_id": appareil.id,
                              "commande": "power_on", "params": {}},
        }

    # ── ÉTEINDRE ─────────────────────────────────────────────────────────
    if any(m in p for m in MOTS_ETEINDRE):
        _envoyer_commande(appareil, 'power_off', {}, user)
        etat.allume = False
        etat.save()
        return {
            "reponse_ia":   f"J'éteins {nom}.",
            "action_to_do": {"action": "DEVICE_CONTROL", "device_id": appareil.id,
                              "commande": "power_off", "params": {}},
        }

    # ── TEMPÉRATURE (climatiseur) ─────────────────────────────────────────
    if type_app == 'climatiseur':
        m_temp = re.search(r'(\d{1,2})\s*(?:degrés|degres|°|degré)', p)
        if m_temp:
            temp = int(m_temp.group(1))
            _envoyer_commande(appareil, 'set_temperature', {'temperature': temp}, user)
            etat.temperature = temp
            etat.allume = True
            etat.save()
            return {
                "reponse_ia":   f"Je règle le climatiseur à {temp} degrés.",
                "action_to_do": {"action": "DEVICE_CONTROL", "device_id": appareil.id,
                                  "commande": "set_temperature", "params": {"temperature": temp}},
            }
        # Modes
        if any(m in p for m in ["froid", "cool", "refroidir"]):
            _envoyer_commande(appareil, 'set_mode', {'mode': 'cool'}, user)
            etat.mode_clim = 'cool'
            etat.save()
            return {
                "reponse_ia":   f"Je mets le climatiseur en mode froid.",
                "action_to_do": {"action": "DEVICE_CONTROL", "device_id": appareil.id,
                                  "commande": "set_mode", "params": {"mode": "cool"}},
            }
        if any(m in p for m in ["chaud", "heat", "chauffer"]):
            _envoyer_commande(appareil, 'set_mode', {'mode': 'heat'}, user)
            etat.mode_clim = 'heat'
            etat.save()
            return {
                "reponse_ia":   f"Je mets le climatiseur en mode chaud.",
                "action_to_do": {"action": "DEVICE_CONTROL", "device_id": appareil.id,
                                  "commande": "set_mode", "params": {"mode": "heat"}},
            }

    # ── LUMINOSITÉ (LED / Ampoule) ────────────────────────────────────────
    if type_app == 'led':
        m_lum = re.search(r'(\d{1,3})\s*(?:%|pourcent|pour cent)', p)
        if m_lum:
            lum = max(0, min(100, int(m_lum.group(1))))
            _envoyer_commande(appareil, 'set_brightness', {'brightness': lum}, user)
            etat.luminosite = lum
            etat.allume = lum > 0
            etat.save()
            return {
                "reponse_ia":   f"Je règle la luminosité à {lum} pourcent.",
                "action_to_do": {"action": "DEVICE_CONTROL", "device_id": appareil.id,
                                  "commande": "set_brightness", "params": {"brightness": lum}},
            }
        # Couleur
        couleurs = {
            "rouge": "#FF0000", "bleu": "#0000FF", "vert": "#00FF00",
            "blanc": "#FFFFFF", "jaune": "#FFFF00", "orange": "#FF6600",
            "violet": "#8800FF", "rose": "#FF00AA",
        }
        for mot_coul, hex_coul in couleurs.items():
            if mot_coul in p:
                _envoyer_commande(appareil, 'set_color', {'color': hex_coul}, user)
                etat.couleur = hex_coul
                etat.save()
                return {
                    "reponse_ia":   f"Je mets la lumière en {mot_coul}.",
                    "action_to_do": {"action": "DEVICE_CONTROL", "device_id": appareil.id,
                                      "commande": "set_color", "params": {"color": hex_coul}},
                }

    # ── VOLUME / CHAÎNE (Télévision) ─────────────────────────────────────
    if type_app == 'television':
        m_vol = re.search(r'(?:volume|son)\s+(?:à\s+)?(\d{1,3})', p)
        if m_vol:
            vol = max(0, min(100, int(m_vol.group(1))))
            _envoyer_commande(appareil, 'set_volume', {'volume': vol}, user)
            etat.volume = vol
            etat.save()
            return {
                "reponse_ia":   f"Je règle le volume à {vol}.",
                "action_to_do": {"action": "DEVICE_CONTROL", "device_id": appareil.id,
                                  "commande": "set_volume", "params": {"volume": vol}},
            }
        if any(m in p for m in ["monte le son", "monte le volume", "plus fort"]):
            _envoyer_commande(appareil, 'volume_up', {}, user)
            return {
                "reponse_ia":   "Je monte le volume.",
                "action_to_do": {"action": "DEVICE_CONTROL", "device_id": appareil.id,
                                  "commande": "volume_up", "params": {}},
            }
        if any(m in p for m in ["baisse le son", "baisse le volume", "moins fort", "mute", "sourdine"]):
            _envoyer_commande(appareil, 'volume_down', {}, user)
            return {
                "reponse_ia":   "Je baisse le volume.",
                "action_to_do": {"action": "DEVICE_CONTROL", "device_id": appareil.id,
                                  "commande": "volume_down", "params": {}},
            }
        m_chaine = re.search(r'(?:chaîne|chaine|canal)\s+(\w+)', p)
        if m_chaine:
            chaine = m_chaine.group(1)
            _envoyer_commande(appareil, 'set_channel', {'channel': chaine}, user)
            etat.chaine = chaine
            etat.save()
            return {
                "reponse_ia":   f"Je mets la chaîne {chaine}.",
                "action_to_do": {"action": "DEVICE_CONTROL", "device_id": appareil.id,
                                  "commande": "set_channel", "params": {"channel": chaine}},
            }

    return None  # Appareil trouvé mais commande non reconnue → Mistral prend la main


# ═══════════════════════════════════════════════════════════════════════════
#  ENVOI RÉEL DE LA COMMANDE À L'APPAREIL
# ═══════════════════════════════════════════════════════════════════════════

def _envoyer_commande(appareil: AppareilConnecte, commande: str, params: dict, user) -> bool:
    """
    Enregistre la commande en base ET tente de l'envoyer à l'appareil.
    Retourne True si succès.

    Protocoles supportés :
      - mqtt  → publication MQTT vers le broker Mosquitto local (Raspberry Pi)
                C'est le protocole principal de l'architecture Edge Computing.
      - unity → maison virtuelle Unity (prototype sans ESP32), via HTTP local
      - wifi  → requête HTTP POST vers l'IP locale de l'appareil
      - ble   → envoie action_to_do vers Flutter via le cache (Flutter gère le BLE)
      - ir    → idem BLE (Flutter déclenche l'IR via le plugin)
    """
    log = CommandeAppareil.objects.create(
        appareil=appareil,
        utilisateur=user,
        commande=commande,
        parametres=params,
        statut='en_attente',
        source='vocal',
    )

    succes = False

    try:
        if appareil.protocole == 'mqtt' and appareil.topic_mqtt:
            from .mqtt_client import publish_command
            succes = publish_command(appareil, commande, params)

        elif appareil.protocole == 'unity':
            # Maison virtuelle Unity — communique le canal (nom de l'objet 3D)
            # et la commande via HTTP, Unity exécute l'action dans la scène.
            url = f"{settings.UNITY_API_URL}/command"
            r = req_lib.post(
                url,
                json={"canal": appareil.canal, "cmd": commande, **params},
                timeout=3,
            )
            succes = r.status_code == 200

        elif appareil.protocole == 'wifi' and appareil.adresse_ip:
            # L'appareil expose une petite API REST locale (ex: ESP8266/ESP32)
            url = f"http://{appareil.adresse_ip}/command"
            r = req_lib.post(url, json={"cmd": commande, **params}, timeout=3)
            succes = r.status_code == 200

        else:
            # BLE / IR / protocole non géré côté serveur :
            # Flutter récupère l'action via /check-will/ et gère en local
            succes = True  # optimiste, Flutter confirmera

    except Exception as e:
        print(f"⚠️ Erreur envoi commande ({commande} → {appareil.nom}): {e}")

    log.statut = 'succes' if succes else 'echec'
    log.save()
    return succes


# ═══════════════════════════════════════════════════════════════════════════
#  ENDPOINTS REST
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def device_list_create(request):
    """
    GET  → liste tous les appareils de l'utilisateur (avec leur état)
    POST → ajoute un nouvel appareil
    """
    if request.method == 'GET':
        appareils = AppareilConnecte.objects.filter(utilisateur=request.user)
        return Response(AppareilConnecteSerializer(appareils, many=True).data)

    serializer = AppareilConnecteSerializer(data=request.data)
    if serializer.is_valid():
        appareil = serializer.save(utilisateur=request.user)
        # Crée l'état initial
        EtatAppareil.objects.get_or_create(appareil=appareil)
        return Response(AppareilConnecteSerializer(appareil).data,
                        status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def device_detail(request, pk):
    """
    GET    → détail d'un appareil
    PUT    → modifie l'appareil (nom, IP, protocole…)
    DELETE → supprime l'appareilq
    """
    appareil = get_object_or_404(AppareilConnecte, pk=pk, utilisateur=request.user)

    if request.method == 'GET':
        return Response(AppareilConnecteSerializer(appareil).data)

    if request.method == 'PUT':
        s = AppareilConnecteSerializer(appareil, data=request.data, partial=True)
        if s.is_valid():
            s.save()
            return Response(s.data)
        return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)

    appareil.delete()
    return Response({"message": "Appareil supprimé"}, status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def device_control(request, pk):
    """
    Envoie une commande manuelle à un appareil (depuis l'interface Flutter).

    Body attendu :
    {
        "commande":   "power_on" | "power_off" | "set_temperature" | "set_brightness" | ...,
        "parametres": {"temperature": 22}   ← optionnel selon la commande
    }
    """
    appareil  = get_object_or_404(AppareilConnecte, pk=pk, utilisateur=request.user)
    commande  = request.data.get('commande', '').strip()
    parametres = request.data.get('parametres', {})

    if not commande:
        return Response({"error": "Commande manquante"}, status=400)

    succes = _envoyer_commande(appareil, commande, parametres, request.user)

    # Mise à jour de l'état en base
    etat, _ = EtatAppareil.objects.get_or_create(appareil=appareil)
    if commande == 'power_on':
        etat.allume = True
    elif commande == 'power_off':
        etat.allume = False
    elif commande == 'set_temperature' and 'temperature' in parametres:
        etat.temperature = parametres['temperature']
        etat.allume = True
    elif commande == 'set_brightness' and 'brightness' in parametres:
        etat.luminosite = parametres['brightness']
        etat.allume = parametres['brightness'] > 0
    elif commande == 'set_color' and 'color' in parametres:
        etat.couleur = parametres['color']
    elif commande == 'set_volume' and 'volume' in parametres:
        etat.volume = parametres['volume']
    elif commande == 'set_channel' and 'channel' in parametres:
        etat.chaine = parametres['channel']
    elif commande == 'set_mode' and 'mode' in parametres:
        etat.mode_clim = parametres['mode']
    etat.save()

    # Si l'appareil utilise BLE/IR → Flutter a besoin de l'action via le cache
    if appareil.protocole in ('ble', 'ir', 'zigbee'):
        cache.set(
            f"will_pending_action_{request.user.id}",
            {"action": "DEVICE_CONTROL", "device_id": pk,
             "commande": commande, "params": parametres},
            timeout=30,
        )

    return Response({
        "success": succes,
        "message": "Commande envoyée" if succes else "Commande en file (BLE/IR)",
        "etat": {
            "allume":      etat.allume,
            "temperature": etat.temperature,
            "luminosite":  etat.luminosite,
            "volume":      etat.volume,
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def device_state(request, pk):
    """
    Retourne l'état courant d'un appareil.
    Flutter l'appelle pour rafraîchir l'UI après une commande.
    """
    appareil = get_object_or_404(AppareilConnecte, pk=pk, utilisateur=request.user)
    etat, _  = EtatAppareil.objects.get_or_create(appareil=appareil)
    return Response({
        "id":          appareil.id,
        "nom":         appareil.nom,
        "type":        appareil.type_appareil,
        "allume":      etat.allume,
        "temperature": etat.temperature,
        "mode_clim":   etat.mode_clim,
        "luminosite":  etat.luminosite,
        "couleur":     etat.couleur,
        "volume":      etat.volume,
        "chaine":      etat.chaine,
        "mis_a_jour":  etat.mis_a_jour,
    })


# ═══════════════════════════════════════════════════════════════════════════
#  ENDPOINTS PIÈCES (organisation par pièce + hub ESP32)
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def piece_list_create(request):
    """
    GET  → liste les pièces existantes (accessible à tout utilisateur connecté,
           pour qu'il puisse choisir où ajouter un appareil)
    POST → crée une nouvelle pièce — RÉSERVÉ AUX ADMINS (installation physique
           d'un ESP32 par le technicien/installateur, pas par l'utilisateur final)
    """
    if request.method == 'GET':
        pieces = Piece.objects.all()
        return Response(PieceSerializer(pieces, many=True).data)

    if not request.user.is_staff:
        return Response(
            {"error": "Seul un administrateur peut créer une pièce (installation d'un ESP32)."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = PieceSerializer(data=request.data)
    if serializer.is_valid():
        # La pièce n'est plus liée à un utilisateur précis : elle appartient
        # à la maison/structure entière, gérée par l'admin.
        piece = serializer.save(utilisateur=request.user)
        return Response(PieceSerializer(piece).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def piece_detail(request, pk):
    """
    GET    → détail d'une pièce (accessible à tous les utilisateurs connectés)
    PUT    → modifie la pièce — RÉSERVÉ AUX ADMINS
    DELETE → supprime la pièce — RÉSERVÉ AUX ADMINS
    """
    piece = get_object_or_404(Piece, pk=pk)

    if request.method == 'GET':
        return Response(PieceSerializer(piece).data)

    if not request.user.is_staff:
        return Response(
            {"error": "Seul un administrateur peut modifier ou supprimer une pièce."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == 'PUT':
        s = PieceSerializer(piece, data=request.data, partial=True)
        if s.is_valid():
            s.save()
            return Response(s.data)
        return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)

    piece.delete()
    return Response({"message": "Pièce supprimée"}, status=status.HTTP_204_NO_CONTENT)