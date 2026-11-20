from django.db import models

from apps.plants.models import Machine


class MachineState(models.Model):
    machine = models.OneToOneField(Machine, primary_key=True, on_delete=models.CASCADE, related_name="state")
    last_ts = models.DateTimeField(null=True, blank=True)
    last_raw_ts = models.DateTimeField(null=True, blank=True)
    # When the server last got NEW data for this machine. Liveness uses this, not the
    # gateway's clock, so a skewed gateway clock cannot make a live machine look dead.
    received_at = models.DateTimeField(null=True, blank=True)
    on = models.BooleanField(default=False)

    kw = models.FloatField(default=0)
    pf = models.FloatField(null=True, blank=True)
    kva = models.FloatField(default=0)
    kvar = models.FloatField(default=0)
    current = models.FloatField(default=0)
    voltage = models.FloatField(null=True, blank=True)
    frequency = models.FloatField(null=True, blank=True)

    total_kwh = models.FloatField(null=True, blank=True)
    total_kvarh = models.FloatField(null=True, blank=True)
    total_kvah = models.FloatField(null=True, blank=True)

    run_start = models.DateTimeField(null=True, blank=True)
    last_stop = models.DateTimeField(null=True, blank=True)
    run_sec = models.FloatField(default=0)
    run_kwh = models.FloatField(default=0)
    run_pf_sum = models.FloatField(default=0)
    run_pf_n = models.PositiveIntegerField(default=0)

    today_date = models.DateField(null=True, blank=True)
    today_sec = models.FloatField(default=0)
    total_runtime_sec = models.FloatField(default=0)


class Reading(models.Model):
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
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="hourly_reports")
    hour = models.DateTimeField()
    kwh = models.FloatField(default=0)
    run_kwh = models.FloatField(default=0)
    kvarh = models.FloatField(default=0)
    kvah = models.FloatField(default=0)
    run_seconds = models.FloatField(default=0)
    samples = models.PositiveIntegerField(default=0)
    sum_kw = models.FloatField(default=0)
    max_kw = models.FloatField(default=0)
    sum_current = models.FloatField(default=0)
    max_current = models.FloatField(default=0)
    pf_samples = models.PositiveIntegerField(default=0)
    sum_pf = models.FloatField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["machine", "hour"], name="unique_hourly_report")]
        indexes = [models.Index(fields=["hour"])]

    @property
    def avg_pf(self):
        return self.sum_pf / self.pf_samples if self.pf_samples else None


class DailyReport(models.Model):
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
