"""Send the automatic report emails that are due.  python manage.py send_auto_reports
(`run_maintenance` does this too.)  --now ignores the time-of-day rule; --user limits it to one username."""

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.alerts.autoreport import send_due_reports


class Command(BaseCommand):
    help = "Email the automatic reports that are due."

    def add_arguments(self, parser):
        parser.add_argument("--now", action="store_true", help="ignore AUTO_REPORT_HOUR")
        parser.add_argument("--user", default="", help="only this username")

    def handle(self, *args, now, user, **options):
        only = User.objects.get(username=user) if user else None
        self.stdout.write(f"reports sent: {send_due_reports(ignore_hour=now, only_user=only)}")
