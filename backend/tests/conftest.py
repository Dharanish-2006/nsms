from datetime import timedelta

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import AuthToken, User
from apps.alerts.models import Threshold
from apps.common import sms
from apps.plants.models import ConnectionPeriod, Gateway, GatewayAssignment, Machine, Plant


@pytest.fixture(autouse=True)
def _clean():
    cache.clear()
    sms.outbox.clear()
    yield


def make_user(username, role="user", status="active", **extra):
    user = User.objects.create_user(
        username=username, email=f"{username}@example.com", password="S3cure-pass-42",
        role=role, status=status, full_name=username.title(), **extra,
    )  # fmt: skip
    return user


def token_for(user):
    raw, _ = AuthToken.issue(user)
    return raw


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_for(user)}")
    return client


@pytest.fixture
def admin(db):
    return make_user("boss", role="admin")


@pytest.fixture
def operator(db):
    return make_user("asha")


@pytest.fixture
def other_user(db):
    return make_user("ravi")


@pytest.fixture
def anon():
    return APIClient()


@pytest.fixture
def admin_client(admin):
    return client_for(admin)


@pytest.fixture
def owner_client(operator, gateway):
    """The plant owner, connected to the gateway: sees its machines, alerts and reports."""
    connect(operator, gateway)
    return client_for(operator)


@pytest.fixture
def user_client(operator):
    return client_for(operator)


@pytest.fixture
def plant(db):
    return Plant.objects.create(name="Plant 1")


@pytest.fixture
def gateway(plant):
    gw = Gateway(name="Gateway A", plant=plant)
    gw.save()
    gw.raw_key = gw._first_key
    return gw


@pytest.fixture
def second_gateway(plant):
    gw = Gateway(name="Gateway B", plant=plant)
    gw.save()
    gw.raw_key = gw._first_key
    return gw


@pytest.fixture
def machines(gateway):
    rows = [
        ("sheller-1", "Sheller", "sheller", 36, "1"),
        ("whitener-2", "Whitener 2", "whitener", 22, "3"),
        ("sortex-1", "Colour Sortex 1", "sortex", 22, "4"),
    ]
    return {
        mid: Machine.objects.create(
            id=mid, name=name, type=kind, rated_kw=rated, gateway=gateway, meter_id=meter
        )
        for mid, name, kind, rated, meter in rows
    }


def connect(user, gateway):
    """Give `user` a connected assignment to `gateway`, as the admin portal would."""
    from django.utils import timezone

    now = timezone.now()
    a = GatewayAssignment.objects.create(gateway=gateway, user=user, status="connected", connected_at=now)
    ConnectionPeriod.objects.create(assignment=a, start=now - timedelta(days=30))
    return a


@pytest.fixture
def pf_threshold(db, operator):
    return Threshold.objects.create(owner=operator, param="powerFactor", machine=None, warning=0.9, critical=0.8)


def push(client, gateway, readings, key=None):
    """POST readings to /api/ingest the way a gateway would."""
    return client.post(
        "/api/ingest",
        {"readings": readings},
        format="json",
        HTTP_X_GATEWAY_KEY=key or gateway.raw_key,
    )
