from django.contrib import admin
from .models import (
    Message, Alarme, AssistantStatus,
    Piece, AppareilConnecte, EtatAppareil, CommandeAppareil,
    Playlist, MorceauPlaylist,
)


# ═══════════════════════════════════════════════════════════════════════════
#  SUPERVISION DOMOTIQUE — panneau d'administration centralisé
# ═══════════════════════════════════════════════════════════════════════════

class AppareilInline(admin.TabularInline):
    """Affiche les appareils directement dans la fiche d'une pièce."""
    model = AppareilConnecte
    extra = 0
    fields = ('nom', 'type_appareil', 'protocole', 'canal', 'est_actif')
    show_change_link = True


@admin.register(Piece)
class PieceAdmin(admin.ModelAdmin):
    list_display  = ('nom', 'utilisateur', 'esp32_id', 'nb_appareils', 'date_ajout')
    list_filter   = ('utilisateur',)
    search_fields = ('nom', 'esp32_id', 'utilisateur__username')
    inlines       = [AppareilInline]

    @admin.display(description="Nb appareils")
    def nb_appareils(self, obj):
        return obj.appareils.count()


class EtatAppareilInline(admin.StackedInline):
    """Affiche l'état courant directement dans la fiche de l'appareil."""
    model = EtatAppareil
    extra = 0
    can_delete = False


@admin.register(AppareilConnecte)
class AppareilConnecteAdmin(admin.ModelAdmin):
    list_display  = (
        'nom', 'utilisateur', 'piece', 'type_appareil',
        'protocole', 'topic_mqtt', 'est_actif_affiche', 'allume_affiche',
    )
    list_filter   = ('type_appareil', 'protocole', 'est_actif', 'piece')
    search_fields = ('nom', 'utilisateur__username', 'topic_mqtt', 'adresse_ip')
    inlines       = [EtatAppareilInline]
    list_select_related = ('piece', 'utilisateur', 'etat')

    @admin.display(boolean=True, description="Actif")
    def est_actif_affiche(self, obj):
        return obj.est_actif

    @admin.display(boolean=True, description="Allumé")
    def allume_affiche(self, obj):
        return getattr(obj.etat, 'allume', False)


@admin.register(CommandeAppareil)
class CommandeAppareilAdmin(admin.ModelAdmin):
    """Journal de toutes les commandes domotique envoyées — pour audit/debug."""
    list_display  = ('date_commande', 'utilisateur', 'appareil', 'commande',
                      'parametres', 'statut', 'source')
    list_filter   = ('statut', 'source', 'commande', 'date_commande')
    search_fields = ('appareil__nom', 'utilisateur__username', 'commande')
    date_hierarchy = 'date_commande'
    readonly_fields = ('date_commande',)

    def has_add_permission(self, request):
        # Le journal de commandes n'est généré que par l'application — pas
        # de création manuelle depuis l'admin.
        return False


# ═══════════════════════════════════════════════════════════════════════════
#  SUPERVISION ASSISTANT (déjà existant, conservé)
# ═══════════════════════════════════════════════════════════════════════════

@admin.register(AssistantStatus)
class AssistantStatusAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'est_actif', 'est_reveille', 'derniere_detection')
    list_filter  = ('est_actif', 'est_reveille')
    search_fields = ('utilisateur__username',)


admin.site.register(Message)
admin.site.register(Alarme)


# ═══════════════════════════════════════════════════════════════════════════
#  PLAYLISTS
# ═══════════════════════════════════════════════════════════════════════════

class MorceauInline(admin.TabularInline):
    model = MorceauPlaylist
    extra = 0
    fields = ('titre', 'chemin_local', 'ordre')


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display  = ('nom', 'utilisateur', 'nb_morceaux', 'date_creation')
    list_filter   = ('utilisateur',)
    search_fields = ('nom', 'utilisateur__username')
    inlines       = [MorceauInline]

    @admin.display(description="Nb morceaux")
    def nb_morceaux(self, obj):
        return obj.morceaux.count()


admin.site.site_header   = "WILL — Administration centralisée"
admin.site.site_title    = "WILL Admin"
admin.site.index_title   = "Supervision des utilisateurs, pièces et appareils"