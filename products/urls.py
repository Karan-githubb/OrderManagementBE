from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, CategoryViewSet, PurchaseViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'purchases', PurchaseViewSet, basename='purchase')
router.register(r'', ProductViewSet, basename='product')


urlpatterns = [
    path('', include(router.urls)),
]
