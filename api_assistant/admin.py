from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Message, Alarme, AssistantStatus, Evaluation


# ── Personnalisation de l'admin User (autoriser/bloquer accès) ───────────────

class AssistantStatusInline(admin.StackedInline):
    model = AssistantStatus
    can_delete = False
    verbose_name_plural = "Statut de Will"
    readonly_fields = ('derniere_detection',)


class UserAdmin(BaseUserAdmin):
    inlines = (AssistantStatusInline,)
    list_display = ('username', 'email', 'is_active', 'is_staff', 'date_joined', 'nb_messages')
    list_filter = ('is_active', 'is_staff', 'date_joined')
    list_editable = ('is_active',)  # Activer/désactiver un compte directement
    actions = ['activer_comptes', 'desactiver_comptes']

    def nb_messages(self, obj):
        return obj.message_set.count()
    nb_messages.short_description = 'Messages'

    @admin.action(description='✅ Activer les comptes sélectionnés')
    def activer_comptes(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} compte(s) activé(s).")

    @admin.action(description='🚫 Désactiver les comptes sélectionnés')
    def desactiver_comptes(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} compte(s) désactivé(s).")


# Remplace l'admin User par défaut
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# ── Messages ─────────────────────────────────────────────────────────────────

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'message_court', 'reponse_courte', 'date')
    list_filter = ('utilisateur', 'date')
    search_fields = ('message_utilisateur', 'reponse_ia', 'utilisateur__username')
    readonly_fields = ('date', 'utilisateur', 'message_utilisateur', 'reponse_ia')
    ordering = ('-date',)
    date_hierarchy = 'date'

    def message_court(self, obj):
        return obj.message_utilisateur[:50] + '...' if len(obj.message_utilisateur) > 50 else obj.message_utilisateur
    message_court.short_description = 'Message utilisateur'

    def reponse_courte(self, obj):
        return obj.reponse_ia[:50] + '...' if len(obj.reponse_ia) > 50 else obj.reponse_ia
    reponse_courte.short_description = 'Réponse Will'


# ── Alarmes ───────────────────────────────────────────────────────────────────

@admin.register(Alarme)
class AlarmeAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'message', 'heure', 'activee', 'date_creation')
    list_filter = ('activee', 'utilisateur')
    search_fields = ('message', 'utilisateur__username')
    list_editable = ('activee',)
    ordering = ('heure',)
    actions = ['activer_alarmes', 'desactiver_alarmes']

    @admin.action(description='✅ Activer les alarmes sélectionnées')
    def activer_alarmes(self, request, queryset):
        queryset.update(activee=True)

    @admin.action(description='🔕 Désactiver les alarmes sélectionnées')
    def desactiver_alarmes(self, request, queryset):
        queryset.update(activee=False)


# ── Statut Assistant ──────────────────────────────────────────────────────────

@admin.register(AssistantStatus)
class AssistantStatusAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'est_actif', 'est_reveille', 'derniere_detection')
    list_filter = ('est_actif', 'est_reveille')
    search_fields = ('utilisateur__username',)
    readonly_fields = ('derniere_detection',)
    list_editable = ('est_actif',)


# ── Évaluations ───────────────────────────────────────────────────────────────

@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'note_etoiles', 'commentaire_court', 'date')
    list_filter = ('note', 'date')
    search_fields = ('commentaire', 'utilisateur__username')
    readonly_fields = ('utilisateur', 'note', 'commentaire', 'date')
    ordering = ('-date',)
    date_hierarchy = 'date'

    def note_etoiles(self, obj):
        return '⭐' * obj.note
    note_etoiles.short_description = 'Note'

    def commentaire_court(self, obj):
        if not obj.commentaire:
            return '—'
        return obj.commentaire[:60] + '...' if len(obj.commentaire) > 60 else obj.commentaire
    commentaire_court.short_description = 'Commentaire'


# ── Personnalisation du site Admin ────────────────────────────────────────────
admin.site.site_header = "Will — Administration"
admin.site.site_title = "Will Admin"
admin.site.index_title = "Tableau de bord"