import secrets

import requests
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import models
from rest_framework import status, parsers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import OTPCode, UserProfile
from .serializers import RegisterSerializer, UserSerializer, EducatorSerializer, GoogleAuthSerializer, ForgotPasswordSerializer, VerifyResetOTPSerializer, ResetPasswordSerializer
from .utils import create_and_send_otp, create_and_send_reset_otp, send_welcome_email


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class EducatorsListView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request):
        search = request.query_params.get('search', '').strip()
        qs = User.objects.filter(
            is_active=True,
            profile__role='educator',
        ).select_related('profile')
        if search:
            qs = qs.filter(
                models.Q(first_name__icontains=search) |
                models.Q(last_name__icontains=search) |
                models.Q(username__icontains=search) |
                models.Q(profile__bio__icontains=search)
            )
        serializer = EducatorSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)


class RegisterView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        role = serializer.validated_data.get('role', 'learner')

        if User.objects.filter(username=username).exists():
            return Response({'username': ['A user with that username already exists.']}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(email=email).exists():
            return Response({'email': ['A user with that email already exists.']}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(username=username, email=email, password=password, is_active=False)
        UserProfile.objects.create(user=user, role=role)
        try:
            create_and_send_otp(email)
        except Exception:
            user.delete()
            return Response({'detail': 'Failed to send verification email. Please try again.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'detail': 'OTP sent to your email.', 'email': email}, status=status.HTTP_201_CREATED)


class VerifyOTPView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('code')

        if not email or not code:
            return Response({'detail': 'Email and code are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            otp = OTPCode.objects.filter(email=email, code=code).latest('created_at')
        except OTPCode.DoesNotExist:
            return Response({'detail': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        if not otp.is_valid():
            otp.delete()
            return Response({'detail': 'OTP has expired.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email, is_active=False)
        except User.DoesNotExist:
            return Response({'detail': 'No pending registration found for this email.'}, status=status.HTTP_400_BAD_REQUEST)

        user.is_active = True
        user.save()
        otp.delete()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        send_welcome_email(user, profile.role)

        return Response({'detail': 'Email verified successfully. Please sign in.'}, status=status.HTTP_200_OK)


class ResendOTPView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'detail': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not User.objects.filter(email=email, is_active=False).exists():
            return Response({'detail': 'No pending registration found for this email.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            create_and_send_otp(email)
        except Exception:
            return Response({'detail': 'Failed to send OTP email. Please try again.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'detail': 'OTP resent to your email.'}, status=status.HTTP_200_OK)


class LoginView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({'detail': 'Username and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)

        if not user:
            try:
                u = User.objects.get(username=username)
                if not u.is_active:
                    return Response(
                        {'detail': 'Please verify your email before signing in.', 'unverified': True, 'email': u.email},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            except User.DoesNotExist:
                pass
            return Response({'detail': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

        return Response(
            {'user': UserSerializer(user, context={'request': request}).data, 'tokens': get_tokens_for_user(user)},
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        try:
            token = RefreshToken(request.data.get('refresh'))
            token.blacklist()
            return Response({'detail': 'Logged out successfully.'}, status=status.HTTP_200_OK)
        except TokenError:
            return Response({'detail': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)


class MeView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(UserSerializer(request.user, context={'request': request}).data)


class UpdateProfileView(APIView):
    permission_classes = (IsAuthenticated,)

    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def patch(self, request):
        user = request.user
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        bio = request.data.get('bio')
        avatar = request.FILES.get('avatar')

        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        if bio is not None:
            profile.bio = bio
        if avatar:
            profile.avatar = avatar
        for field in ('city_country', 'specialization', 'experience',
                      'whatsapp', 'facebook', 'twitter_x', 'linkedin', 'instagram'):
            val = request.data.get(field)
            if val is not None:
                setattr(profile, field, val.strip() if isinstance(val, str) else val)
        profile.save()

        return Response(UserSerializer(user, context={'request': request}).data)


class GoogleAuthView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        access_token = serializer.validated_data['access_token']
        google_response = requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
        )

        if google_response.status_code != 200:
            return Response({'detail': 'Invalid Google token.'}, status=status.HTTP_400_BAD_REQUEST)

        google_data = google_response.json()
        email = google_data.get('email')
        name = google_data.get('name', '')

        if not email:
            return Response({'detail': 'Could not retrieve email from Google.'}, status=status.HTTP_400_BAD_REQUEST)

        role = request.data.get('role', 'learner')
        if role not in ('learner', 'educator'):
            role = 'learner'

        is_new_user = False
        try:
            user = User.objects.get(email=email)
            if not user.is_active:
                return Response({'detail': 'This account is not yet verified. Please verify your email first.'}, status=status.HTTP_403_FORBIDDEN)
            # Never change role for existing users
            UserProfile.objects.get_or_create(user=user, defaults={'role': role})
        except User.DoesNotExist:
            base_username = email.split('@')[0]
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f'{base_username}{counter}'
                counter += 1
            user = User.objects.create_user(username=username, email=email, first_name=name, is_active=True)
            UserProfile.objects.create(user=user, role=role)
            send_welcome_email(user, role)
            is_new_user = True

        return Response(
            {
                'user': UserSerializer(user, context={'request': request}).data,
                'tokens': get_tokens_for_user(user),
                'is_new_user': is_new_user,
            },
            status=status.HTTP_200_OK,
        )

# In-memory store for reset tokens: { token: email }
# For production, use cache (Redis) or a DB model instead
_reset_tokens: dict = {}


class ForgotPasswordView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        if not User.objects.filter(email=email, is_active=True).exists():
            # Return success anyway to avoid email enumeration
            return Response({'detail': 'If that email exists, an OTP has been sent.'}, status=status.HTTP_200_OK)

        try:
            create_and_send_reset_otp(email)
        except Exception:
            return Response({'detail': 'Failed to send OTP email. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'detail': 'If that email exists, an OTP has been sent.'}, status=status.HTTP_200_OK)


class VerifyResetOTPView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = VerifyResetOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        code = serializer.validated_data['code']

        try:
            otp = OTPCode.objects.filter(email=email, code=code).latest('created_at')
        except OTPCode.DoesNotExist:
            return Response({'detail': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        if not otp.is_valid():
            otp.delete()
            return Response({'detail': 'OTP has expired.'}, status=status.HTTP_400_BAD_REQUEST)

        otp.delete()
        reset_token = secrets.token_urlsafe(32)
        _reset_tokens[reset_token] = email

        return Response({'reset_token': reset_token}, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        reset_token = serializer.validated_data['reset_token']
        new_password = serializer.validated_data['new_password']

        email = _reset_tokens.pop(reset_token, None)
        if not email:
            return Response({'detail': 'Invalid or expired reset token.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({'detail': 'Password reset successfully.'}, status=status.HTTP_200_OK)
