import re
import time
from datetime import datetime, timedelta
from http import HTTPStatus
from types import SimpleNamespace

import pytest
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail, signing
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse

from accounts import security
from accounts.models import UserQuerySet

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


# --- Secondary email: model and constraints ---------------------------------


def make_user(username, email="", secondary=None, verified=False):
    return get_user_model().objects.create_user(
        username=username,
        email=email,
        password="x",
        secondary_email=secondary,
        secondary_email_verified=verified,
    )


def test_two_users_may_hold_the_same_pending_secondary(db):
    make_user("first", secondary="shared@example.com")
    make_user("second", secondary="SHARED@example.com")

    pending = get_user_model().objects.filter(
        secondary_email__iexact="shared@example.com"
    )
    assert pending.count() == 2


def test_a_second_verified_copy_of_a_secondary_is_rejected(db):
    make_user("first", secondary="shared@example.com", verified=True)

    with pytest.raises(IntegrityError):
        make_user("second", secondary="Shared@Example.com", verified=True)


def test_clean_rejects_a_secondary_equal_to_the_primary(customer):
    customer.secondary_email = "CUSTOMER@example.com"

    with pytest.raises(ValidationError) as excinfo:
        customer.full_clean()

    assert "secondary_email" in excinfo.value.message_dict


def test_clean_rejects_a_primary_that_is_another_users_verified_secondary(customer):
    make_user("other", secondary="taken@example.com", verified=True)
    customer.email = "Taken@example.com"

    with pytest.raises(ValidationError) as excinfo:
        customer.full_clean()

    assert "email" in excinfo.value.message_dict


def test_clean_rejects_a_verified_secondary_that_is_another_users_primary(customer):
    other = make_user("other", secondary="CUSTOMER@example.com", verified=True)

    with pytest.raises(ValidationError) as excinfo:
        other.full_clean()

    assert "secondary_email" in excinfo.value.message_dict


def test_setting_a_secondary_always_resets_it_to_unverified(customer):
    customer.set_secondary_email("backup@example.com")
    customer.confirm_secondary_email()

    customer.set_secondary_email("newer@example.com")

    customer.refresh_from_db()
    assert customer.secondary_email == "newer@example.com"
    assert not customer.secondary_email_verified


def test_removing_a_secondary_clears_it(customer):
    customer.set_secondary_email("backup@example.com")
    customer.confirm_secondary_email()

    customer.remove_secondary_email()

    customer.refresh_from_db()
    assert customer.secondary_email is None
    assert not customer.secondary_email_verified


def test_signup_rejects_another_accounts_verified_secondary(client, db):
    make_user("other", secondary="taken@example.com", verified=True)

    response = client.post(
        reverse("accounts:signup"),
        {
            "username": "copycat",
            "email": "TAKEN@example.com",
            "password1": "neural-implant-9000",
            "password2": "neural-implant-9000",
        },
    )

    assert "already in use" in response.context["form"].errors["email"][0]


def test_a_pending_secondary_never_blocks_signup(client, db):
    make_user("squatter", secondary="victim@example.com")

    client.post(
        reverse("accounts:signup"),
        {
            "username": "victim",
            "email": "victim@example.com",
            "password1": "neural-implant-9000",
            "password2": "neural-implant-9000",
        },
    )

    assert get_user_model().objects.filter(username="victim").exists()


# --- Secondary email: the security module -----------------------------------


@pytest.fixture
def rf_request(rf):
    return rf.get("/")


def confirm_link(message):
    """The path of the confirmation link in an email, from ``/accounts/`` on."""
    match = re.search(
        r"https?://[^/\s]+(/accounts/secondary-email/confirm/\S+)", message.body
    )
    assert match, message.body
    return match.group(1)


def token_from(message):
    return confirm_link(message).rstrip("/").rsplit("/", 1)[1]


