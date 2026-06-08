# ─── IMPORTS ────────────────────────────────────────────────────────────────
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework import status
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from datetime import datetime, time as dt_time
import pytz, re, requests, urllib.parse
from mistralai import Mistral
from django.contrib.auth.models import User
from .serializers import UserSerializer, MessageSerializer, AlarmeSerializer
from .models import Message, Alarme, AssistantStatus

# ─── CONFIG ─────────────────────────────────────────────────────────────────
MISTRAL_API_KEY = "lFnqxunw1tRbn1zdfHfxPNtVk3u0cHL2"
client = Mistral(api_key=MISTRAL_API_KEY)


# ═══════════════════════════════════════════════════════════════════════════
#  DICTIONNAIRE DES APPS (nom vocal → package Android)
# ═══════════════════════════════════════════════════════════════════════════
APPS_DICT = {
    "whatsapp":       "com.whatsapp",
    "facebook":       "com.facebook.katana",
    "instagram":      "com.instagram.android",
    "tiktok":         "com.zhiliaoapp.musically",
    "twitter":        "com.twitter.android",
    "x":              "com.twitter.android",
    "snapchat":       "com.snapchat.android",
    "telegram":       "org.telegram.messenger",
    "linkedin":       "com.linkedin.android",
    "pinterest":      "com.pinterest",
    "youtube":        "com.google.android.youtube",
    "netflix":        "com.netflix.mediaclient",
    "spotify":        "com.spotify.music",
    "deezer":         "deezer.android.app",
    "gmail":          "com.google.android.gm",
    "outlook":        "com.microsoft.office.outlook",
    "discord":        "com.discord",
    "zoom":           "us.zoom.videomeetings",
    "meet":           "com.google.android.apps.meetings",
    "teams":          "com.microsoft.teams",
    "maps":           "com.google.android.apps.maps",
    "google maps":    "com.google.android.apps.maps",
    "waze":           "com.waze",
    "uber":           "com.ubercab",
    "play store":     "com.android.vending",
    "camera":         "com.android.camera2",
    "appareil photo": "com.android.camera2",
    "calculatrice":   "com.google.android.calculator",
    "agenda":         "com.google.android.calendar",
    "calendrier":     "com.google.android.calendar",
    "chrome":         "com.android.chrome",
    "paramètres":     "com.android.settings",
    "settings":       "com.android.settings",
    "galerie":        "com.google.android.apps.photos",
    "photos":         "com.google.android.apps.photos",
    "fichiers":       "com.google.android.documentsui",
    "horloge":        "com.google.android.deskclock",
    "clock":          "com.google.android.deskclock",
}

# Apps installées dynamiquement depuis le téléphone (via /api/sync-apps/)
APPS_DATABASE: dict = {}


# ═══════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def _extraire_heure(texte: str):
    """
    Extrait la première heure trouvée dans le texte.
    Accepte : 5h, 5h30, 5:30, 05h30, 17h, etc.
    Retourne (heure_str "HH:MM", h int, m int) ou (None, None, None).
    """
    # Forme avec minutes : 5h30, 5:30, 05H30
    m = re.search(r'\b(\d{1,2})\s*[hH:]\s*(\d{2})\b', texte)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        return f"{h:02d}:{mn:02d}", h, mn
    # Forme sans minutes : 5h, 17h
    m2 = re.search(r'\b(\d{1,2})\s*h\b', texte)
    if m2:
        h = int(m2.group(1))
        return f"{h:02d}:00", h, 0
    return None, None, None


