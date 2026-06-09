#!/usr/bin/env bash
set -e
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
echo "from django.contrib.auth.models import User; User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@will.com', 'will2026')" | python manage.py shell
echo "✅ Déploiement terminé"