"""
Django settings for PPE project.
"""

from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv

load_dotenv()  # charge les variables du fichier .env (GEMINI_API_KEY, etc.)

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Sécurité ────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-lxni!cqi9+dh9q#^i&u(78ndw4fb=j!+icrea^!(^2e-e@e+%z')

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = ['*']

# ── Applications ─────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'jazzmin',                          # ← DOIT être en premier
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

# ── Middleware ───────────────────────────────────────────────────────────────
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

# ── REST Framework ───────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
}

# ── CORS ─────────────────────────────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = True

# ── Twilio ───────────────────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID  = os.environ.get('TWILIO_ACCOUNT_SID', 'TON_ACCOUNT_SID')
TWILIO_AUTH_TOKEN   = os.environ.get('TWILIO_AUTH_TOKEN', 'TON_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '+17756000893')

# ── MQTT (broker Mosquitto tournant sur le PC pendant la démo) ───────────────
# En local, le broker tourne sur le même PC que Django → host = 127.0.0.1
# Pour la démo, le PC et l'ESP32 doivent être sur le même réseau Wi-Fi ;
# remplacer MQTT_BROKER_HOST par l'IP du PC sur ce réseau (ex. 192.168.1.42)
# si l'ESP32 n'arrive pas à joindre 127.0.0.1.
MQTT_BROKER_HOST = os.environ.get('MQTT_BROKER_HOST', '127.0.0.1')
MQTT_BROKER_PORT = int(os.environ.get('MQTT_BROKER_PORT', '1883'))
MQTT_USERNAME    = os.environ.get('MQTT_USERNAME', 'will')
MQTT_PASSWORD    = os.environ.get('MQTT_PASSWORD', 'will2026')

ROOT_URLCONF = 'PPE.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

# ── Base de données ──────────────────────────────────────────────────────────
# PostgreSQL sur Render (via DATABASE_URL), SQLite en local
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            ssl_require=True,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ── Validation mots de passe ─────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Internationalisation ──────────────────────────────────────────────────────
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE     = 'Africa/Abidjan'
USE_I18N      = True
USE_TZ        = True

# ── Fichiers statiques (whitenoise) ──────────────────────────────────────────
STATIC_URL  = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Jazzmin (thème admin) ─────────────────────────────────────────────────────
JAZZMIN_SETTINGS = {
    "site_title": "Will Admin",
    "site_header": "Will – Assistant IA",
    "site_brand": "✨ Will",
    "site_logo": None,
    "welcome_sign": "Bienvenue dans le panneau de gestion de Will",
    "copyright": "PPE – IPNET 2026",
    "search_model": ["auth.user", "api_assistant.message"],
    "topmenu_links": [
        {"name": "🏠 Accueil", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "🌐 API", "url": "/api/", "new_window": True},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user-circle",
        "auth.Group": "fas fa-users",
        "api_assistant.Message": "fas fa-comment-dots",
        "api_assistant.Alarme": "fas fa-bell",
        "api_assistant.AssistantStatus": "fas fa-robot",
        "api_assistant.Evaluation": "fas fa-star",
        "api_assistant.AppareilConnecte": "fas fa-plug",
        "api_assistant.CommandeAppareil": "fas fa-terminal",
    },
    "default_icon_parents": "fas fa-folder",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": True,
    "custom_css": None,
    "custom_js": None,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "language_chooser": False,
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-white",
    "accent": "accent-primary",
    "navbar": "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-light-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "flatly",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-outline-primary",
        "secondary": "btn-outline-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
    "actions_sticky_top": True,
}