def _detecter_intention(prompt: str) -> dict | None:
    """
    Détecte les intentions système (ouvrir app, YouTube, Google, Maps).
    Retourne un dict avec 'action', 'reponse_ia' et les paramètres,
    ou None si c'est une conversation normale.
    """
    p = prompt.lower().strip()

    # ── Ouvrir une application ──
    mots_ouvrir = ["ouvre", "ouvrir", "lance", "lancer", "démarre",
                   "demarrer", "open", "va sur", "vas sur"]
    if any(mot in p for mot in mots_ouvrir):
        # D'abord chercher dans les apps dynamiques du téléphone
        for nom, package in APPS_DATABASE.items():
            if nom in p:
                return {"action": "OPEN_APP", "package": package, "app_name": nom.capitalize(),
                        "reponse_ia": f"J'ouvre {nom.capitalize()} !"}
        # Puis dans le dictionnaire statique
        for nom, package in APPS_DICT.items():
            if nom in p:
                return {"action": "OPEN_APP", "package": package, "app_name": nom.capitalize(),
                        "reponse_ia": f"J'ouvre {nom.capitalize()} !"}

    # ── YouTube ──
    mots_yt = ["joue", "jouer", "écoute", "ecoute", "mets", "met",
               "play", "youtube", "chanson", "musique"]
    if any(mot in p for mot in mots_yt):
        query = p
        for mot in ["joue", "écoute", "ecoute", "mets", "met", "lance", "play"]:
            if mot in query:
                query = query[query.index(mot) + len(mot):].strip()
                break
        for rm in ["sur youtube", "sur spotify", "s'il te plaît", "stp", "pour moi"]:
            query = query.replace(rm, "").strip()
        if query:
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            return {"action": "OPEN_URL", "url": url,
                    "reponse_ia": f"Je lance '{query}' sur YouTube !"}

    # ── Google Search ──
    mots_google = ["cherche", "recherche", "googler", "trouve", "infos sur",
                   "information sur", "qu'est-ce que", "c'est quoi", "je veux savoir"]
    if any(mot in p for mot in mots_google):
        query = p
        for mot in mots_google + ["sur google", "s'il te plaît", "stp", "pour moi"]:
            query = query.replace(mot, "").strip()
        if query:
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            return {"action": "OPEN_URL", "url": url,
                    "reponse_ia": f"Je cherche '{query}' sur Google !"}

    # ── Maps / Navigation ──
    mots_maps = ["navigue vers", "itinéraire vers", "itineraire vers",
                 "comment aller à", "amène-moi à", "amene-moi à", "directions vers"]
    if any(mot in p for mot in mots_maps):
        dest = p
        for mot in mots_maps:
            dest = dest.replace(mot, "").strip()
        if dest:
            url = f"https://www.google.com/maps/search/{urllib.parse.quote(dest)}"
            return {"action": "OPEN_URL", "url": url,
                    "reponse_ia": f"Je t'emmène vers {dest} sur Maps !"}

    return None


