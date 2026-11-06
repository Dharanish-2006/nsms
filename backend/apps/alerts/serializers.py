from rest_framework import serializers

from apps.common.errors import ApiError
from apps.common.timeutil import to_ms
from apps.plants.models import Machine

from .models import PhoneNumber, Threshold

# Unit-less parameters and which direction is "worse" (only "below" exists today).
RANGE_01 = {"powerFactor"}


def alert_json(alert):
    machine = alert.machine
    return {
        "key": alert.key,
        "thresholdId": str(alert.threshold_id),
        "machineId": machine.pk,
        "machineName": machine.name,
        "plant": machine.gateway.plant.name,
        "param": alert.param,
        "severity": alert.severity,
        "status": alert.status,
        "reading": round(alert.reading, 3),
        "limit": alert.limit_value,
        "since": to_ms(alert.since),
        "recoveredAt": to_ms(alert.recovered_at),
    }


def threshold_json(t):
    return {
        "id": str(t.pk),
        "param": t.param,
        "machineId": t.machine_id or "all",
        "warning": t.warning,
        "critical": t.critical,
    }


def phone_json(p):
    return {"id": str(p.pk), "digits": p.digits, "label": p.label}


class ThresholdSerializer(serializers.Serializer):
    param = serializers.ChoiceField(Threshold.Param.values)
    machineId = serializers.CharField(max_length=64, default="all")
    warning = serializers.FloatField(allow_null=True, required=False, default=None)
    critical = serializers.FloatField(allow_null=True, required=False, default=None)

    def validate(self, attrs):
        warning, critical, param = attrs["warning"], attrs["critical"], attrs["param"]
        if warning is None and critical is None:
            raise serializers.ValidationError("Set at least one limit.")
        for name, value in (("warning", warning), ("critical", critical)):
            if value is None:
                continue
            if value != value or abs(value) == float("inf"):
                raise serializers.ValidationError({name: "Enter a number."})
            if param in RANGE_01 and not 0 < value <= 1:
                raise serializers.ValidationError({name: "Power factor limits are between 0 and 1."})
        if warning is not None and critical is not None:
            # Power factor is worse when LOWER, so critical must be at or below warning.
            if param == "powerFactor" and critical > warning:
                raise serializers.ValidationError(
                    "The critical limit must be at or below the warning limit."
                )
            if param != "powerFactor" and critical < warning:
                raise serializers.ValidationError(
                    "The critical limit must be at or above the warning limit."
                )

        machine_id = attrs["machineId"]
        attrs["machine"] = None
        if machine_id != "all":
            machine = Machine.objects.filter(pk=machine_id).first()
            if machine is None:
                raise serializers.ValidationError({"machineId": "Unknown machine."})
            attrs["machine"] = machine
        return attrs

    def check_unique(self, attrs, exclude_pk=None):
        qs = Threshold.objects.filter(param=attrs["param"], machine=attrs["machine"])
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if qs.exists():
            raise ApiError(
                "A threshold for that parameter and machine already exists.", 409, "duplicate"
            )


class PhoneSerializer(serializers.Serializer):
    digits = serializers.RegexField(
        r"^\d{10}$", error_messages={"invalid": "Enter exactly 10 digits, without the country code."}
    )
    label = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")

    def check_unique(self, digits, exclude_pk=None):
        qs = PhoneNumber.objects.filter(digits=digits)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if qs.exists():
            raise ApiError("That number is already in the list.", 409, "duplicate")
