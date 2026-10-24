import re
from datetime import datetime, timedelta
from http import HTTPStatus

import pytest
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse

from accounts import security

# --- Signup -----------------------------------------------------------------


def test_signup_page_returns_200(client, db):
    response = client.get(reverse("accounts:signup"))

    assert response.status_code == HTTPStatus.OK


def test_signup_creates_plain_customer(client, db):
    response = client.post(
        reverse("accounts:signup"),
        {
            "username": "fresh-thinker",
            "email": "Fresh@Example.com",
            "password1": "neural-implant-9000",
            "password2": "neural-implant-9000",
        },
        follow=True,
    )

    user = get_user_model().objects.get(username="fresh-thinker")
    # Stored as typed, apart from Django lowercasing the domain.
    assert user.email == "Fresh@example.com"
    assert not user.is_staff
    assert not user.is_superuser

    # Signup hands off to the login page with a confirmation message;
    # auto-login is a student exercise, so the visitor is still anonymous.
    assert response.redirect_chain[-1][0] == reverse("accounts:login")
    assert "Account created" in response.content.decode()
    assert not response.context["user"].is_authenticated


def test_signup_password_mismatch_shows_field_error(client, db):
    response = client.post(
        reverse("accounts:signup"),
        {
            "username": "fresh-thinker",
            "email": "fresh@example.com",
            "password1": "neural-implant-9000",
            "password2": "neural-implant-9001",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["password2"]
    assert not get_user_model().objects.filter(username="fresh-thinker").exists()


def test_signup_requires_an_email(client, db):
    response = client.post(
        reverse("accounts:signup"),
        {
            "username": "fresh-thinker",
            "password1": "neural-implant-9000",
            "password2": "neural-implant-9000",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["email"]
    assert not get_user_model().objects.filter(username="fresh-thinker").exists()


def test_signup_rejects_an_email_in_use_ignoring_capitals(client, customer):
    response = client.post(
        reverse("accounts:signup"),
        {
            "username": "copycat",
            "email": "CUSTOMER@example.com",
            "password1": "neural-implant-9000",
            "password2": "neural-implant-9000",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert "already in use" in response.context["form"].errors["email"][0]
    assert not get_user_model().objects.filter(username="copycat").exists()


# --- Primary email constraint -----------------------------------------------


def test_primary_emails_differing_only_in_capitals_are_rejected(customer):
    with pytest.raises(IntegrityError):
        get_user_model().objects.create_user(
            username="copycat", email="Customer@Example.COM", password="x"
        )


def test_users_without_an_email_may_coexist(db):
    # Admin-, shell- and test-made users may still have no primary.
    User = get_user_model()
    User.objects.create_user(username="nameless-one", password="x")
    User.objects.create_user(username="nameless-two", password="x")

    assert User.objects.filter(email="").count() == 2


# --- Login and logout --------------------------------------------------------


def test_login_page_returns_200(client, db):
    response = client.get(reverse("accounts:login"))

    assert response.status_code == HTTPStatus.OK


def test_login_round_trip(client, customer):
    response = client.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "customer123"},
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse("products:catalog")
    assert response.context["user"] == customer


def test_login_bad_credentials_stays_put(client, customer):
    response = client.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "wrong"},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].non_field_errors()


def test_logout_signs_out_with_message(client, customer):
    client.force_login(customer)

    response = client.post(reverse("accounts:logout"), follow=True)

    assert response.redirect_chain[-1][0] == reverse("products:catalog")
    assert "You have signed out." in response.content.decode()
    assert not response.context["user"].is_authenticated


# --- Auth-aware navbar --------------------------------------------------------


def test_navbar_offers_login_and_signup_to_visitors(client, db):
    page = client.get(reverse("products:catalog")).content.decode()

    assert reverse("accounts:login") in page
    assert reverse("accounts:signup") in page
    assert "Sign out" not in page


def test_navbar_greets_signed_in_customer(client, customer):
    client.force_login(customer)

    page = client.get(reverse("products:catalog")).content.decode()

    assert "Hi, customer" in page
    assert "Sign out" in page
    assert reverse("accounts:signup") not in page


def test_navbar_links_signed_in_users_to_the_security_center(client, staff_user):
    client.force_login(staff_user)

    page = client.get(reverse("products:catalog")).content.decode()

    assert reverse("accounts:security") in page


def test_navbar_hides_the_security_center_from_visitors(client, db):
    page = client.get(reverse("products:catalog")).content.decode()

    assert reverse("accounts:security") not in page


# --- Account Security Center hub ----------------------------------------------


@pytest.mark.parametrize("name", ["accounts:security", "accounts:password_change"])
def test_security_pages_send_visitors_to_login(client, db, name):
    url = reverse(name)

    response = client.get(url)

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == f"{reverse('accounts:login')}?next={url}"


def test_hub_shows_primary_email_and_secondary_empty_state(client, customer):
    client.force_login(customer)

    response = client.get(reverse("accounts:security"))

    page = response.content.decode()
    assert response.status_code == HTTPStatus.OK
    assert "customer@example.com" in page
    assert "No backup email yet" in page
    assert reverse("accounts:password_change") in page


def test_hub_works_for_a_user_without_a_primary(client, db):
    user = get_user_model().objects.create_user(username="nameless", password="x")
    client.force_login(user)

    response = client.get(reverse("accounts:security"))

    assert response.status_code == HTTPStatus.OK
    assert "No primary email on file" in response.content.decode()


def test_staff_use_the_storefront_security_center(client, staff_user):
    client.force_login(staff_user)

    response = client.get(reverse("accounts:security"))

    assert response.status_code == HTTPStatus.OK
    assert "employee@example.com" in response.content.decode()
    assert "backoffice/base.html" not in [t.name for t in response.templates]


# --- Change password ----------------------------------------------------------


def change_password(client, old="customer123", new="fresh-cortex-4471"):
    return client.post(
        reverse("accounts:password_change"),
        {"old_password": old, "new_password1": new, "new_password2": new},
    )


def test_change_password_page_returns_200(client, customer):
    client.force_login(customer)

    response = client.get(reverse("accounts:password_change"))

    assert response.status_code == HTTPStatus.OK


def test_change_password_sets_the_new_password(client, customer):
    client.force_login(customer)

    response = change_password(client)

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("accounts:password_change_done")
    customer.refresh_from_db()
    assert customer.check_password("fresh-cortex-4471")


def test_change_password_keeps_this_session_and_ends_the_others(client, customer):
    other_device = Client()
    other_device.force_login(customer)
    client.force_login(customer)

    change_password(client)

    hub = reverse("accounts:security")
    assert client.get(hub).status_code == HTTPStatus.OK
    assert other_device.get(hub).status_code == HTTPStatus.FOUND


def test_change_password_rejects_a_wrong_current_password(client, customer):
    client.force_login(customer)

    response = change_password(client, old="not-my-password")

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["old_password"]
    customer.refresh_from_db()
    assert customer.check_password("customer123")
    assert mail.outbox == []


def test_change_password_notifies_the_primary(client, customer):
    client.force_login(customer)

    change_password(client)

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["customer@example.com"]
    assert "password was changed" in mail.outbox[0].subject


def test_change_password_done_page_returns_200(client, customer):
    client.force_login(customer)

    response = client.get(reverse("accounts:password_change_done"))

    assert response.status_code == HTTPStatus.OK
    assert "Password changed" in response.content.decode()


# --- Security notices ---------------------------------------------------------


def test_security_notice_goes_to_the_primary(customer):
    sent = security.send_security_notice(customer, security.Notice.PASSWORD_CHANGED)

    assert sent
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["customer@example.com"]
    assert "customer" in mail.outbox[0].body


def test_security_notice_skips_a_user_without_a_primary(db):
    user = get_user_model().objects.create_user(username="nameless", password="x")

    sent = security.send_security_notice(user, security.Notice.PASSWORD_CHANGED)

    assert not sent
    assert mail.outbox == []


# --- Mail cooldown ------------------------------------------------------------


def test_cooldown_allows_the_first_claim_and_refuses_the_second():
    assert security.claim_mail_cooldown("customer@example.com")
    assert not security.claim_mail_cooldown("CUSTOMER@example.com")


def test_cooldown_is_per_address():
    assert security.claim_mail_cooldown("customer@example.com")
    assert security.claim_mail_cooldown("employee@example.com")


def test_cooldown_claims_a_sixty_second_window(monkeypatch):
    calls = []
    monkeypatch.setattr(security.cache, "add", lambda *args: calls.append(args) or True)

    security.claim_mail_cooldown("customer@example.com")

    [(_key, _value, timeout)] = calls
    assert timeout == 60


# --- Forgotten password -------------------------------------------------------


def request_reset(client, email="customer@example.com"):
    return client.post(reverse("accounts:password_reset"), {"email": email})


def reset_link(message):
    """The path of the reset link in an email, from ``/accounts/`` on."""
    match = re.search(r"https?://[^/\s]+(/accounts/password-reset/\S+)", message.body)
    assert match, message.body
    return match.group(1)


def test_login_page_links_to_password_reset(client, db):
    page = client.get(reverse("accounts:login")).content.decode()

    assert "Forgot your password?" in page
    assert reverse("accounts:password_reset") in page


@pytest.mark.parametrize(
    "name",
    [
        "accounts:password_reset",
        "accounts:password_reset_done",
        "accounts:password_reset_complete",
    ],
)
def test_reset_pages_work_signed_out(client, db, name):
    response = client.get(reverse(name))

    assert response.status_code == HTTPStatus.OK


def test_reset_timeout_defaults_to_one_hour():
    assert django_settings.PASSWORD_RESET_TIMEOUT == 60 * 60


def test_reset_mails_a_link_to_the_primary(client, customer):
    response = request_reset(client)

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("accounts:password_reset_done")
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["customer@example.com"]
    assert reset_link(mail.outbox[0])


def test_reset_matches_ignoring_capitals_and_mails_the_address_typed(client, customer):
    request_reset(client, "CUSTOMER@Example.com")

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["CUSTOMER@Example.com"]


def test_reset_response_is_identical_for_an_unknown_address(client, customer):
    known = request_reset(client, "customer@example.com")
    unknown = request_reset(client, "nobody@example.com")

    assert (unknown.status_code, unknown.url) == (known.status_code, known.url)
    assert [m.to for m in mail.outbox] == [["customer@example.com"]]
    done = client.get(unknown.url).content.decode()
    assert "If an account matches" in done


def test_reset_ignores_inactive_users(client, customer):
    customer.is_active = False
    customer.save()

    request_reset(client)

    assert mail.outbox == []


def test_reset_sends_at_most_one_email_a_minute_per_address(client, customer):
    first = request_reset(client)
    second = request_reset(client, "Customer@example.com")

    assert len(mail.outbox) == 1
    assert second.status_code == first.status_code
    assert second.url == first.url


def test_reset_link_sets_a_new_password_and_notifies_the_primary(client, customer):
    request_reset(client)
    form_url = client.get(reset_link(mail.outbox[0]), follow=True).redirect_chain[-1][0]

    response = client.post(
        form_url,
        {"new_password1": "fresh-cortex-4471", "new_password2": "fresh-cortex-4471"},
    )

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("accounts:password_reset_complete")
    customer.refresh_from_db()
    assert customer.check_password("fresh-cortex-4471")
    # No auto-login: the customer signs in themselves.
    assert "_auth_user_id" not in client.session

    notice = mail.outbox[1]
    assert notice.to == ["customer@example.com"]
    assert "password was reset" in notice.subject


def test_reset_link_works_only_once(client, customer):
    request_reset(client)
    link = reset_link(mail.outbox[0])
    form_url = client.get(link, follow=True).redirect_chain[-1][0]
    client.post(
        form_url,
        {"new_password1": "fresh-cortex-4471", "new_password2": "fresh-cortex-4471"},
    )

    response = Client().get(link, follow=True)

    assert not response.context["validlink"]
    assert "no longer works" in response.content.decode()


def test_reset_link_dies_when_the_password_changes(client, customer):
    request_reset(client)
    link = reset_link(mail.outbox[0])
    customer.set_password("changed-elsewhere-123")
    customer.save()

    response = client.get(link, follow=True)

    assert not response.context["validlink"]


def test_reset_link_expires_after_an_hour(client, customer, monkeypatch):
    request_reset(client)
    link = reset_link(mail.outbox[0])
    later = datetime.now() + timedelta(hours=1, minutes=1)
    monkeypatch.setattr(default_token_generator, "_now", lambda: later)

    response = client.get(link, follow=True)

    assert not response.context["validlink"]
