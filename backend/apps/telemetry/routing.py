from django.urls import re_path

from .consumers import LiveConsumer

# Under /api so a single reverse-proxy rule (location /api/) carries REST and WebSocket.
websocket_urlpatterns = [re_path(r"^api/live/?$", LiveConsumer.as_asgi())]
