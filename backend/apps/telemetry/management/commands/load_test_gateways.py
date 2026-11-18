"""Create (or delete) many fake gateways for load testing.

    python manage.py load_test_gateways --count 50 --out keys.json     # create
    python manage.py load_test_gateways --delete                       # remove them all

The fake gateways have serial numbers LOAD-0001, LOAD-0002 ... and are approved at once. The file
written by --out holds their keys (it is the only copy: keep it private and delete it afterwards).
Deleting also removes their machines and readings.
"""

import json
import os

from django.core.management.base import BaseCommand, CommandError

from apps.plants.models import Gateway, Machine, Plant

PREFIX = "LOAD"


class Command(BaseCommand):
    help = "Create or delete fake gateways (serial LOAD-0001...) for load testing."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=0, help="how many gateways to create")
        parser.add_argument("--out", default="", help="file to write the keys to (JSON)")
        parser.add_argument("--delete", action="store_true", help="delete every LOAD-* gateway")

    def handle(self, *args, count, out, delete, **options):
        if delete:
            qs = Gateway.objects.filter(serial_number__startswith=PREFIX + "-")
            n = qs.count()
            Machine.objects.filter(gateway__in=qs).delete()  # machines are protected; their readings go with them
            qs.delete()
            self.stdout.write(f"Deleted {n} load-test gateways.")
            return
        if count < 1:
            raise CommandError("Pass --count N to create, or --delete to remove.")
        if not out:
            raise CommandError("Pass --out FILE so the keys are saved for the load test.")
        from django.conf import settings

        plant, _ = Plant.objects.get_or_create(name=settings.DEFAULT_PLANT_NAME)
        keys = []
        for i in range(1, count + 1):
            serial = f"{PREFIX}-{i:04d}"
            gw = Gateway.objects.filter(serial_number=serial).first()
            if gw is None:
                gw = Gateway(name=serial, plant=plant, serial_number=serial, verified=True)
            raw = gw.rotate_key()  # existing ones get a fresh key, so the file is always valid
            gw.save()
            keys.append({"serial": serial, "key": raw})
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(keys, f)
        self.stdout.write(f"Created {count} gateways. Keys written to {out}.")
