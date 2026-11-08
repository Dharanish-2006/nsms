"""Report numbers for one plant owner over a time range. Used by the Reports page API and by
the automatic report emails, so both always agree."""

from django.db.models import Max, Sum

from apps.plants.access import accessible_machines, window_q

from .models import HourlyReport

KW_PER_HP = 0.7457  # 1 mechanical horsepower in kW (a physical constant, not a setting)


def rated_hp(machine):
    """The machine's motor rating in HP to one decimal, or None if it is not set."""
    return round(machine.rated_kw / KW_PER_HP, 1) if machine.rated_kw else None


def owner_report_rows(user, start, end, machines=None):
    """One dict per machine the owner can see, summed over [start, end) and only over the hours
    the owner was connected, so a previous owner's hours never appear."""
    if machines is None:
        machines = list(accessible_machines(user))
    ids = [m.pk for m in machines]
    agg = (
        HourlyReport.objects.filter(window_q(user), machine_id__in=ids, hour__gte=start, hour__lt=end)
        .values("machine_id")
        .annotate(
            kwh=Sum("kwh"), run_kwh=Sum("run_kwh"), kvarh=Sum("kvarh"), kvah=Sum("kvah"),
            run_seconds=Sum("run_seconds"), samples=Sum("samples"), sum_kw=Sum("sum_kw"),
            max_kw=Max("max_kw"), max_current=Max("max_current"),
            pf_samples=Sum("pf_samples"), sum_pf=Sum("sum_pf"),
        )
    )  # fmt: skip
    by_machine = {r["machine_id"]: r for r in agg}
    rows = []
    for m in machines:
        r = by_machine.get(m.pk)
        n = (r["samples"] or 0) if r else 0
        rows.append(
            {
                "machineId": m.pk,
                "machineName": m.name,
                "plant": m.gateway.plant.name,
                "motorHp": rated_hp(m),
                "kwh": round(r["kwh"] or 0, 2) if r else 0,
                "runKwh": round(r["run_kwh"] or 0, 2) if r else 0,
                "kvarh": round(r["kvarh"] or 0, 2) if r else 0,
                "kvah": round(r["kvah"] or 0, 2) if r else 0,
                "runSeconds": int(r["run_seconds"] or 0) if r else 0,
                "avgKw": round(r["sum_kw"] / n, 2) if r and n else 0,
                "maxKw": round(r["max_kw"] or 0, 2) if r else 0,
                "avgPf": round(r["sum_pf"] / r["pf_samples"], 3) if r and r["pf_samples"] else None,
                "maxCurrent": round(r["max_current"] or 0, 2) if r else 0,
                "samples": n,
            }
        )  # fmt: skip
    return rows
