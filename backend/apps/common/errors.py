"""Error responses in the shape the frontend expects: { message, code }."""

import re

from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class ApiError(exceptions.APIException):
    """Raise anywhere in a view to return `{message, code}` with a chosen status."""

    def __init__(self, message, status_code=status.HTTP_400_BAD_REQUEST, code="error", details=None):
        super().__init__(message, code)
        self.status_code = status_code
        self.message = message
        self.code = code
        self.details = details


def _humanise(key):
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", str(key)).replace("_", " ").strip().lower()
    return words[:1].upper() + words[1:]


def first_message(detail, key=None):
    if isinstance(detail, dict):
        for k, v in detail.items():
            found = first_message(v, None if k == "non_field_errors" else k)
            if found:
                return found
        return None
    if isinstance(detail, (list, tuple)):
        for item in detail:
            found = first_message(item, key)
            if found:
                return found
        return None
    text = str(detail)
    return f"{_humanise(key)}: {text}" if key else text


def api_exception_handler(exc, context):
    if isinstance(exc, ApiError):
        body = {"message": exc.message, "code": exc.code}
        if exc.details is not None:
            body["details"] = exc.details
        return Response(body, status=exc.status_code)

    response = drf_exception_handler(exc, context)
    if response is None:
        return None  # unexpected error: Django answers 500 and logs it

    if isinstance(exc, exceptions.ValidationError):
        response.data = {
            "message": first_message(exc.detail) or "Please check the details and try again.",
            "code": "validation",
            "details": exc.detail,
        }
        response.status_code = 422
    elif isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)):
        response.status_code = status.HTTP_401_UNAUTHORIZED
        response.data = {"message": "Please sign in again.", "code": "unauthenticated"}
    elif isinstance(exc, exceptions.PermissionDenied):
        response.data = {"message": "You do not have permission to do that.", "code": "forbidden"}
    elif isinstance(exc, exceptions.NotFound):
        response.data = {"message": "Not found.", "code": "not_found"}
    elif isinstance(exc, exceptions.Throttled):
        response.data = {
            "message": "Too many attempts. Please wait a little and try again.",
            "code": "throttled",
        }
    elif isinstance(exc, exceptions.MethodNotAllowed):
        response.data = {"message": "Method not allowed.", "code": "method_not_allowed"}
    elif isinstance(exc, exceptions.ParseError):
        response.data = {"message": "The request body is not valid JSON.", "code": "bad_request"}
    elif isinstance(exc, exceptions.UnsupportedMediaType):
        response.data = {"message": "Send the request as JSON.", "code": "unsupported_media_type"}
    else:
        response.data = {"message": "Request failed.", "code": "http_error"}
    return response
