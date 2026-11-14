import pytest
from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient

from apps.enquiries.models import Enquiry

from .conftest import client_for

GOOD = {"name": "  Ravi   Kumar ", "mobile": "+91 98765 43210", "requirement": "Need to monitor two shellers."}


@pytest.fixture(autouse=True)
def _fresh_throttle():
    from django.core.cache import cache

    cache.clear()


@override_settings(ENQUIRY_NOTIFY_EMAIL="team@example.com, boss@example.com")
def test_enquiry_is_saved_and_the_team_is_emailed(db):
    r = APIClient().post("/api/contact", GOOD, format="json")
    assert r.status_code == 201 and r.json() == {"ok": True}
    e = Enquiry.objects.get()
    assert (e.name, e.mobile, e.status, e.emailed) == ("Ravi Kumar", "9876543210", "new", True)
    assert mail.outbox[0].to == ["team@example.com", "boss@example.com"]
    assert "9876543210" in mail.outbox[0].body


def test_enquiry_is_kept_when_the_email_fails(db, monkeypatch):
    def boom(*a, **k):
        raise OSError("smtp down")

    monkeypatch.setattr("apps.enquiries.views.send_mail", boom)
    with override_settings(ENQUIRY_NOTIFY_EMAIL="team@example.com"):
        r = APIClient().post("/api/contact", GOOD, format="json")
    assert r.status_code == 201
    assert Enquiry.objects.get().emailed is False


def test_no_notify_address_still_saves(db):
    assert APIClient().post("/api/contact", GOOD, format="json").status_code == 201
    assert Enquiry.objects.count() == 1 and mail.outbox == []


@pytest.mark.parametrize(
    "patch",
    [{"name": ""}, {"name": "   "}, {"mobile": "12345"}, {"mobile": "5876543210"}, {"requirement": ""}, {"requirement": "hi"}],
)
def test_bad_input_is_refused(db, patch):
    r = APIClient().post("/api/contact", {**GOOD, **patch}, format="json")
    assert r.status_code == 422 and Enquiry.objects.count() == 0


def test_honeypot_stores_nothing(db):
    r = APIClient().post("/api/contact", {**GOOD, "website": "http://spam.example"}, format="json")
    assert r.status_code == 201 and Enquiry.objects.count() == 0


def test_contact_is_rate_limited(db):
    c = APIClient()
    codes = [c.post("/api/contact", GOOD, format="json").status_code for _ in range(7)]
    assert codes[:5] == [201] * 5 and 429 in codes[5:]


def test_admin_lists_and_updates_enquiries_owner_cannot(db, admin_client, operator):
    APIClient().post("/api/contact", GOOD, format="json")
    assert client_for(operator).get("/api/admin-portal/enquiries").status_code == 403
    assert APIClient().get("/api/admin-portal/enquiries").status_code in (401, 403)
    rows = admin_client.get("/api/admin-portal/enquiries?status=new").json()
    assert len(rows) == 1 and rows[0]["requirement"].startswith("Need")
    assert admin_client.get("/api/admin-portal/dashboard").json()["newEnquiries"] == 1
    r = admin_client.put(f"/api/admin-portal/enquiries/{rows[0]['id']}", {"status": "contacted"}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "contacted" and r.json()["handledBy"]
    assert admin_client.get("/api/admin-portal/enquiries?status=new").json() == []
    assert admin_client.get("/api/admin-portal/dashboard").json()["newEnquiries"] == 0
    assert admin_client.put(f"/api/admin-portal/enquiries/{rows[0]['id']}", {"status": "x"}, format="json").status_code == 422
    assert admin_client.get("/api/admin-portal/enquiries?status=zzz").status_code == 422
