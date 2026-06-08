from django.contrib import admin
from .models import Message, Alarme, AssistantStatus


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'message_court', 'date')
    list_filter = ('utilisateur', 'date')
    search_fields = ('message_utilisateur', 'reponse_ia', 'utilisateur__username')
    readonly_fields = ('date',)
    ordering = ('-date',)

    def message_court(self, obj):
        return obj.message_utilisateur[:60] + '...' if len(obj.message_utilisateur) > 60 else obj.message_utilisateur
    message_court.short_description = 'Message'


@admin.register(Alarme)
class AlarmeAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'message', 'heure', 'activee', 'date_creation')
    list_filter = ('activee', 'utilisateur')
    search_fields = ('message', 'utilisateur__username')
    list_editable = ('activee',)
    ordering = ('heure',)


@admin.register(AssistantStatus)
class AssistantStatusAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'est_actif', 'est_reveille', 'derniere_detection')
    list_filter = ('est_actif', 'est_reveille')
    search_fields = ('utilisateur__username',)
    readonly_fields = ('derniere_detection',)