import re

import pytest
from django.core import mail

from apps.accounts.models import User

from .conftest import client_for, make_user

pytestmark = pytest.mark.django_db


def _code():
    return re.search(r"code is (\d{6})", mail.outbox[-1].body).group(1)


def _verified_email(anon, email):
    assert anon.post("/api/auth/otp/send", {"channel": "email", "target": email}, format="json").status_code == 204
    r = anon.post("/api/auth/otp/verify", {"channel": "email", "target": email, "code": _code()}, format="json")
    assert r.status_code == 200
    return r.json()["token"]


def _register(anon, **over):
    body = {
        "fullName": "New Person", "username": "newbie", "email": "new@example.com",
        "emailToken": _verified_email(anon, "new@example.com"),
        "password": "Corr3ct-horse-battery", "role": "user",
    }  # fmt: skip
    body.update(over)
    return anon.post("/api/auth/register", body, format="json")


def test_register_approve_login_flow(anon, admin_client):
    assert _register(anon).status_code == 201

    # Cannot sign in until approved
    r = anon.post("/api/auth/login", {"username": "newbie", "password": "Corr3ct-horse-battery"}, format="json")
    assert r.status_code == 403 and r.json()["code"] == "pending_approval"

    pending = admin_client.get("/api/admin-portal/users?status=pending").json()
    assert [u["username"] for u in pending] == ["newbie"]
    assert "password" not in pending[0]
    assert admin_client.post(f"/api/admin-portal/users/{pending[0]['id']}/approve").status_code == 200

    r = anon.post("/api/auth/login", {"username": "newbie", "password": "Corr3ct-horse-battery"}, format="json")
    assert r.status_code == 200
    token = r.json()["token"]
    anon.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    me = anon.get("/api/auth/me").json()
    assert me["username"] == "newbie" and me["role"] == "user" and me["status"] == "active"

    assert anon.post("/api/auth/logout").status_code == 204
    assert anon.get("/api/auth/me").status_code == 401


def test_admin_role_at_signup_is_only_a_request(anon):
    assert _register(anon, role="admin").status_code == 201
    user = User.objects.get(username="newbie")
    assert user.role == "user" and user.requested_role == "admin" and user.status == "pending"


def test_register_needs_matching_email_proof(anon):
    r = _register(anon, emailToken="not-a-real-token")
    assert r.status_code == 400 and r.json()["code"] == "otp_required"
    token = _verified_email(anon, "someone@example.com")
    r = _register(anon, emailToken=token)  # proof is for a different address
    assert r.status_code == 400


def test_proof_is_single_use(anon):
    token = _verified_email(anon, "new@example.com")
    assert _register(anon, emailToken=token).status_code == 201
    r = _register(anon, emailToken=token, username="second", email="new@example.com")
    assert r.status_code in (400, 409)


def test_taken_username_conflicts_without_burning_the_code(anon):
    make_user("newbie")
    token = _verified_email(anon, "new@example.com")
    r = _register(anon, emailToken=token)
    assert r.status_code == 409 and r.json()["code"] == "username_taken"
    assert _register(anon, emailToken=token, username="other-name").status_code == 201


def test_weak_password_is_rejected_with_a_plain_message(anon):
    r = _register(anon, password="12345678")
    assert r.status_code == 422
    assert r.json()["code"] == "validation" and "Password" in r.json()["message"]


def test_otp_locks_after_five_wrong_tries(anon):
    anon.post("/api/auth/otp/send", {"channel": "email", "target": "a@example.com"}, format="json")
    real = _code()
    wrong = "000000" if real != "000000" else "111111"
    statuses = [
        anon.post("/api/auth/otp/verify", {"channel": "email", "target": "a@example.com", "code": wrong}, format="json").status_code
        for _ in range(5)
    ]
    assert statuses == [400, 400, 400, 400, 429]
    # even the right code no longer works
    r = anon.post("/api/auth/otp/verify", {"channel": "email", "target": "a@example.com", "code": real}, format="json")
    assert r.status_code == 429


def test_otp_send_is_rate_limited_per_target(anon):
    codes = [anon.post("/api/auth/otp/send", {"channel": "email", "target": "a@example.com"}, format="json").status_code for _ in range(4)]
    assert codes == [204, 204, 204, 429]


def test_phone_otp_goes_out_by_sms(anon):
    from apps.common import sms

    assert anon.post("/api/auth/otp/send", {"channel": "phone", "target": "+91 98765 43210"}, format="json").status_code == 204
    digits, text = sms.outbox[-1]
    assert digits == "9876543210" and re.search(r"\d{6}", text)


def test_login_wrong_password_and_lockout(anon, operator):
    for _ in range(10):
        r = anon.post("/api/auth/login", {"username": "asha", "password": "nope"}, format="json")
        assert r.status_code == 401
    r = anon.post("/api/auth/login", {"username": "asha", "password": "S3cure-pass-42"}, format="json")
    assert r.status_code == 429  # account locked for a while, even with the right password


def test_change_password_signs_out_other_sessions(operator):
    a, b = client_for(operator), client_for(operator)
    r = a.post("/api/auth/change-password", {"currentPassword": "wrong", "newPassword": "An0ther-good-pass"}, format="json")
    assert r.status_code == 400 and r.json()["code"] == "wrong_password"
    r = a.post("/api/auth/change-password", {"currentPassword": "S3cure-pass-42", "newPassword": "An0ther-good-pass"}, format="json")
    assert r.status_code == 204
    assert a.get("/api/auth/me").status_code == 200
    assert b.get("/api/auth/me").status_code == 401


def test_admin_endpoints_reject_regular_users_and_anonymous(user_client, anon, operator):
    assert user_client.get("/api/admin-portal/users").status_code == 403
    assert user_client.post(f"/api/admin-portal/users/{operator.pk}/approve").status_code == 403
    assert user_client.get("/api/admin-portal/dashboard").status_code == 403
    r = anon.get("/api/admin-portal/users")
    assert r.status_code == 401 and r.json()["code"] == "unauthenticated"


def test_rejected_user_cannot_sign_in_and_sees_the_reason(anon, admin_client):
    assert _register(anon).status_code == 201
    uid = admin_client.get("/api/admin-portal/users?status=pending").json()[0]["id"]
    assert admin_client.post(f"/api/admin-portal/users/{uid}/reject", {"reason": "Not a customer"}, format="json").status_code == 200
    r = anon.post("/api/auth/login", {"username": "newbie", "password": "Corr3ct-horse-battery"}, format="json")
    assert r.status_code == 403 and r.json()["code"] == "rejected" and "Not a customer" in r.json()["message"]
    assert User.objects.get(username="newbie").status == "rejected"  # kept, not deleted


def test_profile_edit_only_changes_the_name(operator, user_client):
    r = user_client.patch("/api/auth/me", {"fullName": "Asha K", "role": "admin", "email": "x@y.z"}, format="json")
    assert r.status_code == 200 and r.json()["fullName"] == "Asha K"
    operator.refresh_from_db()
    assert operator.role == "user" and operator.email == "asha@example.com"


def test_pending_user_token_is_rejected(db):
    user = make_user("waiting", status="pending")
    assert client_for(user).get("/api/auth/me").status_code == 401
