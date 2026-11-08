"""Housekeeping. Run it every few minutes (cron / ECS scheduled task / EventBridge), or
keep one process looping:  python manage.py run_maintenance --loop 300

  * rebuilds the DailyReport rows for today and the previous days
  * deletes raw readings older than RAW_RETENTION_DAYS
  * deletes expired auth tokens and one-time codes
  * emails the automatic reports that are due (see apps/alerts/autoreport.py)
"""

import logging
import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.alerts.autoreport import send_due_reports
from apps.accounts.models import AuthToken, OtpChallenge, OtpProof
from apps.telemetry.consolidate import consolidate_day
from apps.telemetry.models import Reading

logger = logging.getLogger(__name__)
PRUNE_BATCH = 10_000


def run_once(days=2):
    today = timezone.localdate()
    rows = sum(consolidate_day(today - timedelta(days=i)) for i in range(days))

    cutoff = timezone.now() - timedelta(days=settings.RAW_RETENTION_DAYS)
    pruned = 0
    while True:  # in batches so a big backlog never holds one huge lock
        ids = list(Reading.objects.filter(ts__lt=cutoff).values_list("pk", flat=True)[:PRUNE_BATCH])
        if not ids:
            break
        pruned += Reading.objects.filter(pk__in=ids).delete()[0]

    now = timezone.now()
    AuthToken.objects.filter(expires_at__lte=now).delete()
    OtpChallenge.objects.filter(expires_at__lte=now).delete()
    OtpProof.objects.filter(expires_at__lte=now).delete()
    reports = send_due_reports()
    return rows, pruned, reports


class Command(BaseCommand):
    help = "Consolidate daily reports and prune old raw readings / expired tokens."

    def add_arguments(self, parser):
        parser.add_argument("--loop", type=int, default=0, metavar="SECONDS", help="repeat forever")
        parser.add_argument("--days", type=int, default=2, help="how many recent days to rebuild")

    def handle(self, *args, loop, days, **options):
        while True:
            try:
                rows, pruned, reports = run_once(days)
                self.stdout.write(f"daily rows written: {rows}, raw readings pruned: {pruned}, reports sent: {reports}")
            except Exception:  # noqa: BLE001 - keep a looping worker alive
                logger.exception("Maintenance run failed")
                if not loop:
                    raise
            if not loop:
                return
            time.sleep(loop)
