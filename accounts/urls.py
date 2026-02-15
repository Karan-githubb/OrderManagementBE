from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import RegisterPharmacyView, UserDetailView, UserViewSet, EmailTokenObtainPairView

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    path('login/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', RegisterPharmacyView.as_view(), name='register_pharmacy'),
    path('me/', UserDetailView.as_view(), name='user_detail'),
    path('', include(router.urls)),
]
