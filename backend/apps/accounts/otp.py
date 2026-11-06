"""One-time codes used to prove ownership of an email address or phone number."""

import logging
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from apps.common.errors import ApiError
from apps.common.sms import send_sms

from .models import OtpChallenge, OtpProof, hash_secret

logger = logging.getLogger(__name__)

CODE_TTL = timedelta(minutes=5)
PROOF_TTL = timedelta(minutes=15)
MAX_WRONG_TRIES = 5
SENDS_PER_WINDOW = 3
SEND_WINDOW = timedelta(minutes=10)


def normalise_target(channel, target):
    target = str(target or "").strip()
    if channel == "email":
        target = target.lower()
        try:
            validate_email(target)
        except DjangoValidationError:
            raise ApiError("Enter a valid email address.", 422, "validation") from None
        return target
    if channel == "phone":
        digits = re.sub(r"\D", "", target)
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]
        if not re.fullmatch(r"[6-9]\d{9}", digits):
            raise ApiError("Enter a valid 10-digit mobile number.", 422, "validation")
        return digits
    raise ApiError("Channel must be email or phone.", 422, "validation")


def _code_hash(channel, target, code):
    return salted_hmac("nsms.otp", f"{channel}:{target}:{code}").hexdigest()


def send_code(channel, target):
    """Create and deliver a code. The caller always answers 204, so the response
    never reveals whether an address is already registered."""
    target = normalise_target(channel, target)
    now = timezone.now()
    recent = OtpChallenge.objects.filter(
        channel=channel, target=target, created_at__gte=now - SEND_WINDOW
    ).count()
    if recent >= SENDS_PER_WINDOW:
        raise ApiError(
            "Too many codes requested. Please wait a few minutes.", 429, "otp_rate_limited"
        )

    code = f"{secrets.randbelow(10**6):06d}"
    OtpChallenge.objects.filter(channel=channel, target=target, expires_at__lte=now).delete()
    OtpChallenge.objects.create(
        channel=channel,
        target=target,
        code_hash=_code_hash(channel, target, code),
        expires_at=now + CODE_TTL,
    )
    message = f"Your Rice Mill Monitor verification code is {code}. It expires in 5 minutes."
    try:
        if channel == "email":
            send_mail("Your verification code", message, None, [target])
        else:
            send_sms(target, message)
    except Exception:  # noqa: BLE001
        logger.exception("Could not deliver verification code")
        raise ApiError(
            "We could not send the code right now. Please try again.", 503, "delivery_failed"
        ) from None


def verify_code(channel, target, code):
    """Check a code and return a single-use proof token."""
    target = normalise_target(channel, target)
    now = timezone.now()
    challenge = (
        OtpChallenge.objects.filter(channel=channel, target=target, expires_at__gt=now)
        .order_by("-created_at")
        .first()
    )
    wrong = ApiError("That code is incorrect or has expired.", 400, "otp_invalid")
    if challenge is None:
        raise wrong
    if challenge.attempts >= MAX_WRONG_TRIES:
        raise ApiError("Too many wrong codes. Request a new code.", 429, "otp_locked")

    if not constant_time_compare(challenge.code_hash, _code_hash(channel, target, str(code or "").strip())):
        OtpChallenge.objects.filter(pk=challenge.pk).update(attempts=challenge.attempts + 1)
        if challenge.attempts + 1 >= MAX_WRONG_TRIES:
            raise ApiError("Too many wrong codes. Request a new code.", 429, "otp_locked")
        raise wrong

    OtpChallenge.objects.filter(channel=channel, target=target).delete()
    raw = secrets.token_urlsafe(24)
    OtpProof.objects.filter(expires_at__lte=now).delete()
    OtpProof.objects.create(
        channel=channel, target=target, token_hash=hash_secret(raw), expires_at=now + PROOF_TTL
    )
    return raw


def proof_for(channel, target, token):
    """The unexpired proof matching these values, or None. Does not consume it."""
    if not token:
        return None
    return OtpProof.objects.filter(
        channel=channel,
        target=target,
        token_hash=hash_secret(str(token)),
        expires_at__gt=timezone.now(),
    ).first()
