import hashlib
import hmac
import json
import time
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentications.models import CustomUser
from .models import Subscription, SubscriptionPlan

WEBHOOK_SECRET = "whsec_test"


def post_event(event_type, obj):
    payload = json.dumps({"id": "evt_1", "object": "event", "type": event_type, "data": {"object": obj}})
    timestamp = int(time.time())
    signature = hmac.new(WEBHOOK_SECRET.encode(), f"{timestamp}.{payload}".encode(), hashlib.sha256).hexdigest()
    return APIClient().post(
        "/api/payment/webhook/", payload, content_type="application/json",
        HTTP_STRIPE_SIGNATURE=f"t={timestamp},v1={signature}",
    )


@mock.patch("payment.views.endpoint_secret", WEBHOOK_SECRET)
class WebhookTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(email="p@test.com", password="x")
        self.plan = SubscriptionPlan.objects.create(name="Monthly", amount=10, price_id="price_1")
        self.subscription = Subscription.objects.create(
            user=self.user, plan=self.plan, stripe_subscription_id="sub_1", is_active=True, auto_renew=True,
        )

    def test_bad_signature_is_rejected(self):
        response = APIClient().post(
            "/api/payment/webhook/", "{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="t=1,v1=x"
        )
        self.assertEqual(response.status_code, 400)

    def test_subscription_deleted_deactivates(self):
        response = post_event("customer.subscription.deleted", {"id": "sub_1", "object": "subscription"})
        self.assertEqual(response.status_code, 200)
        self.subscription.refresh_from_db()
        self.assertFalse(self.subscription.is_active)

    def test_subscription_updated_syncs_auto_renew(self):
        post_event("customer.subscription.updated", {"id": "sub_1", "cancel_at_period_end": True})
        self.subscription.refresh_from_db()
        self.assertFalse(self.subscription.auto_renew)

    def test_invoice_paid_renews_with_new_api_format(self):
        now = int(time.time())
        stripe_sub = {"items": {"data": [{
            "current_period_start": now, "current_period_end": now + 30 * 86400, "price": {"id": "price_1"},
        }]}}
        with mock.patch("payment.views.stripe.Subscription.retrieve", return_value=stripe_sub):
            response = post_event("invoice.paid", {
                "id": "in_1", "object": "invoice", "parent": {"subscription_details": {"subscription": "sub_1"}},
            })
        self.assertEqual(response.status_code, 200)
        self.subscription.refresh_from_db()
        self.assertGreater(self.subscription.end_date, timezone.now() + timedelta(days=29))

    def test_invoice_for_unknown_subscription_is_acknowledged(self):
        response = post_event("invoice.paid", {"id": "in_2", "object": "invoice", "subscription": "sub_x"})
        self.assertEqual(response.status_code, 200)


class CheckoutAndSubscriptionTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(email="p@test.com", password="x")
        self.plan = SubscriptionPlan.objects.create(name="Monthly", amount=10, price_id="price_1")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_checkout_copies_metadata_to_subscription(self):
        with mock.patch("payment.views.stripe.checkout.Session.create") as create:
            create.return_value = mock.Mock(url="https://checkout")
            response = self.client.post("/api/payment/create-checkout-session/", {"price_id": "price_1"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(create.call_args.kwargs["subscription_data"]["metadata"]["user_id"], str(self.user.id))

    def test_checkout_rejects_unknown_price(self):
        response = self.client.post("/api/payment/create-checkout-session/", {"price_id": "price_x"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_cancel_and_resume(self):
        Subscription.objects.create(
            user=self.user, plan=self.plan, stripe_subscription_id="sub_1", is_active=True, auto_renew=True,
        )
        with mock.patch("payment.views.stripe.Subscription.modify") as modify:
            response = self.client.post("/api/payment/subscription/cancel/")
            self.assertEqual(response.status_code, 200)
            modify.assert_called_with("sub_1", cancel_at_period_end=True)
            self.assertFalse(response.data["subscription"]["auto_renew"])

            response = self.client.post("/api/payment/subscription/resume/")
            modify.assert_called_with("sub_1", cancel_at_period_end=False)
            self.assertTrue(response.data["subscription"]["auto_renew"])

        response = self.client.get("/api/payment/subscription/")
        self.assertEqual(response.data["subscription"]["plan_name"], "Monthly")

    def test_cancel_without_subscription_returns_404(self):
        self.assertEqual(self.client.post("/api/payment/subscription/cancel/").status_code, 404)

    def test_no_subscription_is_not_an_error(self):
        response = self.client.get("/api/payment/subscription/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["subscription"])
