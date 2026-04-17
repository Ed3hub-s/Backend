from pathlib import Path
from datetime import timedelta
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('SECRET_KEY')

DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')]


INSTALLED_APPS = [
    'daphne',
    'unfold',
    'unfold.contrib.filters',
    'unfold.contrib.forms',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_yasg',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'channels',
    'storages',
    # Local
    'authentication',
    'courses',
    'chat',
    'notifications',
]

SITE_ID = 1

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = 'core.asgi.application'

# Channels
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [os.getenv('REDIS_URL', 'redis://127.0.0.1:6379')],
        },
    },
}

# Celery
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'


# Database
if os.getenv('DB_NAME'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME'),
            'USER': os.getenv('DB_USER'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files — served by WhiteNoise
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# Media / File Storage — Cloudflare R2 in production, local in development
USE_R2 = os.getenv('USE_R2', 'False') == 'True'

if USE_R2:
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    AWS_ACCESS_KEY_ID = os.getenv('R2_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('R2_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('R2_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = os.getenv('R2_ENDPOINT_URL')
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None          # R2 does not support S3 ACLs
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',
    }
    AWS_QUERYSTRING_AUTH = False    # Use public URLs, not signed URLs
    # R2_MEDIA_URL is the public base URL for the bucket (custom domain or r2.dev URL)
    _r2_media_url = os.getenv('R2_MEDIA_URL', '').rstrip('/')
    MEDIA_URL = f'{_r2_media_url}/'
    MEDIA_ROOT = ''
else:
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'

UNFOLD = {
    'SITE_TITLE': 'Ed3Hub Admin',
    'SITE_HEADER': 'Ed3Hub',
    'SITE_SUBHEADER': 'Platform Management',
    'SITE_URL': '/',
    'SITE_LOGO': lambda request: '/static/img/ed3hub_logo.png',
    'SITE_FAVICON': lambda request: '/static/img/ed3hub_logo.png',
    'SITE_SYMBOL': 'school',
    'SHOW_HISTORY': True,
    'SHOW_VIEW_ON_SITE': True,
    'COLORS': {
        'font': {
            'subtle-light': '107 114 128',
            'subtle-dark': '156 163 175',
            'default-light': '17 24 39',
            'default-dark': '243 244 246',
            'important-light': '0 0 0',
            'important-dark': '255 255 255',
        },
        'primary': {
            '50': '245 243 255',
            '100': '237 233 254',
            '200': '221 214 254',
            '300': '196 181 253',
            '400': '167 139 250',
            '500': '139 92 246',
            '600': '124 58 237',
            '700': '109 40 217',
            '800': '91 33 182',
            '900': '76 29 149',
            '950': '46 16 101',
        },
    },
    'SIDEBAR': {
        'show_search': True,
        'show_all_applications': True,
        'navigation': [
            {
                'title': 'Users & Auth',
                'separator': True,
                'items': [
                    {'title': 'Users', 'icon': 'person', 'link': '/admin/auth/user/'},
                    {'title': 'Profiles', 'icon': 'badge', 'link': '/admin/authentication/userprofile/'},
                    {'title': 'OTP Codes', 'icon': 'lock', 'link': '/admin/authentication/otpcode/'},
                ],
            },
            {
                'title': 'Courses',
                'separator': True,
                'items': [
                    {'title': 'Courses', 'icon': 'menu_book', 'link': '/admin/courses/course/'},
                    {'title': 'Categories', 'icon': 'category', 'link': '/admin/courses/category/'},
                    {'title': 'Modules', 'icon': 'view_module', 'link': '/admin/courses/module/'},
                    {'title': 'Lessons', 'icon': 'play_lesson', 'link': '/admin/courses/lesson/'},
                    {'title': 'Enrollments', 'icon': 'how_to_reg', 'link': '/admin/courses/enrollment/'},
                    {'title': 'Certificates', 'icon': 'workspace_premium', 'link': '/admin/courses/certificate/'},
                    {'title': 'Reviews', 'icon': 'star', 'link': '/admin/courses/review/'},
                ],
            },
            {
                'title': 'Tokens',
                'separator': True,
                'items': [
                    {'title': 'Wallets', 'icon': 'account_balance_wallet', 'link': '/admin/courses/tokenwallet/'},
                    {'title': 'Transactions', 'icon': 'receipt_long', 'link': '/admin/courses/tokentransaction/'},
                ],
            },
            {
                'title': 'Chat',
                'separator': True,
                'items': [
                    {'title': 'Conversations', 'icon': 'forum', 'link': '/admin/chat/conversation/'},
                    {'title': 'Messages', 'icon': 'chat', 'link': '/admin/chat/message/'},
                ],
            },
        ],
    },
}

# CORS
CORS_ALLOWED_ORIGINS = [o.strip() for o in os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000').split(',')]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_HEADERS = [
    'accept',
    'authorization',
    'content-type',
    'origin',
    'x-requested-with',
    'x-csrftoken',
]
CORS_EXPOSE_HEADERS = ['content-disposition']

# CSRF
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv('CSRF_TRUSTED_ORIGINS', 'http://localhost:3000').split(',')]

# Frontend URL for certificate verification
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

# JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# Allauth
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'OAUTH_PKCE_ENABLED': True,
        'APP': {
            'client_id': os.getenv('GOOGLE_CLIENT_ID'),
            'secret': os.getenv('GOOGLE_CLIENT_SECRET'),
        },
    }
}

ACCOUNT_EMAIL_VERIFICATION = 'none'

# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'das121.truehost.cloud')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', 'ed3hub@ed3hub.name.ng')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD','EIFousk4J0jqN9R4')
DEFAULT_FROM_EMAIL = os.getenv('EMAIL_HOST_USER', 'ed3hub@ed3hub.name.ng')
SERVER_EMAIL = os.getenv('EMAIL_HOST_USER', 'ed3hub@ed3hub.name.ng')
EMAIL_TIMEOUT = 30
EMAIL_SSL_CERTFILE = None
EMAIL_SSL_KEYFILE = None

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Allow large file uploads (videos, thumbnails) — 100 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 104857600
FILE_UPLOAD_MAX_MEMORY_SIZE = 104857600
