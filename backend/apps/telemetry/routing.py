from django.urls import re_path

from .consumers import LiveConsumer

websocket_urlpatterns = [re_path(r"^api/live/?$", LiveConsumer.as_asgi())]
