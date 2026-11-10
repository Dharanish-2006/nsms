"""Builds the `machine` object of docs/API.md from stored state. Used by the REST
endpoints and by the WebSocket feed so both always agree."""

from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from apps.common.timeutil import local_day_start, to_ms

from apps.plants.access import current_period_starts
from apps.plants.models import Machine

from .models import HourlyReport


def hourly_rows_today(machine_ids, now):
    """{machine_id: [HourlyReport...]} for the current IST day, in one query."""
    rows = defaultdict(list)
    machine_ids = list(machine_ids)
    qs = HourlyReport.objects.filter(machine_id__in=machine_ids, hour__gte=local_day_start(now))
    # Hours before the current owner connected belong to someone else.
    gateway_of = dict(Machine.objects.filter(pk__in=machine_ids).values_list("pk", "gateway_id"))
    started = current_period_starts(set(gateway_of.values()))
    for row in qs:
        begin = started.get(gateway_of.get(row.machine_id))
        if begin is not None and row.hour <= begin - timedelta(hours=1):
            continue
        rows[row.machine_id].append(row)
    return rows


def machine_payload(machine, state, hourly_rows, now):
    local_now = timezone.localtime(now)
    on = bool(state and state.on)

    hourly_kwh = [0.0] * 24
    today_run_kwh = 0.0
    hour_on = [0 if h <= local_now.hour else 2 for h in range(24)]
    for row in hourly_rows:
        local = timezone.localtime(row.hour)
        if local.date() == local_now.date():
            hourly_kwh[local.hour] = round(row.kwh, 3)
            today_run_kwh += row.run_kwh
            hour_on[local.hour] = 1 if row.run_seconds > 0 else 0

    if state is None:
        return {
            "id": machine.pk, "name": machine.name, "plant": machine.gateway.plant.name,
            "type": machine.type, "ratedKw": machine.rated_kw,
            "gatewayId": str(machine.gateway_id), "meterId": machine.meter_id,
            "on": False, "updatedAt": 0,
            "kw": 0, "pf": 0, "kva": 0, "kvar": 0, "current": 0, "loadFactor": 0,
            "totalKwh": 0, "totalKvarh": 0, "totalKvah": 0, "runKwh": 0, "todayRunKwh": round(today_run_kwh, 3),
            "runStart": None, "lastStop": None, "runSec": 0, "todaySec": 0,
            "totalRuntimeSec": 0, "avgPfRun": None,
            "hourlyKwh": hourly_kwh, "hourOn": hour_on,
        }  # fmt: skip

    # Electrical values read 0 while the machine is off (docs/API.md).
    kw = state.kw if on else 0
    pf = (state.pf or 0) if on else 0
    kva = state.kva if on else 0
    kvar = state.kvar if on else 0
    current = state.current if on else 0
    load_factor = (kw / machine.rated_kw * 100) if on and machine.rated_kw else 0
    today_sec = state.today_sec if state.today_date == local_now.date() else 0
    avg_pf_run = (state.run_pf_sum / state.run_pf_n) if on and state.run_pf_n else None

    return {
        "id": machine.pk,
        "name": machine.name,
        "plant": machine.gateway.plant.name,
        "type": machine.type,
        "ratedKw": machine.rated_kw,
        "gatewayId": str(machine.gateway_id),
        "meterId": machine.meter_id,
        "on": on,
        "updatedAt": to_ms(state.received_at or state.last_ts) or 0,
        "kw": round(kw, 2),
        "pf": round(pf, 3),
        "kva": round(kva, 2),
        "kvar": round(kvar, 2),
        "current": round(current, 2),
        "loadFactor": round(load_factor, 1),
        "totalKwh": round(state.total_kwh or 0, 2),
        "totalKvarh": round(state.total_kvarh or 0, 2),
        "totalKvah": round(state.total_kvah or 0, 2),
        "runKwh": round(state.run_kwh, 3) if on else 0,
        "todayRunKwh": round(today_run_kwh, 3),
        "runStart": to_ms(state.run_start) if on else None,
        "lastStop": to_ms(state.last_stop),
        "runSec": int(state.run_sec) if on else 0,
        "todaySec": int(today_sec),
        "totalRuntimeSec": int(state.total_runtime_sec),
        "avgPfRun": round(avg_pf_run, 3) if avg_pf_run is not None else None,
        "hourlyKwh": hourly_kwh,
        "hourOn": hour_on,
    }


def build_payloads(machines, now=None):
    """`machines` must be loaded with select_related("gateway__plant", "state")."""
    now = now or timezone.now()
    machines = list(machines)
    rows = hourly_rows_today([m.pk for m in machines], now)
    return [machine_payload(m, getattr(m, "state", None), rows.get(m.pk, []), now) for m in machines]
