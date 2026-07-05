from django.apps import AppConfig

class ApiAssistantConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api_assistant'

    def ready(self):
        # L'écoute et le traitement vocal sont maintenant gérés par le frontend (téléphone).
        # Django sert uniquement d'API standard sans thread d'arrière-plan requis au démarrage.
        pass