def test_requesting_a_secondary_mails_the_link_and_notifies_the_primary(
    customer, rf_request
):
    sent = security.request_secondary_email(customer, "backup@example.com", rf_request)

    assert sent
    customer.refresh_from_db()
    assert customer.has_pending_secondary_email
    confirmation, notice = mail.outbox
    assert confirmation.to == ["backup@example.com"]
    assert confirm_link(confirmation)
    assert notice.to == ["customer@example.com"]
    assert "added" in notice.subject
    assert "backup@example.com" in notice.body


def test_replacing_a_secondary_sends_the_replaced_notice(customer, rf_request):
    security.request_secondary_email(customer, "backup@example.com", rf_request)

    security.request_secondary_email(customer, "newer@example.com", rf_request)

    assert mail.outbox[-2].to == ["newer@example.com"]
    assert "replaced" in mail.outbox[-1].subject


def test_confirming_a_token_verifies_and_notifies(customer, rf_request):
    security.request_secondary_email(customer, "backup@example.com", rf_request)
    token = token_from(mail.outbox[0])

    user = security.confirm_secondary_email(token)

    assert user == customer
    customer.refresh_from_db()
    assert customer.secondary_email_verified
    assert mail.outbox[-1].to == ["customer@example.com"]
    assert "confirmed" in mail.outbox[-1].subject


def test_confirm_max_age_defaults_to_a_day():
    assert django_settings.SECONDARY_EMAIL_CONFIRM_MAX_AGE == 24 * 60 * 60


def test_an_expired_token_is_rejected(customer, rf_request, monkeypatch):
    security.request_secondary_email(customer, "backup@example.com", rf_request)
    token = token_from(mail.outbox[0])
    later = time.time() + 24 * 60 * 60 + 1
    monkeypatch.setattr(signing, "time", SimpleNamespace(time=lambda: later))

    with pytest.raises(security.ConfirmationError, match="no longer works"):
        security.check_confirmation_token(token)


def test_a_forged_token_is_rejected(db):
    with pytest.raises(security.ConfirmationError):
        security.check_confirmation_token("not-a-real-token")


def test_a_token_for_a_replaced_address_is_rejected(customer, rf_request):
    security.request_secondary_email(customer, "typo@example.com", rf_request)
    old_token = token_from(mail.outbox[0])
    security.request_secondary_email(customer, "backup@example.com", rf_request)

    with pytest.raises(security.ConfirmationError):
        security.confirm_secondary_email(old_token)

    customer.refresh_from_db()
    assert not customer.secondary_email_verified


def test_a_used_token_is_rejected(customer, rf_request):
    security.request_secondary_email(customer, "backup@example.com", rf_request)
    token = token_from(mail.outbox[0])
    security.confirm_secondary_email(token)

    with pytest.raises(security.ConfirmationError):
        security.confirm_secondary_email(token)


def test_confirming_fails_if_another_account_verified_the_address_first(
    customer, staff_user, rf_request
):
    security.request_secondary_email(customer, "shared@example.com", rf_request)
    customer_token = token_from(mail.outbox[0])
    staff_user.set_secondary_email("shared@example.com")
    staff_user.confirm_secondary_email()

    with pytest.raises(security.ConfirmationError, match="already claimed"):
        security.confirm_secondary_email(customer_token)

    customer.refresh_from_db()
    assert customer.has_pending_secondary_email


def test_confirming_fails_if_the_address_became_a_primary(customer, rf_request):
    security.request_secondary_email(customer, "newcomer@example.com", rf_request)
    token = token_from(mail.outbox[0])
    make_user("newcomer", email="Newcomer@example.com")

    with pytest.raises(security.ConfirmationError, match="already claimed"):
        security.confirm_secondary_email(token)


def test_the_constraint_judges_a_confirmation_race(customer, staff_user, monkeypatch):
    # Blind the check, as a concurrent confirmation would; the database
    # constraint still lets only one account verify the address.
    customer.set_secondary_email("shared@example.com")
    staff_user.set_secondary_email("shared@example.com")
    staff_user.confirm_secondary_email()
    monkeypatch.setattr(UserQuerySet, "with_address", lambda self, address: self.none())

    with pytest.raises(ValidationError):
        customer.confirm_secondary_email()

    customer.refresh_from_db()
    assert not customer.secondary_email_verified


