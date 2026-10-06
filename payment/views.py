from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django.conf import settings
from django.http import HttpResponse
from datetime import datetime, timezone as dt_timezone
import logging
import os

import stripe

from .models import Subscription, SubscriptionPlan
from authentications.models import CustomUser
from .serializers import *

logger = logging.getLogger(__name__)

# Set your Stripe secret key
stripe.api_key = os.getenv("STRIPE_API_KEY")

# Webhook secret (get this from your Stripe Dashboard)
endpoint_secret = os.getenv("ENDPOINT_SECRET")


def _to_datetime(timestamp):
    return datetime.fromtimestamp(timestamp, tz=dt_timezone.utc)


def _invoice_subscription_id(invoice):
    # Older API versions: invoice.subscription; 2025-03-31.basil and later:
    # invoice.parent.subscription_details.subscription
    subscription_id = invoice.get("subscription")
    if not subscription_id:
        parent = invoice.get("parent") or {}
        subscription_id = (parent.get("subscription_details") or {}).get("subscription")
    return subscription_id


def _deactivate_subscription(stripe_subscription_id):
    if stripe_subscription_id:
        Subscription.objects.filter(stripe_subscription_id=stripe_subscription_id).update(is_active=False)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_checkout_session(request):
    # Get the data from the frontend
    price_id = request.data.get("price_id")  # Stripe price ID

    if not price_id:
        return Response({"error": "Missing price_id"}, status=400)

    # Only allow prices that belong to one of our plans
    if not SubscriptionPlan.objects.filter(price_id=price_id).exists():
        return Response({"error": "Invalid price_id"}, status=400)

    user = request.user
    metadata = {
        "user_id": str(user.id),  # Include the user ID for tracking
        "custom_note": "Tracking payment for subscription",
    }

    try:
        # Create the Stripe Checkout session
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=f"{settings.FRONTEND_URL}/payment/success",
            cancel_url=f"{settings.FRONTEND_URL}/payment/cancel",
            customer_email=user.email,
            metadata=metadata,
            # Copy metadata onto the subscription so renewal/cancel events can find the user
            subscription_data={"metadata": metadata},
        )

        return Response({"checkout_url": session.url}, status=200)

    except stripe.error.StripeError:
        logger.exception("Failed to create checkout session for user %s", user.id)
        return Response({"error": "Could not create checkout session"}, status=400)


@api_view(["POST"])
@permission_classes([AllowAny])
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        logger.warning("Error verifying webhook signature: %s", e)
        return Response({"error": "Webhook signature failed"}, status=400)

    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        metadata = obj.get("metadata") or {}
        user_id = metadata.get("user_id")
        stripe_subscription_id = obj.get("subscription")

        if not user_id or not stripe_subscription_id:
            logger.warning("Missing user_id or subscription_id in checkout session %s", obj.get("id"))
            return Response({"error": "Missing user_id or subscription_id"}, status=400)

        try:
            user = CustomUser.objects.get(id=user_id)
            stripe_subscription = stripe.Subscription.retrieve(stripe_subscription_id)
            subscription_item = stripe_subscription["items"]["data"][0]

            current_period_start = subscription_item.get("current_period_start")
            current_period_end = subscription_item.get("current_period_end")

            if not current_period_start or not current_period_end:
                logger.warning("Missing subscription period data for %s", stripe_subscription_id)
                return Response({"error": "Missing subscription period information from Stripe"}, status=400)

            plan_id = subscription_item["price"]["id"]
            subscription_plan = SubscriptionPlan.objects.get(price_id=plan_id)

            Subscription.objects.update_or_create(
                user=user,
                defaults={
                    "plan": subscription_plan,
                    "start_date": _to_datetime(current_period_start),
                    "end_date": _to_datetime(current_period_end),
                    "is_active": True,
                    "price": subscription_plan.amount,
                    "status": "premium",
                    "stripe_subscription_id": stripe_subscription_id,
                    "auto_renew": not stripe_subscription.get("cancel_at_period_end", False),
                },
            )
        except Exception:
            logger.exception("Error processing subscription for user %s", user_id)
            return Response({"error": "Error processing subscription"}, status=400)

    elif event_type == "invoice.payment_failed":
        _deactivate_subscription(_invoice_subscription_id(obj))

    elif event_type == "customer.subscription.deleted":
        _deactivate_subscription(obj.get("id"))

    elif event_type == "customer.subscription.updated":
        # Keep auto-renew in sync when the subscription is cancelled/resumed in Stripe
        Subscription.objects.filter(stripe_subscription_id=obj.get("id")).update(
            auto_renew=not obj.get("cancel_at_period_end", False)
        )

    elif event_type == "invoice.paid":
        subscription_id = _invoice_subscription_id(obj)
        if not subscription_id:
            return Response({"status": "ignored"}, status=200)

        subscription = Subscription.objects.filter(stripe_subscription_id=subscription_id).first()
        if not subscription:
            # First invoice of a new subscription - handled by checkout.session.completed
            return Response({"status": "ignored"}, status=200)

        try:
            stripe_subscription = stripe.Subscription.retrieve(subscription_id)
            subscription_item = stripe_subscription["items"]["data"][0]

            plan_id = subscription_item["price"]["id"]
            subscription_plan = SubscriptionPlan.objects.get(price_id=plan_id)

            # Update subscription for renewal
            subscription.start_date = _to_datetime(subscription_item["current_period_start"])
            subscription.end_date = _to_datetime(subscription_item["current_period_end"])
            subscription.plan = subscription_plan
            subscription.price = subscription_plan.amount
            subscription.status = "premium"
            subscription.is_active = True
            subscription.save()

            logger.info("Subscription renewed for user %s", subscription.user_id)

        except Exception:
            logger.exception("Error processing renewal for subscription %s", subscription_id)
            return Response({"error": "Error processing renewal"}, status=400)

    return Response({"status": "success"}, status=200)


