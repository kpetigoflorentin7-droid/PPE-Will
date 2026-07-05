from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()  # charge les variables depuis le fichier .env à la racine du projet

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-lxni!cqi9+dh9q#^i&u(78ndw4fb=j!+icrea^!(^2e-e@e+%z',
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')

CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if o
]


# Application definition

INSTALLED_APPS = [
    'jazzmin',                      # ← doit être AVANT django.contrib.admin
    'corsheaders',
    'rest_framework.authtoken',
    'rest_framework',
    'api_assistant',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
#  CLÉS API / URLS EXTERNES — jamais en dur dans le code, toujours via
#  variables d'environnement (fichier .env en local, variables d'env sur
#  Render en prod)
# ─────────────────────────────────────────────────────────────────────────────
GEMINI_API_KEY       = os.environ.get('GEMINI_API_KEY', '')
OPENWEATHER_API_KEY  = os.environ.get('OPENWEATHER_API_KEY', '')

TWILIO_ACCOUNT_SID   = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN    = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER  = os.environ.get('TWILIO_PHONE_NUMBER', '')

# Maison virtuelle Unity (via tunnel ngrok depuis le PC qui héberge Unity)
UNITY_API_URL = os.environ.get('UNITY_API_URL', 'http://localhost:5005')

ROOT_URLCONF = 'PPE.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'PPE.wsgi.application'


# ─────────────────────────────────────────────────────────────────────────────
#  BASE DE DONNÉES — PostgreSQL (locale en dev, Render en prod, mêmes
#  variables d'environnement des deux côtés)
# ─────────────────────────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE':   'django.db.backends.postgresql',
        'NAME':     os.environ.get('DB_NAME', 'will_db'),
        'USER':     os.environ.get('DB_USER', 'will_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST':     os.environ.get('DB_HOST', 'localhost'),
        'PORT':     os.environ.get('DB_PORT', '5432'),
    }
}

# ─────────────────────────────────────────────────────────────────────────────
#  FICHIERS STATIQUES (CSS/JS de l'admin) — servis par whitenoise en prod
# ─────────────────────────────────────────────────────────────────────────────
STATIC_URL  = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']   # ← notre CSS personnalisé vit ici
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
#  MQTT — connexion au broker Mosquitto local (architecture Edge Computing)
# ─────────────────────────────────────────────────────────────────────────────
MQTT_BROKER_HOST = os.environ.get('WILL_MQTT_HOST', 'localhost')
MQTT_BROKER_PORT = int(os.environ.get('WILL_MQTT_PORT', '1883'))
MQTT_USERNAME    = os.environ.get('WILL_MQTT_USER') or None
MQTT_PASSWORD    = os.environ.get('WILL_MQTT_PASSWORD') or None
MQTT_KEEPALIVE   = 60


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Lome'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
CORS_ALLOW_ALL_ORIGINS = True


# ─────────────────────────────────────────────────────────────────────────────
#  JAZZMIN — Interface moderne et attractive
# ─────────────────────────────────────────────────────────────────────────────
JAZZMIN_SETTINGS = {
    "site_title":   "WILL Assistant Intelligent",
    "site_header":  "WILL",
    "site_brand":   "🏠 WILL Assistant",
    "welcome_sign": "Bienvenue sur l'interface d'administration de WILL",
    "copyright":    "IPNET — Projet WILL",

    "site_logo": None,
    "site_logo_classes": "img-fluid",
    "site_icon": "fa-robot",

    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],

    # Polices en local uniquement — évite toute dépendance à un CDN externe
    # pendant la démo (fiable même sur un réseau qui bloque certains domaines)
    "use_google_fonts_cdn": False,

    "search_model": ["auth.User", "api_assistant.AppareilConnecte", "api_assistant.Message"],

    "topmenu_links": [
        {"name": "Tableau de bord", "url": "admin:index"},
        {"model": "auth.User"},
        {"app": "api_assistant"},
    ],

    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user-circle",
        "auth.Group": "fas fa-users",

        "api_assistant.Message": "fas fa-comments",
        "api_assistant.Alarme": "fas fa-bell",
        "api_assistant.AssistantStatus": "fas fa-power-off",
        "api_assistant.Piece": "fas fa-door-open",
        "api_assistant.AppareilConnecte": "fas fa-plug",
        "api_assistant.EtatAppareil": "fas fa-toggle-on",
        "api_assistant.CommandeAppareil": "fas fa-terminal",
        "api_assistant.Playlist": "fas fa-music",
        "api_assistant.MorceauPlaylist": "fas fa-file-audio",
        "api_assistant.AppInstallee": "fas fa-mobile-alt",
    },

    "default_icon_parents": "fas fa-folder-open",
    "default_icon_children": "fas fa-circle",

    "related_modal_active": True,
    "save_on_top": True,

    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "auth.user": "collapsible",
        "auth.group": "vertical_tabs",
    },

    # Notre CSS personnalisé — chemin relatif dans STATICFILES_DIRS, pas du texte brut
    "custom_css": "css/admin_custom.css",
    "custom_js": None,
}

# ─────────────────────────────────────────────────────────────────────────────
#  UI TWEAKS — Thème moderne
# ─────────────────────────────────────────────────────────────────────────────
JAZZMIN_UI_TWEAKS = {
    "theme": "darkly",
    "dark_mode_theme": "darkly",

    "navbar": "navbar-dark",
    "no_navbar_border": True,
    "navbar_fixed": True,

    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_flat_style": True,

    "brand_colour": "navbar-primary",
    "accent": "accent-info",

    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },

    "actions_sticky_top": True,
    "show_footer": True,
    "footer_fixed": False,
}