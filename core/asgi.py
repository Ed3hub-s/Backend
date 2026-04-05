import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from notifications.routing import websocket_urlpatterns as notification_patterns
from chat.routing import websocket_urlpatterns as chat_patterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(
            notification_patterns + chat_patterns
        )
    ),
})
