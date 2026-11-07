"""Create demo data matching the frontend's built-in demo plant, so the real backend
can be tried straight away:

    python manage.py seed_demo
    python manage.py simulate_gateway --key <printed key>
"""

import secrets

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.alerts.models import Threshold
from apps.plants.models import ConnectionPeriod, Gateway, GatewayAssignment, Machine, Plant

MACHINES = [  # id, name, type, rated kW, meter id
    ("sheller-1", "Sheller", "sheller", 36, "1"),
    ("whitener-1", "Whitener 1", "whitener", 25, "2"),
    ("whitener-2", "Whitener 2", "whitener", 22, "3"),
    ("sortex-1", "Colour Sortex 1", "sortex", 22, "4"),
]


class Command(BaseCommand):
    help = "Create a demo admin, a demo user, one plant, one gateway and four machines."

    def add_arguments(self, parser):
        parser.add_argument("--admin-password", default=None, help="default: a random one is printed")
        parser.add_argument("--new-key", action="store_true", help="issue a new key for an existing demo gateway")

    def handle(self, *args, admin_password, new_key, **options):
        # admin_password = admin_password or secrets.token_urlsafe(9)
        admin_password = "realadmin@123"
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults=dict(
                email="admin@example.com", full_name="Administrator", role="admin",
                status="active", is_staff=True, is_superuser=True,
            ),  # fmt: skip
        )
        if created:
            admin.set_password("realadmin@123")
            admin.save()
            self.stdout.write(f"admin user created.  username: admin  password: {admin_password}")
        else:
            self.stdout.write("admin user already exists (password unchanged)")

        user_password = "sam@123"
        operator, created = User.objects.get_or_create(
            username="sam",
            defaults=dict(email="sam@example.com", full_name="sam K", role="user", status="active"),
        )
        if created:
            operator.set_password(user_password)
            operator.save()
            self.stdout.write(f"operator created.     username: sam   password: {user_password}")

        plant, _ = Plant.objects.get_or_create(name="Plant 1")
        gateway = Gateway.objects.filter(name="Plant 1 gateway").first()
        key = None
        if gateway is None:
            gateway = Gateway(name="Plant 1 gateway", plant=plant)
            gateway.save()
            key = gateway._first_key
        elif new_key:
            key = gateway.rotate_key()
            gateway.save(update_fields=["api_key_prefix", "api_key_hash"])

        for position, (machine_id, name, kind, rated, meter) in enumerate(MACHINES):
            Machine.objects.get_or_create(
                id=machine_id,
                defaults=dict(
                    name=name, type=kind, rated_kw=rated, gateway=gateway, meter_id=meter, position=position
                ),
            )
        Threshold.objects.get_or_create(
            owner=operator, param="powerFactor", machine=None, defaults={"warning": 0.9, "critical": 0.8}
        )
        if not GatewayAssignment.objects.filter(gateway=gateway, status__in=["assigned", "connected"]).exists():
            now = timezone.now()
            a = GatewayAssignment.objects.create(
                gateway=gateway, user=operator, status="connected", connected_at=now
            )
            ConnectionPeriod.objects.create(assignment=a, start=now)

        if key:
            self.stdout.write(f"gateway key (shown once): {key}")
        else:
            self.stdout.write("gateway already exists; use --new-key to issue a fresh key")
