from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.alerts.models import Alert
from apps.telemetry.models import DailyReport, HourlyReport, MachineState, Reading


class Command(BaseCommand):
    help = (
        "Delete all stored readings, hourly and daily reports, alerts and live machine state. "
        "Accounts, plants, gateways and machines are kept."
    )

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Really delete. Without it nothing is changed.")

    def handle(self, *args, **opts):
        models = [Reading, HourlyReport, DailyReport, Alert, MachineState]
        counts = {m.__name__: m.objects.count() for m in models}
        for name, n in counts.items():
            self.stdout.write(f"{name}: {n} rows")
        if not opts["yes"]:
            raise CommandError("Nothing deleted. Run again with --yes to delete the rows listed above.")
        with transaction.atomic():
            for m in models:
                m.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("History cleared. New readings start from zero."))
