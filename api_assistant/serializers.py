from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Message,Alarme

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']
        extra_kwargs = {'password': {'write_only': True}} # Le mot de passe ne sera jamais renvoyé en texte clair

    def create(self, validated_data):
        # Cette méthode permet de crypter le mot de passe avant de sauvegarder
        user = User.objects.create_user(**validated_data)
        return user
    

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'utilisateur', 'message_utilisateur', 'reponse_ia', 'date']
        read_only_fields = ['utilisateur', 'reponse_ia', 'date']
        
class AlarmeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alarme
        fields = ['id', 'heure', 'message', 'activee']
        read_only_fields = ['id']