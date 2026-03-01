from rest_framework import serializers
from django.contrib.auth import get_user_model
from pharmacies.models import Pharmacy

User = get_user_model()


class PharmacySerializer(serializers.ModelSerializer):
    class Meta:
        model = Pharmacy
        fields = '__all__'

class UserSerializer(serializers.ModelSerializer):
    pharmacy = PharmacySerializer(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'role', 'pharmacy', 'first_name', 'last_name')


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')
        extra_kwargs = {'email': {'required': False, 'allow_blank': True}}


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'password', 'email', 'role', 'pharmacy')

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class RegisterPharmacySerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)
    username = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True)  # for pharmacy record; use placeholder if blank
    pharmacy_name = serializers.CharField()
    license_number = serializers.CharField()
    gst_number = serializers.CharField()
    contact_person = serializers.CharField()
    phone = serializers.CharField()
    address = serializers.CharField()

    def create(self, validated_data):
        # Pharmacy model requires email; use placeholder if not provided
        email = validated_data.get('email') or f"{validated_data['username']}@pharmacy.local"
        pharmacy_data = {
            'pharmacy_name': validated_data['pharmacy_name'],
            'license_number': validated_data['license_number'],
            'gst_number': validated_data['gst_number'],
            'contact_person': validated_data['contact_person'],
            'phone': validated_data['phone'],
            'email': email,
            'address': validated_data['address'],
        }
        pharmacy = Pharmacy.objects.create(**pharmacy_data)

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            role='pharmacy',
            pharmacy=pharmacy
        )
        return user
