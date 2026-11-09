"""Receiving gateway data.

One call to `ingest()` handles one HTTP request from a gateway:

  1. validate each reading (bad ones are rejected individually, the rest are kept)
  2. per machine, in time order and under a row lock:
       - keep a thinned raw sample (for trend charts)
       - update the live MachineState (power, run/stop, runtime, energy...)
       - fold the sample into the consolidated HourlyReport
       - re-evaluate alerts
  3. return what changed so the caller can push it to dashboards AFTER the commit

Samples older than a machine's newest applied sample (late or duplicate deliveries)
never change live state or reports, which makes retries by the gateway safe.
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers

from apps.alerts.engine import evaluate_machine
from apps.common.errors import ApiError, first_message
from apps.common.timeutil import local_hour_start, parse_timestamp
from apps.plants.models import Gateway, Machine

from .models import HourlyReport, MachineState, Reading



# --- Validation -------------------------------------------------------------
class FiniteFloat(serializers.FloatField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not math.isfinite(value):
            self.fail("invalid")
        return value


class TimestampField(serializers.Field):
    def to_internal_value(self, data):
        try:
            return parse_timestamp(data)
        except (ValueError, OverflowError, OSError) as exc:
            raise serializers.ValidationError(str(exc)) from None


class ReadingSerializer(serializers.Serializer):
    """One meter reading. Only `meterId` and `kw` are required."""

    meterId = serializers.CharField(max_length=32)
    ts = TimestampField(required=False)
    kw = FiniteFloat()
    pf = FiniteFloat(required=False, allow_null=True)
    kva = FiniteFloat(required=False, allow_null=True, min_value=0)
    kvar = FiniteFloat(required=False, allow_null=True, min_value=0)
    current = FiniteFloat(required=False, allow_null=True, min_value=0)
    voltage = FiniteFloat(required=False, allow_null=True, min_value=0)
    frequency = FiniteFloat(required=False, allow_null=True, min_value=0)
    kwh = FiniteFloat(required=False, allow_null=True, min_value=0)
    kvarh = FiniteFloat(required=False, allow_null=True, min_value=0)
    kvah = FiniteFloat(required=False, allow_null=True, min_value=0)
    on = serializers.BooleanField(required=False, allow_null=True)

    def validate_pf(self, value):
        if value is None:
            return None
        value = abs(value)  # some meters report a signed power factor
        if value > 1.0001:
            raise serializers.ValidationError("Power factor must be between 0 and 1.")
        return min(value, 1.0)


@dataclass
class Sample:
    meter_id: str
    ts: object
    kw: float
    pf: float | None
    kva: float
    kvar: float
    current: float
    voltage: float | None
    frequency: float | None
    kwh: float | None
    kvarh: float | None
    kvah: float | None
    on: bool


def _complete(d, machine, ts):
    """Fill in what the meter did not send, from what it did."""
    kw = max(d["kw"], 0.0)  # tiny negatives at idle are meter noise
    pf = d.get("pf")
    kva = d.get("kva")
    if pf is None and kva:
        pf = min(kw / kva, 1.0)
    if kva is None:
        kva = kw / pf if pf else 0.0
    kvar = d.get("kvar")
    if kvar is None:
        kvar = math.sqrt(max(kva * kva - kw * kw, 0.0))
    current = d.get("current")
    if current is None:
        current = kva * 1000 / (math.sqrt(3) * (d.get("voltage") or settings.NOMINAL_VOLTAGE)) if kva else 0.0
    on = d.get("on")
    if on is None:
        on = kw >= machine.on_threshold_kw
    return Sample(
        meter_id=d["meterId"], ts=ts, kw=kw, pf=pf, kva=kva, kvar=kvar, current=current,
        voltage=d.get("voltage"), frequency=d.get("frequency"),
        kwh=d.get("kwh"), kvarh=d.get("kvarh"), kvah=d.get("kvah"), on=bool(on),
    )  # fmt: skip


def parse_payload(data, now):
    """-> (list of (validated dict, ts), rejected). Accepts {"readings": [...]} or one reading."""
    if not isinstance(data, dict):
        raise ApiError("Send a JSON object with a readings list.", 422, "validation")
    items = data.get("readings")
    if items is None:
        items = [data]
    if not isinstance(items, list) or not items:
        raise ApiError("readings must be a non-empty list.", 422, "validation")
    if len(items) > settings.INGEST_MAX_READINGS:
        raise ApiError(
            f"Send at most {settings.INGEST_MAX_READINGS} readings per request.", 413, "too_many_readings"
        )

    oldest = now - timedelta(days=settings.RAW_RETENTION_DAYS)
    newest = now + timedelta(seconds=settings.MAX_CLOCK_SKEW_SEC)
    good, rejected = [], []
    for index, item in enumerate(items):
        s = ReadingSerializer(data=item)
        if not s.is_valid():
            rejected.append({"index": index, "error": first_message(s.errors)})
            continue
        ts = s.validated_data.get("ts") or now
        if ts > newest:
            rejected.append({"index": index, "error": "Timestamp is in the future. Check the gateway clock."})
        elif ts < oldest:
            rejected.append({"index": index, "error": "Timestamp is too old."})
        else:
            good.append((s.validated_data, ts))
    return good, rejected


# --- Applying a sample ------------------------------------------------------
def _delta(new, old):
    """Increase of a lifetime counter, or None if unusable (missing or reset)."""
    if new is None or old is None or new < old:
        return None
    return new - old


def apply_sample(machine, state, s, hourly):
    """Fold one sample (newer than state.last_ts) into live state and the hourly report."""
    prev_ts, prev_on = state.last_ts, state.on
    dt = (s.ts - prev_ts).total_seconds() if prev_ts else None
    contiguous = dt is not None and dt <= settings.MAX_SAMPLE_GAP_SEC

    local = timezone.localtime(s.ts)
    if state.today_date != local.date():
        state.today_date, state.today_sec = local.date(), 0

    hour = local_hour_start(s.ts)
    hr = hourly.get(hour)
    if hr is None:
        hr, _ = HourlyReport.objects.get_or_create(machine=machine, hour=hour)
        hourly[hour] = hr

    # Energy since the previous sample: prefer the meter's own counter, fall back to
    # integrating power when it is missing, was reset, or jumped implausibly.
    d_kwh = d_kvarh = d_kvah = 0.0
    if prev_ts is not None:
        integrated = (state.kw + s.kw) / 2 * dt / 3600 if contiguous else 0.0
        d_kwh = _delta(s.kwh, state.total_kwh)
        if d_kwh is None:
            d_kwh = integrated
        elif contiguous:
            ceiling = max(machine.rated_kw, s.kw, state.kw, 1.0) * 3 * dt / 3600 + 0.01
            if d_kwh > ceiling:
                d_kwh = integrated
        d_kvarh = _delta(s.kvarh, state.total_kvarh) or 0.0
        d_kvah = _delta(s.kvah, state.total_kvah) or 0.0
    state.total_kwh = s.kwh if s.kwh is not None else (state.total_kwh or 0.0) + d_kwh
    if s.kvarh is not None:
        state.total_kvarh = s.kvarh
    if s.kvah is not None:
        state.total_kvah = s.kvah

    # Run / stop transitions and runtime
    if s.on and not prev_on:
        state.run_start = s.ts
        state.run_sec = state.run_kwh = state.run_pf_sum = 0.0
        state.run_pf_n = 0
    if prev_on and not s.on:
        state.last_stop = s.ts
    if contiguous and prev_on:  # the machine was running across this interval
        state.run_sec += dt
        state.today_sec += dt
        state.total_runtime_sec += dt
        state.run_kwh += d_kwh
        hr.run_seconds += dt
        hr.run_kwh += d_kwh
    if s.on and s.pf:
        state.run_pf_sum += s.pf
        state.run_pf_n += 1
        hr.sum_pf += s.pf
        hr.pf_samples += 1

    # Hourly consolidation
    hr.kwh += d_kwh
    hr.kvarh += d_kvarh
    hr.kvah += d_kvah
    hr.samples += 1
    hr.sum_kw += s.kw
    hr.max_kw = max(hr.max_kw, s.kw)
    hr.sum_current += s.current
    hr.max_current = max(hr.max_current, s.current)

    # Live values
    state.on, state.kw, state.pf = s.on, s.kw, s.pf
    state.kva, state.kvar, state.current = s.kva, s.kvar, s.current
    state.voltage, state.frequency = s.voltage, s.frequency
    state.last_ts = s.ts


def _keep_raw(state, s):
    """Thin raw storage: one sample per RAW_SAMPLE_INTERVAL_SEC, plus every on/off change."""
    if state.last_raw_ts is None:
        return True
    gap = (s.ts - state.last_raw_ts).total_seconds()
    if gap >= settings.RAW_SAMPLE_INTERVAL_SEC:
        return True
    return gap > 0 and state.last_ts is not None and s.ts > state.last_ts and s.on != state.on


def _auto_register(gateway, meter_id, machines):
    """A verified gateway reported a meter we have not seen: register it as a machine so the
    administrator can name it. Until then it is stored but hidden from the owner. Capped, so a faulty gateway cannot flood us."""
    if len(machines) >= settings.MAX_AUTO_MACHINES_PER_GATEWAY:
        return None
    base = slugify(f"{gateway.serial_number or gateway.name}-{meter_id}")[:55] or "meter"
    candidate, n = base, 1
    while Machine.objects.filter(pk=candidate).exists():
        n += 1
        candidate = f"{base}-{n}"
    machine = Machine.objects.create(
        id=candidate, name=f"Meter {meter_id}", type=Machine.Type.SHELLER, rated_kw=0,
        gateway=gateway, meter_id=meter_id, position=len(machines), configured=False,
    )  # fmt: skip
    machines[meter_id] = machine
    return machine


# --- Entry point ------------------------------------------------------------
@dataclass
class IngestResult:
    accepted: int = 0
    rejected: list = field(default_factory=list)
    unknown_meters: list = field(default_factory=list)
    machine_ids: list = field(default_factory=list)
    events: list = field(default_factory=list)


def ingest(gateway, data, now=None, ip=None):
    now = now or timezone.now()
    good, rejected = parse_payload(data, now)
    result = IngestResult(rejected=rejected)

    machines = {m.meter_id: m for m in Machine.objects.filter(gateway=gateway)}
    by_meter = defaultdict(list)
    for validated, ts in good:
        by_meter[validated["meterId"]].append((ts, validated))

    with transaction.atomic():
        Gateway.objects.filter(pk=gateway.pk).update(last_seen_at=now, last_ip=ip)

        for meter_id, items in by_meter.items():
            machine = machines.get(meter_id) or _auto_register(gateway, meter_id, machines)
            if machine is None:
                result.unknown_meters.append(meter_id)
                continue
            result.accepted += len(items)
            items.sort(key=lambda pair: pair[0])

            state, _ = MachineState.objects.select_for_update().get_or_create(machine=machine)
            hourly, raw, applied = {}, [], 0
            for ts, validated in items:
                s = _complete(validated, machine, ts)
                if _keep_raw(state, s):
                    raw.append(
                        Reading(
                            machine=machine, ts=s.ts, on=s.on, kw=s.kw, pf=s.pf, kva=s.kva,
                            kvar=s.kvar, current=s.current, voltage=s.voltage, frequency=s.frequency,
                        )  # fmt: skip
                    )
                    state.last_raw_ts = s.ts
                if state.last_ts is not None and s.ts <= state.last_ts:
                    continue  # late or duplicate: stored raw at most, never counted twice
                apply_sample(machine, state, s, hourly)
                applied += 1

            if raw:
                Reading.objects.bulk_create(raw, ignore_conflicts=True)
            if applied:
                state.received_at = now
                state.save()
                for report in hourly.values():
                    report.save()
                result.machine_ids.append(machine.pk)
                result.events.extend(evaluate_machine(machine, state, now))
    return result
