from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView, LoginView, LogoutView, MeView, GoogleAuthView,
    VerifyOTPView, ResendOTPView, UpdateProfileView,
    ForgotPasswordView, VerifyResetOTPView, ResetPasswordView,
    EducatorsListView, MarketerDashboardView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', MeView.as_view(), name='me'),
    path('profile/update/', UpdateProfileView.as_view(), name='update-profile'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('google/', GoogleAuthView.as_view(), name='google-auth'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('verify-reset-otp/', VerifyResetOTPView.as_view(), name='verify-reset-otp'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('educators/', EducatorsListView.as_view(), name='educators'),
    path('marketer/dashboard/', MarketerDashboardView.as_view(), name='marketer-dashboard'),
]
