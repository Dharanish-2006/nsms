from datetime import timedelta

from django.utils import timezone
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header

from .models import AuthToken, User, hash_secret


class InvalidToken(Exception):
    pass


def authenticate_token(raw):
    """Look up a bearer token. Returns (user, token) or raises InvalidToken.

    Shared by the REST authenticator and the WebSocket consumer.
    """
    if not raw:
        raise InvalidToken
    try:
        token = AuthToken.objects.select_related("user").get(key_hash=hash_secret(raw))
    except AuthToken.DoesNotExist:
        raise InvalidToken from None
    now = timezone.now()
    if token.expires_at <= now:
        token.delete()
        raise InvalidToken
    user = token.user
    if not user.is_active or user.status != User.Status.ACTIVE:
        raise InvalidToken
    if now - token.last_used_at > timedelta(seconds=60):  # avoid a write on every poll
        AuthToken.objects.filter(pk=token.pk).update(last_used_at=now)
    return user, token


class BearerTokenAuthentication(BaseAuthentication):
    """`Authorization: Bearer <token>`."""

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != b"bearer":
            return None
        if len(parts) != 2:
            raise exceptions.AuthenticationFailed("Invalid token header.")
        try:
            return authenticate_token(parts[1].decode())
        except (InvalidToken, UnicodeDecodeError):
            raise exceptions.AuthenticationFailed("Invalid or expired token.") from None

    def authenticate_header(self, request):
        return "Bearer"
