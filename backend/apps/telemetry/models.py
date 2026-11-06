from django.db import models

from apps.plants.models import Machine


class MachineState(models.Model):
    """The latest known state of a machine, updated on every ingest.

    This is what the live dashboard reads, so `GET /machines` never has to scan readings.
    """

    machine = models.OneToOneField(Machine, primary_key=True, on_delete=models.CASCADE, related_name="state")
    last_ts = models.DateTimeField(null=True, blank=True)  # timestamp of the newest sample applied
    last_raw_ts = models.DateTimeField(null=True, blank=True)  # newest sample kept in Reading
    # When the server last got NEW data for this machine. Liveness uses this, not the
    # gateway's clock, so a skewed gateway clock cannot make a live machine look dead.
    received_at = models.DateTimeField(null=True, blank=True)
    on = models.BooleanField(default=False)

    # Instantaneous values from the newest sample
    kw = models.FloatField(default=0)
    pf = models.FloatField(null=True, blank=True)
    kva = models.FloatField(default=0)
    kvar = models.FloatField(default=0)
    current = models.FloatField(default=0)
    voltage = models.FloatField(null=True, blank=True)
    frequency = models.FloatField(null=True, blank=True)

    # Lifetime meter counters (the meter's own totals when the gateway sends them)
    total_kwh = models.FloatField(null=True, blank=True)
    total_kvarh = models.FloatField(null=True, blank=True)
    total_kvah = models.FloatField(null=True, blank=True)

    # Current run
    run_start = models.DateTimeField(null=True, blank=True)
    last_stop = models.DateTimeField(null=True, blank=True)
    run_sec = models.FloatField(default=0)
    run_kwh = models.FloatField(default=0)
    run_pf_sum = models.FloatField(default=0)
    run_pf_n = models.PositiveIntegerField(default=0)

    # Runtime counters
    today_date = models.DateField(null=True, blank=True)  # IST day `today_sec` belongs to
    today_sec = models.FloatField(default=0)
    total_runtime_sec = models.FloatField(default=0)


class Reading(models.Model):
    """Raw samples, kept for RAW_RETENTION_DAYS to draw trend charts. Pruned by
    `manage.py run_maintenance`; the hourly and daily reports are the permanent record."""

    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="readings")
    ts = models.DateTimeField()
    on = models.BooleanField(default=False)
    kw = models.FloatField()
    pf = models.FloatField(null=True, blank=True)
    kva = models.FloatField(default=0)
    kvar = models.FloatField(default=0)
    current = models.FloatField(default=0)
    voltage = models.FloatField(null=True, blank=True)
    frequency = models.FloatField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["machine", "ts"], name="unique_reading_per_machine_ts")]
        indexes = [models.Index(fields=["ts"])]


class HourlyReport(models.Model):
    """Consolidated per-machine, per-IST-hour totals. Updated incrementally on ingest."""

    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="hourly_reports")
    hour = models.DateTimeField()  # start of the IST hour
    kwh = models.FloatField(default=0)  # all energy metered in the hour
    run_kwh = models.FloatField(default=0)  # the part used while the machine was running
    kvarh = models.FloatField(default=0)
    kvah = models.FloatField(default=0)
    run_seconds = models.FloatField(default=0)
    samples = models.PositiveIntegerField(default=0)
    sum_kw = models.FloatField(default=0)
    max_kw = models.FloatField(default=0)
    sum_current = models.FloatField(default=0)
    max_current = models.FloatField(default=0)
    pf_samples = models.PositiveIntegerField(default=0)  # samples taken while running
    sum_pf = models.FloatField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["machine", "hour"], name="unique_hourly_report")]
        indexes = [models.Index(fields=["hour"])]

    @property
    def avg_pf(self):
        return self.sum_pf / self.pf_samples if self.pf_samples else None


class DailyReport(models.Model):
    """Consolidated per-machine, per-IST-day report, rolled up from the hourly rows."""

    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="daily_reports")
    date = models.DateField()
    kwh = models.FloatField(default=0)
    run_kwh = models.FloatField(default=0)
    kvarh = models.FloatField(default=0)
    kvah = models.FloatField(default=0)
    run_seconds = models.FloatField(default=0)
    avg_kw = models.FloatField(default=0)
    max_kw = models.FloatField(default=0)
    avg_pf = models.FloatField(null=True, blank=True)
    max_current = models.FloatField(default=0)
    samples = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["machine", "date"], name="unique_daily_report")]
        indexes = [models.Index(fields=["date"])]
