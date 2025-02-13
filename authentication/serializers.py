from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User  
        fields = ['id', 'username', 'password', 'email', 'phone_number', 'address']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        """
        Custom create method to ensure password is hashed when creating a new user.
        Also assigns a default username if not provided.
        """
        username = validated_data.get('username', validated_data['email'])  # Default username to email if missing
        user = User.objects.create_user(
            email=validated_data['email'],
            username=username,
            password=validated_data['password'],
            phone_number=validated_data.get('phone_number', ''),
            address=validated_data.get('address', '')
        )
        return user
