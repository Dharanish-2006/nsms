"""Who may see what. Admins see everything; everyone else sees the gateways
(and therefore machines, alerts and plants) an admin has assigned to them."""

from .models import Gateway, Machine, Plant


def accessible_gateways(user):
    qs = Gateway.objects.select_related("plant")
    if user.role == "admin":
        return qs
    return qs.filter(assignments__user=user)


def accessible_machines(user):
    qs = Machine.objects.select_related("gateway__plant")
    if user.role == "admin":
        return qs
    return qs.filter(gateway__assignments__user=user)


def accessible_plants(user):
    if user.role == "admin":
        return Plant.objects.all()
    return Plant.objects.filter(gateways__assignments__user=user).distinct()


def accessible_gateway_ids(user):
    return list(accessible_gateways(user).values_list("pk", flat=True))
