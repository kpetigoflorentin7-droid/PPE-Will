# ─────────────────────────────────────────────────────────────────────────
#  Vues domotique — gestion des appareils connectés et envoi des ordres
#  MQTT vers les ESP32.
# ─────────────────────────────────────────────────────────────────────────
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import AppareilConnecte, EtatAppareil, CommandeAppareil
from .serializers import AppareilConnecteSerializer, CommandeAppareilSerializer
from .mqtt_client import publish_command


# ═══════════════════════════════════════════════════════════════════════
#  CŒUR : exécute une commande sur un appareil (MQTT + base de données)
#  Réutilisé par les endpoints HTTP ci-dessous ET par le moteur vocal
#  (views.py → _traiter_message) pour qu'une commande tapée ou dite ait
#  exactement le même comportement.
# ═══════════════════════════════════════════════════════════════════════
def executer_commande(appareil: AppareilConnecte, commande: str,
                       parametres: dict | None, utilisateur, source="manuel"):
    """
    commande : 'on' | 'off' | (autres commandes futures : 'set_temp', etc.)
    Retourne (succes: bool, commande_obj: CommandeAppareil, etat: EtatAppareil)
    """
    parametres = parametres or {}

    cmd = CommandeAppareil.objects.create(
        appareil=appareil,
        utilisateur=utilisateur,
        commande=commande,
        parametres=parametres,
        statut="en_attente",
        source=source,
    )

    payload = {"action": commande, **parametres}
    envoye = publish_command(appareil.topic_mqtt, payload)

    etat, _ = EtatAppareil.objects.get_or_create(appareil=appareil)

    if envoye:
        # Mise à jour optimiste : on suppose que l'ESP32 va exécuter l'ordre.
        # Pour le prototype, il n'y a pas (encore) d'accusé de réception
        # MQTT relu par Django ; l'état affiché reflète l'ordre envoyé.
        if commande == "on":
            etat.allume = True
        elif commande == "off":
            etat.allume = False
        etat.save()
        cmd.statut = "envoyee"
    else:
        cmd.statut = "echec"
    cmd.save()

    return envoye, cmd, etat


# ═══════════════════════════════════════════════════════════════════════
#  1. Liste des appareils / création
# ═══════════════════════════════════════════════════════════════════════
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def device_list_create(request):
    if request.method == 'GET':
        appareils = AppareilConnecte.objects.filter(utilisateur=request.user)
        return Response(AppareilConnecteSerializer(appareils, many=True).data)

    serializer = AppareilConnecteSerializer(data=request.data)
    if serializer.is_valid():
        appareil = serializer.save(utilisateur=request.user)
        EtatAppareil.objects.get_or_create(appareil=appareil)
        return Response(AppareilConnecteSerializer(appareil).data,
                         status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ═══════════════════════════════════════════════════════════════════════
#  2. Détail / modification / suppression d'un appareil
# ═══════════════════════════════════════════════════════════════════════
@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def device_detail(request, pk):
    appareil = get_object_or_404(AppareilConnecte, pk=pk, utilisateur=request.user)

    if request.method == 'GET':
        return Response(AppareilConnecteSerializer(appareil).data)

    if request.method == 'PUT':
        serializer = AppareilConnecteSerializer(appareil, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    appareil.delete()
    return Response({"message": "Appareil supprimé"}, status=status.HTTP_204_NO_CONTENT)


# ═══════════════════════════════════════════════════════════════════════
#  3. Envoi d'une commande à un appareil (allumer / éteindre / etc.)
# ═══════════════════════════════════════════════════════════════════════
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def device_control(request, pk):
    """
    Body attendu : { "commande": "on" | "off", "parametres": {...} }
    Publie l'ordre MQTT vers l'ESP32 et met à jour l'état en base.
    """
    appareil = get_object_or_404(AppareilConnecte, pk=pk, utilisateur=request.user)
    commande = request.data.get('commande', '').strip().lower()
    parametres = request.data.get('parametres', {})

    if commande not in ('on', 'off'):
        return Response({"error": "Commande invalide. Utilisez 'on' ou 'off'."},
                         status=status.HTTP_400_BAD_REQUEST)

    if not appareil.est_actif:
        return Response({"error": "Cet appareil est désactivé."},
                         status=status.HTTP_400_BAD_REQUEST)

    envoye, cmd, etat = executer_commande(
        appareil, commande, parametres, request.user, source="manuel"
    )

    if not envoye:
        return Response({
            "message": f"Échec de l'envoi de la commande à {appareil.nom}.",
            "commande": CommandeAppareilSerializer(cmd).data,
        }, status=status.HTTP_502_BAD_GATEWAY)

    return Response({
        "message": f"Commande '{commande}' envoyée à {appareil.nom}.",
        "commande": CommandeAppareilSerializer(cmd).data,
        "etat": {
            "allume": etat.allume,
            "mis_a_jour": etat.mis_a_jour,
        },
    })


# ═══════════════════════════════════════════════════════════════════════
#  4. État courant d'un appareil
# ═══════════════════════════════════════════════════════════════════════
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def device_state(request, pk):
    appareil = get_object_or_404(AppareilConnecte, pk=pk, utilisateur=request.user)
    etat, _ = EtatAppareil.objects.get_or_create(appareil=appareil)
    return Response({
        "appareil": appareil.nom,
        "allume": etat.allume,
        "temperature": etat.temperature,
        "mode_clim": etat.mode_clim,
        "luminosite": etat.luminosite,
        "couleur": etat.couleur,
        "volume": etat.volume,
        "chaine": etat.chaine,
        "mis_a_jour": etat.mis_a_jour,
    })
