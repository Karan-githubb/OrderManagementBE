from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DraftViewSet, DraftOrderItemViewSet

router = DefaultRouter()
router.register(r'', DraftViewSet, basename='draft')
router.register(r'items', DraftOrderItemViewSet, basename='draftitem')

urlpatterns = [
    path('', include(router.urls)),
]