def test_a_second_confirmation_send_within_the_cooldown_sends_nothing(
    customer, rf_request
):
    security.request_secondary_email(customer, "backup@example.com", rf_request)
    mail.outbox.clear()

    sent = security.send_secondary_confirmation(customer, rf_request)

    assert not sent
    assert mail.outbox == []


def test_no_confirmation_is_sent_without_a_pending_secondary(customer, rf_request):
    assert not security.send_secondary_confirmation(customer, rf_request)
    assert mail.outbox == []


def test_removing_a_secondary_notifies_the_primary(customer):
    customer.set_secondary_email("backup@example.com")

    assert security.remove_secondary_email(customer)

    assert mail.outbox[0].to == ["customer@example.com"]
    assert "removed" in mail.outbox[0].subject
    assert "backup@example.com" in mail.outbox[0].body


def test_removing_when_there_is_no_secondary_sends_nothing(customer):
    assert not security.remove_secondary_email(customer)
    assert mail.outbox == []


# --- Secondary email: pages ---------------------------------------------------


def add_secondary(client, email="backup@example.com", password="customer123"):
    return client.post(
        reverse("accounts:secondary_email"), {"email": email, "password": password}
    )


@pytest.mark.parametrize(
    "name",
    [
        "accounts:secondary_email",
        "accounts:secondary_email_remove",
        "accounts:secondary_email_resend",
    ],
)
def test_secondary_pages_send_visitors_to_login(client, db, name):
    url = reverse(name)

    response = client.post(url)

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == f"{reverse('accounts:login')}?next={url}"


def test_secondary_email_page_returns_200(client, customer):
    client.force_login(customer)

    response = client.get(reverse("accounts:secondary_email"))

    assert response.status_code == HTTPStatus.OK


def test_hub_links_to_adding_a_secondary(client, customer):
    client.force_login(customer)

    page = client.get(reverse("accounts:security")).content.decode()

    assert reverse("accounts:secondary_email") in page


def test_adding_a_secondary_requires_the_current_password(client, customer):
    client.force_login(customer)

    response = add_secondary(client, password="not-my-password")

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["password"]
    customer.refresh_from_db()
    assert customer.secondary_email is None
    assert mail.outbox == []


def test_adding_a_secondary_sends_the_link_and_shows_it_pending(client, customer):
    client.force_login(customer)

    response = add_secondary(client)

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("accounts:security")
    assert [m.to for m in mail.outbox] == [
        ["backup@example.com"],
        ["customer@example.com"],
    ]
    page = client.get(response.url).content.decode()
    assert "backup@example.com" in page
    assert "Pending" in page
    assert "sent a confirmation link" in page
    assert reverse("accounts:secondary_email_resend") in page


@pytest.mark.parametrize(
    ("email", "error"),
    [
        ("CUSTOMER@example.com", "your primary email"),
        ("EMPLOYEE@example.com", "already in use"),
    ],
)
def test_adding_a_secondary_rejects_addresses_that_cannot_work(
    client, customer, staff_user, email, error
):
    client.force_login(customer)

    response = add_secondary(client, email=email)

    assert error in response.context["form"].errors["email"][0]


def test_adding_another_accounts_verified_secondary_is_rejected(client, customer):
    make_user("other", secondary="taken@example.com", verified=True)
    client.force_login(customer)

    response = add_secondary(client, email="Taken@example.com")

    assert "already in use" in response.context["form"].errors["email"][0]


def test_adding_another_accounts_pending_secondary_is_allowed(client, customer):
    make_user("other", secondary="shared@example.com")
    client.force_login(customer)

    response = add_secondary(client, email="shared@example.com")

    assert response.status_code == HTTPStatus.FOUND


def test_replacing_a_verified_secondary_stops_it_counting_at_once(client, customer):
    customer.set_secondary_email("backup@example.com")
    customer.confirm_secondary_email()
    client.force_login(customer)

    add_secondary(client, email="newer@example.com")

    customer.refresh_from_db()
    assert customer.secondary_email == "newer@example.com"
    assert not customer.secondary_email_verified
    assert "replaced" in mail.outbox[-1].subject