# ═══════════════════════════════════════════════════════════════════════════
#  CŒUR DU TRAITEMENT — commun au chat et aux commandes vocales
# ═══════════════════════════════════════════════════════════════════════════
def _traiter_message(user, prompt: str):
    """
    Analyse le prompt, exécute l'action (alarme, appel, app…)
    et retourne une Response DRF avec :
      - reponse_ia  : texte que Will lit à voix haute sur le téléphone
      - action_to_do: dict d'action à exécuter côté Flutter (ou {})
    """
    try:
        p_low = prompt.lower().strip()

        # Mots-clés par catégorie
        MOTS_ALARME = ["réveil", "reveil", "alarme", "réveille", "reveille",
                       "lève moi", "leve moi", "debout", "programme", "mets une alarme",
                       "met une alarme", "crée une alarme", "creer une alarme",
                       "programme moi une alarme", "met moi un réveil"]
        MOTS_SUPPR  = ["supprime", "supprimer", "suprime", "efface", "effacer",
                       "annule", "annuler", "enlève", "enleve", "vire", "désactive",
                       "desactive", "retire"]
        MOTS_MODIF  = ["change", "modifier", "modifie", "déplace", "deplace",
                       "repousse", "avance", "décale", "decale", "mets à", "met à"]
        MOTS_APPEL  = ["appelle", "appel", "appeler", "compose", "téléphone",
                       "telephone", "contact", "appele"]
        MOTS_METEO  = ["météo", "meteo", "temps qu'il fait", "temperature",
                       "température", "il fait chaud", "il fait froid",
                       "quel temps", "prévisions", "previsions"]

        reponse_ia  = ""
        action_data = {}

        # ── 0. Intentions système (apps, YouTube, Google, Maps) ──────────
        intention = _detecter_intention(prompt)
        if intention:
            reponse_ia  = intention.pop("reponse_ia")
            action_data = intention
            cache.set(f"will_pending_action_{user.id}", action_data, timeout=30)

        # ── 1. Suppression d'alarme ──────────────────────────────────────
        elif (any(m in p_low for m in MOTS_SUPPR)
              and any(x in p_low for x in ["alarme", "réveil", "reveil"])):

            if any(x in p_low for x in ["tous", "toutes", "tout"]):
                count = Alarme.objects.filter(utilisateur=user).count()
                Alarme.objects.filter(utilisateur=user).delete()
                reponse_ia  = (f"C'est fait {user.username} ! J'ai supprimé toutes "
                               f"tes {count} alarmes.")
                action_data = {"action": "DELETE_ALL_ALARMS"}
            else:
                heure_str, h, mn = _extraire_heure(p_low)
                if heure_str:
                    alarme = Alarme.objects.filter(utilisateur=user, heure=heure_str).first()
                    if alarme:
                        alarme.delete()
                        reponse_ia  = f"C'est fait ! L'alarme de {heure_str} est supprimée."
                        action_data = {"action": "DELETE_ALARM", "heure": heure_str}
                    else:
                        reponse_ia = (f"Je n'ai pas trouvé d'alarme à {heure_str} "
                                      f"{user.username}.")
                else:
                    # Supprime la dernière alarme créée
                    alarme = (Alarme.objects.filter(utilisateur=user)
                              .order_by('-date_creation').first())
                    if alarme:
                        h_aff = alarme.heure.strftime('%H:%M')
                        alarme.delete()
                        reponse_ia  = f"L'alarme de {h_aff} a été supprimée {user.username}."
                        action_data = {"action": "DELETE_ALARM"}
                    else:
                        reponse_ia = f"Tu n'as aucune alarme {user.username}."

        # ── 2. Modification d'alarme ─────────────────────────────────────
        elif (any(m in p_low for m in MOTS_MODIF)
              and any(x in p_low for x in ["alarme", "réveil", "reveil"])):

            heures = re.findall(r'\b(\d{1,2})\s*[hH:]\s*(\d{2})\b', p_low)
            if len(heures) >= 2:
                anc = f"{int(heures[0][0]):02d}:{heures[0][1]}"
                nouv = f"{int(heures[1][0]):02d}:{heures[1][1]}"
                alarme = Alarme.objects.filter(utilisateur=user, heure=anc).first()
                if alarme:
                    h, ms = map(int, nouv.split(':'))
                    alarme.heure   = dt_time(h, ms)
                    alarme.message = f"Alarme de {user.username} à {nouv}"
                    alarme.save()
                    reponse_ia  = (f"C'est modifié {user.username} ! "
                                   f"Ton alarme passe de {anc} à {nouv}.")
                    action_data = {"action": "SET_ALARM", "heure": nouv}
                else:
                    reponse_ia = f"Je n'ai pas trouvé d'alarme à {anc} {user.username}."
            elif len(heures) == 1:
                nouv = f"{int(heures[0][0]):02d}:{heures[0][1]}"
                alarme = (Alarme.objects.filter(utilisateur=user)
                          .order_by('-date_creation').first())
                if alarme:
                    anc_aff = alarme.heure.strftime('%H:%M')
                    h, ms = map(int, nouv.split(':'))
                    alarme.heure   = dt_time(h, ms)
                    alarme.message = f"Alarme de {user.username} à {nouv}"
                    alarme.save()
                    reponse_ia  = (f"C'est fait ! Ton alarme passe de "
                                   f"{anc_aff} à {nouv} {user.username}.")
                    action_data = {"action": "SET_ALARM", "heure": nouv}
                else:
                    reponse_ia = f"Tu n'as aucune alarme à modifier {user.username}."
            else:
                reponse_ia = (f"Précise les heures {user.username}. "
                              "Exemple : 'change mon alarme de 7h à 8h'.")

        # ── 3. Création d'alarme ─────────────────────────────────────────
        elif any(m in p_low for m in MOTS_ALARME):
            heure_str, h, mn = _extraire_heure(p_low)
            if heure_str and h is not None:
                Alarme.objects.create(
                    utilisateur=user,
                    heure=dt_time(h, mn),
                    message=f"Alarme de {user.username} à {heure_str}",
                    activee=True,
                )
                # Réponse naturelle et orale
                reponse_ia = (
                    f"C'est noté {user.username} ! "
                    f"Je programme une alarme pour {heure_str}. "
                    f"Je te réveillerai à {heure_str}."
                )
                action_data = {"action": "SET_ALARM", "heure": heure_str}
            else:
                reponse_ia = (f"À quelle heure dois-je régler l'alarme "
                              f"{user.username} ?")

        # ── 4. Appel téléphonique ────────────────────────────────────────
        elif any(m in p_low for m in MOTS_APPEL):
            num = re.search(r'(\d[\d\s\-\.]{5,})', prompt)
            if num:
                numero = re.sub(r'[\s\-\.]', '', num.group(1))
                reponse_ia  = (f"J'appelle le {numero} pour toi "
                               f"{user.username}. Une seconde…")
                action_data = {"action": "MAKE_PHONE_CALL", "number": numero}
                cache.set(f"will_pending_action_{user.id}", action_data, timeout=30)
            else:
                nom_m = re.search(
                    r'(?:appelle|appeler|appel|contact|téléphone|telephone)'
                    r'\s+([a-zA-ZÀ-ÿ\s]+)',
                    p_low
                )
                if nom_m:
                    nom = nom_m.group(1).strip()
                    reponse_ia  = f"Je cherche {nom.capitalize()} dans tes contacts…"
                    action_data = {"action": "SEARCH_AND_CALL", "name": nom}
                    cache.set(f"will_pending_action_{user.id}", action_data, timeout=30)
                else:
                    reponse_ia = f"Qui veux-tu appeler {user.username} ?"

        # ── 5. Météo ─────────────────────────────────────────────────────
        elif any(m in p_low for m in MOTS_METEO):
            # Extrait la ville si précisée, sinon Lomé par défaut
            ville = "Lomé"
            m_ville = re.search(
                r'(?:à|a|pour|sur|de)\s+([A-ZÀ-ÿa-z\-]+)', prompt
            )
            if m_ville:
                ville = m_ville.group(1).strip().capitalize()

            api_key = "00192cef4b75b678c3a83924c08ce994"
            url = (f"https://api.openweathermap.org/data/2.5/weather"
                   f"?q={ville}&appid={api_key}&units=metric&lang=fr")
            try:
                r = requests.get(url, timeout=5)
                d = r.json()
                if r.status_code == 200:
                    temp  = round(d['main']['temp'])
                    desc  = d['weather'][0]['description']
                    humid = d['main']['humidity']
                    reponse_ia = (
                        f"À {ville} en ce moment : {temp} degrés, {desc}. "
                        f"L'humidité est de {humid} pourcent."
                    )
                    action_data = {"action": "SHOW_WEATHER", "city": ville}
                else:
                    reponse_ia = f"Je n'ai pas trouvé la météo pour {ville}."
            except Exception:
                reponse_ia = "Je ne peux pas récupérer la météo pour l'instant."

        # ── 6. IA Mistral (conversation générale) ───────────────────────
        else:
            contexte = (
                f"Tu es Will, l'assistant vocal personnel de {user.username}. "
                "Tu réponds TOUJOURS en français, de façon courte, naturelle et chaleureuse. "
                "Tes réponses sont lues à voix haute, donc évite les listes et le markdown. "
                "Ton prénom est Will. Si on te demande qui tu es, dis que tu es Will, "
                f"l'assistant de {user.username}."
            )
            try:
                chat_res = client.chat.complete(
                    model="open-mistral-7b",
                    messages=[
                        {"role": "system", "content": contexte},
                        {"role": "user",   "content": prompt},
                    ],
                    max_tokens=200,
                )
                reponse_ia = chat_res.choices[0].message.content.strip()
                # Nettoie les caractères markdown qui sonnent mal à l'oral
                reponse_ia = re.sub(r'[*_#`]', '', reponse_ia)
            except Exception as e:
                reponse_ia = "Désolé, je n'ai pas pu répondre pour l'instant."
                print(f"❌ Mistral error: {e}")

        # ── Sauvegarde en base ───────────────────────────────────────────
        msg = Message.objects.create(
            utilisateur=user,
            message_utilisateur=prompt,
            reponse_ia=reponse_ia,
        )

        return Response({
            "id":           msg.id,
            "reponse_ia":   reponse_ia,   # ← Will lit ça à voix haute
            "action_to_do": action_data,  # ← Flutter exécute ça
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({"error": str(e)}, status=500)


# ═══════════════════════════════════════════════════════════════════════════
#  ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

# ── 1. Inscription ──────────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user  = serializer.save()
        token = Token.objects.create(user=user)
        return Response(
            {'token': token.key, 'username': user.username},
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── 2. Connexion ────────────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user     = authenticate(username=username, password=password)
    if user:
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {'token': token.key, 'username': user.username},
            status=status.HTTP_200_OK,
        )
    return Response({'error': 'Identifiants invalides'}, status=status.HTTP_401_UNAUTHORIZED)


# ── 3. Profil ───────────────────────────────────────────────────────────────
@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def profile(request):
    user = request.user
    if request.method == 'GET':
        return Response(UserSerializer(user).data)
    elif request.method == 'PUT':
        s = UserSerializer(user, data=request.data, partial=True)
        if s.is_valid():
            s.save()
            return Response(s.data)
        return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)
    elif request.method == 'DELETE':
        user.delete()
        return Response({"message": "Compte supprimé"}, status=status.HTTP_204_NO_CONTENT)


# ── 4. Chat (interface écrite) ──────────────────────────────────────────────
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def chat(request):
    user = request.user
    if request.method == 'GET':
        msgs = Message.objects.filter(utilisateur=user).order_by('-date')
        return Response(MessageSerializer(msgs, many=True).data)
    prompt = request.data.get('message', '').strip()
    if not prompt:
        return Response({"error": "Message vide"}, status=status.HTTP_400_BAD_REQUEST)
    return _traiter_message(user, prompt)


# ── 5. Commande vocale (depuis le téléphone via will_service.dart) ──────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def voice_command(request):
    """
    Appelé par will_service.dart après détection du mot-clé sur le téléphone.
    Le téléphone reconnaît la voix, envoie le texte ici, Will répond.
    La réponse 'reponse_ia' est ensuite lue oralement par flutter_tts.
    """
    prompt = request.data.get('message', '').strip()
    if not prompt:
        return Response({"error": "Message vide"}, status=status.HTTP_400_BAD_REQUEST)
    print(f"🎙️ Commande vocale de [{request.user.username}] : {prompt}")
    return _traiter_message(request.user, prompt)


# ── 6. Alarmes ──────────────────────────────────────────────────────────────
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def alarm_list_create(request):
    if request.method == 'GET':
        alarmes = Alarme.objects.filter(utilisateur=request.user)
        return Response(AlarmeSerializer(alarmes, many=True).data)
    s = AlarmeSerializer(data=request.data)
    if s.is_valid():
        s.save(utilisateur=request.user)
        return Response(s.data, status=status.HTTP_201_CREATED)
    return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def alarm_delete(request, pk):
    alarme = get_object_or_404(Alarme, pk=pk, utilisateur=request.user)
    alarme.delete()
    return Response({"message": "Alarme supprimée"}, status=status.HTTP_204_NO_CONTENT)


# ── 7. Statut de Will (activer/désactiver depuis l'app) ─────────────────────
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def check_will(request):
    """
    GET  → retourne si Will est actif pour cet utilisateur.
    POST → active ou désactive Will.
            { "est_actif": true/false }
            { "clear_action": true }   ← efface une action en attente
    """
    user = request.user
    status_obj, _ = AssistantStatus.objects.get_or_create(utilisateur=user)

    if request.method == 'GET':
        pending = cache.get(f"will_pending_action_{user.id}")
        if pending:
            cache.delete(f"will_pending_action_{user.id}")
        return Response({
            "est_actif":      status_obj.est_actif,
            "pending_action": pending,
        })

    # POST
    if 'est_actif' in request.data:
        status_obj.est_actif = bool(request.data['est_actif'])
        status_obj.save()
        cache.set("will_global_est_actif", status_obj.est_actif, timeout=300)

    if request.data.get('clear_action'):
        cache.delete(f"will_pending_action_{user.id}")

    return Response({"est_actif": status_obj.est_actif})


# ── 8. Météo (endpoint dédié, appelable depuis l'app) ───────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_weather(request):
    city    = request.query_params.get('city', 'Lome')
    api_key = "00192cef4b75b678c3a83924c08ce994"
    url     = (f"https://api.openweathermap.org/data/2.5/forecast"
               f"?q={city}&appid={api_key}&units=metric&lang=fr")
    try:
        r = requests.get(url, timeout=5)
        d = r.json()
        if r.status_code != 200:
            return Response({"success": False, "error": "Ville non trouvée"}, status=400)

        jours_fr = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
        tz       = pytz.timezone('Africa/Lome')
        forecast = []
        for item in d.get('list', [])[::8]:
            local_dt = datetime.fromtimestamp(item['dt'], pytz.UTC).astimezone(tz)
            forecast.append({
                "day":         jours_fr[local_dt.weekday()],
                "full_date":   local_dt.strftime("%d %b"),
                "temp":        round(item['main']['temp']),
                "condition":   item['weather'][0]['main'],
                "icon":        item['weather'][0]['icon'],
                "humidity":    item['main']['humidity'],
                "wind":        round(item.get('wind', {}).get('speed', 0) * 3.6, 1),
                "description": item['weather'][0]['description'].capitalize(),
            })
        return Response({"success": True, "data": {
            "city":     d.get("city", {}).get("name", city),
            "forecast": forecast,
        }})
    except Exception as e:
        return Response({"success": False, "error": str(e)}, status=500)


# ── 9. Synchronisation des apps installées (depuis le téléphone) ────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_apps(request):
    global APPS_DATABASE
    apps = request.data.get('apps', {})
    if apps:
        APPS_DATABASE = {k.lower(): v for k, v in apps.items()}
        print(f"✅ {len(APPS_DATABASE)} apps synchronisées depuis {request.user.username}.")
        return Response({"status": "success", "count": len(APPS_DATABASE)})
    return Response({"status": "error", "message": "Aucune app reçue"}, status=400)


# ── 10. Appel téléphonique direct ───────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def make_call(request):
    numero = request.data.get('phone_number', '').strip()
    if not numero:
        return Response({"error": "Numéro requis"}, status=400)
    cache.set(
        f"will_pending_action_{request.user.id}",
        {"action": "MAKE_PHONE_CALL", "number": numero},
        timeout=30,
    )
    return Response({"message": f"Appel vers {numero} en cours…"})