def checkout_success(request):
    return HttpResponse("Your checkout was successful!", status=200)


def checkout_cencel(request):
    return HttpResponse("Your checkout was cancelled.", status=200)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_subscription(request):
    """
    Retrieve the subscription details for the authenticated user.
    """
    user = request.user
    try:
        # Retrieve subscription for the current user
        subscription = Subscription.objects.get(user=user)
        serializer = SubscriptionSerializer(subscription)
        return Response({"subscription": serializer.data}, status=200)
    except Subscription.DoesNotExist:
        # Not being subscribed is a normal state, not an error
        return Response({"subscription": None}, status=200)


def _set_cancel_at_period_end(user, cancel):
    subscription = Subscription.objects.filter(user=user, is_active=True).first()
    if not subscription or not subscription.stripe_subscription_id:
        return Response({"message": "You don't have an active subscription."}, status=404)

    try:
        stripe.Subscription.modify(subscription.stripe_subscription_id, cancel_at_period_end=cancel)
    except stripe.error.StripeError:
        logger.exception("Failed to update subscription %s", subscription.stripe_subscription_id)
        return Response({"message": "Could not update your subscription. Please try again."}, status=502)

    subscription.auto_renew = not cancel
    subscription.save(update_fields=["auto_renew", "updated_at"])
    return Response({"subscription": SubscriptionSerializer(subscription).data}, status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_subscription(request):
    """Stop auto-renewal; access continues until the end of the paid period."""
    return _set_cancel_at_period_end(request.user, True)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resume_subscription(request):
    """Undo a cancellation before the period ends."""
    return _set_cancel_at_period_end(request.user, False)



@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_all_subscription(request):
    subscriptions = Subscription.objects.select_related('user').all()
    serializer = SubscriptionSerializer(subscriptions, many=True)
    return Response({"subscriptions": serializer.data}, status=200)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_all_plan(request):
    plans = SubscriptionPlan.objects.all()
    serializer = SubscriptionPlanSerializer(plans, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_subscription_invoices(request):
    user = request.user

    try:
        subscription = Subscription.objects.get(user=user)
        stripe_subscription_id = subscription.stripe_subscription_id
        if not stripe_subscription_id:
            return Response({"invoices": []}, status=200)

        period_end = subscription.end_date.strftime('%m/%d/%Y') if subscription.end_date else None

        invoices = stripe.Invoice.list(subscription=stripe_subscription_id)

        invoice_data = []
        for inv in invoices.auto_paging_iter():
            invoice_data.append({
                "plan": subscription.plan.name if subscription.plan else None,
                "issue_date": _to_datetime(inv.created).strftime('%m/%d/%Y'),
                "expire_date": period_end,
                "amount": f"${inv.amount_paid / 100:.2f}",
                "invoice_pdf": inv.invoice_pdf
            })

        return Response({"invoices": invoice_data}, status=200)

    except Subscription.DoesNotExist:
        # Return empty invoices list instead of 404
        return Response({"invoices": []}, status=200)
    except Exception:
        logger.exception("Failed to load invoices for user %s", user.id)
        return Response({"error": "Could not load invoices"}, status=500)





# @background(schedule=60)  # Check every 60 seconds (adjust as needed)
# def check_subscription_status():
#     """
#     Automatically check and deactivate expired free trials or subscriptions.
#     """
#     now = datetime.now()

#     # Check for expired free trials
#     free_trial_expired = Subscription.objects.filter(
#         free_trial=True, free_trial_end__lte=now
#     )
#     for subscription in free_trial_expired:
#         subscription.free_trial = False
#         subscription.save()
#         print(f"Free trial expired for user {subscription.user.username}")

#     # Check for expired subscriptions
#     subscription_expired = Subscription.objects.filter(
#         is_active=True, end_date__lte=now
#     )
#     for subscription in subscription_expired:
#         subscription.is_active = False
#         subscription.save()
#         print(f"Subscription expired for user {subscription.user.username}")

#     print("Checked free trial and subscription statuses.")
    
    

# @api_view(['GET'])

# def get_all_subscription(request):
   
#     # Get or create the user's subscription object
#     subscription = Subscription.objects.all()
#     # Check if the user already has a Stripe customer ID
#     subscription_serializer = SubscriptionSerializer(subscription, many=True)

#     return Response(subscription_serializer.data, status=200)







