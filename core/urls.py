from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(title='Ed3Hub API', default_version='v1', description='Authentication API for Ed3Hub'),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

def api_landing(request):
    return render(request, 'api_landing.html')

urlpatterns = [
    path('', api_landing, name='api-landing'),
    path('admin/', admin.site.urls),
    path('api/auth/', include('authentication.urls')),
    path('api/courses/', include('courses.urls')),
    path('api/chat/', include('chat.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='redoc'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Always serve media files regardless of DEBUG
if not settings.DEBUG:
    from django.views.static import serve
    from django.urls import re_path
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]