def test_hub_shows_a_verified_secondary(client, customer):
    customer.set_secondary_email("backup@example.com")
    customer.confirm_secondary_email()
    client.force_login(customer)

    page = client.get(reverse("accounts:security")).content.decode()

    assert "Verified" in page
    assert reverse("accounts:secondary_email_resend") not in page


def test_remove_button_clears_the_secondary(client, customer):
    customer.set_secondary_email("backup@example.com")
    client.force_login(customer)

    response = client.post(reverse("accounts:secondary_email_remove"), follow=True)

    customer.refresh_from_db()
    assert customer.secondary_email is None
    assert "No backup email yet" in response.content.decode()
    assert "removed" in mail.outbox[0].subject


def test_remove_does_not_accept_get(client, customer):
    customer.set_secondary_email("backup@example.com")
    client.force_login(customer)

    response = client.get(reverse("accounts:secondary_email_remove"))

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    customer.refresh_from_db()
    assert customer.secondary_email == "backup@example.com"


def test_resend_mails_a_fresh_link_at_most_once_a_minute(client, customer):
    customer.set_secondary_email("backup@example.com")
    client.force_login(customer)
    resend = reverse("accounts:secondary_email_resend")

    first = client.post(resend, follow=True)
    second = client.post(resend, follow=True)

    assert [m.to for m in mail.outbox] == [["backup@example.com"]]
    assert "sent a confirmation link" in first.content.decode()
    assert "sent a confirmation link" in second.content.decode()


def test_resend_does_nothing_for_a_verified_secondary(client, customer):
    customer.set_secondary_email("backup@example.com")
    customer.confirm_secondary_email()
    client.force_login(customer)

    client.post(reverse("accounts:secondary_email_resend"))

    assert mail.outbox == []


def test_confirmation_page_works_signed_out_and_get_changes_nothing(client, customer):
    client.force_login(customer)
    add_secondary(client)
    link = confirm_link(mail.outbox[0])

    response = Client().get(link)

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert "backup@example.com" in page
    assert "Confirm" in page
    customer.refresh_from_db()
    assert not customer.secondary_email_verified


def test_confirmation_page_confirms_on_post(client, customer):
    client.force_login(customer)
    add_secondary(client)
    link = confirm_link(mail.outbox[0])

    response = Client().post(link)

    assert response.status_code == HTTPStatus.OK
    assert "Secondary email confirmed" in response.content.decode()
    customer.refresh_from_db()
    assert customer.secondary_email_verified


def test_confirmation_page_explains_a_dead_link(client, customer):
    client.force_login(customer)
    add_secondary(client)
    link = confirm_link(mail.outbox[0])
    client.post(reverse("accounts:secondary_email_remove"))

    on_get = Client().get(link)
    on_post = Client().post(link)

    assert "no longer works" in on_get.content.decode()
    assert "no longer works" in on_post.content.decode()


def test_confirmation_page_explains_an_address_claimed_elsewhere(client, customer):
    client.force_login(customer)
    add_secondary(client, email="shared@example.com")
    link = confirm_link(mail.outbox[0])
    make_user("quicker", secondary="shared@example.com", verified=True)

    response = Client().post(link)

    assert "already claimed" in response.content.decode()


# --- Password reset by verified secondary -----------------------------------


def test_reset_matches_a_verified_secondary_and_mails_it(client, customer):
    customer.set_secondary_email("backup@example.com")
    customer.confirm_secondary_email()

    request_reset(client, "Backup@example.com")

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["Backup@example.com"]
    assert reset_link(mail.outbox[0])


def test_reset_ignores_a_pending_secondary(client, customer):
    customer.set_secondary_email("backup@example.com")

    response = request_reset(client, "backup@example.com")

    assert response.url == reverse("accounts:password_reset_done")
    assert mail.outbox == []
