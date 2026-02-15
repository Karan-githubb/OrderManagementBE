from rest_framework import serializers
from django.contrib.auth import get_user_model
from pharmacies.models import Pharmacy
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = User.EMAIL_FIELD

    def validate(self, attrs):
        # Allow passing 'email' instead of 'username'
        if 'email' in attrs:
            attrs[self.username_field] = attrs.pop('email')
        return super().validate(attrs)

class PharmacySerializer(serializers.ModelSerializer):
    class Meta:
        model = Pharmacy
        fields = '__all__'

class UserSerializer(serializers.ModelSerializer):
    pharmacy = PharmacySerializer(read_only=True)
    
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'role', 'pharmacy', 'first_name', 'last_name')

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('email', 'password', 'role', 'pharmacy')

    def create(self, validated_data):
        email = validated_data.get('email')
        validated_data['username'] = email
        user = User.objects.create_user(**validated_data)
        return user

class RegisterPharmacySerializer(serializers.Serializer):

    password = serializers.CharField(write_only=True)
    email = serializers.EmailField()
    pharmacy_name = serializers.CharField()
    license_number = serializers.CharField()
    gst_number = serializers.CharField(required=False, allow_blank=True)
    contact_person = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)

    def create(self, validated_data):
        pharmacy_data = {
            'pharmacy_name': validated_data['pharmacy_name'],
            'license_number': validated_data['license_number'],
            'gst_number': validated_data.get('gst_number', ''),
            'contact_person': validated_data.get('contact_person', ''),
            'phone': validated_data.get('phone', ''),
            'email': validated_data['email'],
            'address': validated_data.get('address', ''),
        }
        pharmacy = Pharmacy.objects.create(**pharmacy_data)
        
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=validated_data['password'],
            role='pharmacy',
            pharmacy=pharmacy
        )
        return user
