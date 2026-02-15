from rest_framework import viewsets, permissions as drf_permissions, filters
from .models import Product, Category
from .serializers import ProductSerializer, CategorySerializer
from accounts.permissions import IsAdminUser

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [drf_permissions.AllowAny]
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'category__name', 'description']

    def get_queryset(self):
        queryset = Product.objects.all().order_by('-id')
        if self.request.user.is_authenticated and self.request.user.role == 'admin':
            return queryset
        return queryset.filter(is_active=True)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [drf_permissions.AllowAny]
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]
