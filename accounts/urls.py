from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView
from .views import RegisterPharmacyView, UserDetailView, UserProfileUpdateView, ChangePasswordView, UserViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', RegisterPharmacyView.as_view(), name='register_pharmacy'),
    path('me/', UserDetailView.as_view(), name='user_detail'),
    path('me/update/', UserProfileUpdateView.as_view(), name='user_profile_update'),
    path('me/change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('', include(router.urls)),
]
