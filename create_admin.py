import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PPE.settings')
django.setup()

from django.contrib.auth.models import User

username = os.environ.get('ADMIN_USERNAME', 'admin')
password = os.environ.get('ADMIN_PASSWORD', 'Admin1234')
email = os.environ.get('ADMIN_EMAIL', 'admin@will.com')

if User.objects.filter(username=username).exists():
    u = User.objects.get(username=username)
    u.set_password(password)
    u.is_superuser = True
    u.is_staff = True
    u.save()
    print(f"✅ Admin '{username}' mis à jour")
else:
    User.objects.create_superuser(username, email, password)
    print(f"✅ Admin '{username}' créé")
