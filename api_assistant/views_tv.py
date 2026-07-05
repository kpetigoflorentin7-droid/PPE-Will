# api_assistant/views_tv.py
# ─────────────────────────────────────────────────────────────────────────────
# Détection vocale pour ouvrir une application de streaming (YouTube, Netflix)
# sur la Smart TV. Le lancement réel se fait côté Flutter via le protocole
# DIAL (découverte de la TV sur le réseau WiFi local) — le backend se
# contente de détecter l'intention et la plateforme demandée.
#
# "Will, ouvre Netflix"          → action_to_do: OPEN_TV_APP / netflix
# "Will, ouvre YouTube"          → action_to_do: OPEN_TV_APP / youtube
# "Will, ouvre une plateforme"   → Will demande de préciser (pas d'action)
# ─────────────────────────────────────────────────────────────────────────────

MOTS_OUVRIR = [
    "ouvre", "ouvrir", "lance", "lancer", "va sur", "mets", "mettre",
    "démarre", "demarre", "active",
]

PLATEFORMES = {
    "netflix":  "netflix",
    "youtube":  "youtube",
    "you tube": "youtube",
}

# Mots qui indiquent qu'on parle bien de la télé/streaming (évite les faux
# positifs du type "ouvre l'application Calculatrice")
MOTS_CONTEXTE_TV = ["télé", "tele", "tv", "netflix", "youtube", "you tube"]


def _detecter_commande_tv_app(prompt: str, user) -> dict | None:
    """
    Détecte une demande d'ouverture d'application de streaming sur la TV.
    Retourne un dict avec 'reponse_ia' et 'action_to_do', ou None si la
    commande ne concerne pas ça.
    """
    p = prompt.lower().strip()

    if not any(mot in p for mot in MOTS_OUVRIR):
        return None

    # Cherche quelle plateforme est demandée
    plateforme = None
    for cle, valeur in PLATEFORMES.items():
        if cle in p:
            plateforme = valeur
            break

    if plateforme is None:
        # Pas de plateforme détectée — on vérifie que la phrase parle bien
        # de la télé avant de répondre (sinon on laisse passer à une autre
        # détection, ex: "ouvre Chrome" n'a rien à voir).
        if not any(mot in p for mot in MOTS_CONTEXTE_TV):
            return None
        return {
            "reponse_ia":   "Sur quelle plateforme veux-tu aller : YouTube ou Netflix ?",
            "action_to_do": {},
        }

    return {
        "reponse_ia":   f"J'ouvre {plateforme.capitalize()} sur la télé.",
        "action_to_do": {
            "action":   "OPEN_TV_APP",
            "platform": plateforme,
        },
    }