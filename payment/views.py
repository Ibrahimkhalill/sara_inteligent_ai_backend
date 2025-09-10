from django.shortcuts import render
from rest_framework import status

# Create your views here.
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import authentication_classes, permission_classes
# Create your views here.
import stripe
from rest_framework.response import Response
from django.http import JsonResponse , HttpResponse
from collections import defaultdict
from datetime import datetime
from .models import Subscription , SubscriptionPlan
from authentications.models import  CustomUser
from .serializers import *
import os
from dotenv import load_dotenv
load_dotenv()
# Set your Stripe secret key
stripe.api_key = os.getenv("STRIPE_API_KEY")

# Webhook secret (get this from your Stripe Dashboard)
endpoint_secret =os.getenv("ENDPOINT_SECRET")

print("endpoint_secret",endpoint_secret)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_checkout_session(request):
    # DOMAIN = "https://lamprey-included-lion.ngrok-free.app/api/payment"  # Replace with your actual domain

    # Get the data from the frontend
    price_id = request.data.get("price_id")  # Stripe price ID
  

    if not price_id:
        return Response({"error": "Missing price_id"}, status=400)

    user = request.user

    try:
        # Create the Stripe Checkout session
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,  # Use dynamic price_id from frontend
                    "quantity": 1,
                }
            ],
            mode="subscription",
                success_url=f"http://127.0.0.1:3901/payment/success",
                cancel_url=f"http://127.0.0.1:3901/payment/cancel",
            metadata={  # Attach metadata to the session
                "user_id": str(user.id),  # Include the user ID for tracking
                "custom_note": "Tracking payment for subscription",
            },
        )

        return Response({"checkout_url": session.url}, status=200)

    except Exception as e:
        return Response({"error": str(e)}, status=400)

    
    

@api_view(["POST"])
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        # Increase tolerance for testing (e.g., 30 days in seconds)
        tolerance = 30 * 24 * 60 * 60  # 30 days
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret, tolerance=tolerance)
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        print(f"Error verifying webhook signature: {str(e)}")
        return Response({"error": "Webhook signature failed"}, status=400)

    # Rest of your webhook logic remains unchanged
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        print(f"Session completed: {session}")
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        stripe_subscription_id = session.get("subscription")

        if not user_id or not stripe_subscription_id:
            print(f"Missing user_id or subscription_id in metadata: {metadata}")
            return Response({"error": "Missing user_id or subscription_id"}, status=400)

        try:
            user = get_object_or_404(CustomUser, id=user_id)
            stripe_subscription = stripe.Subscription.retrieve(stripe_subscription_id)
            subscription_item = stripe_subscription["items"]["data"][0]
 
            current_period_start = subscription_item.get("current_period_start")
            current_period_end = subscription_item.get("current_period_end")

            if not current_period_start or not current_period_end:
                print(f"Missing subscription period data: {stripe_subscription}")
                return Response({"error": "Missing subscription period information from Stripe"}, status=400)

            current_period_start = datetime.fromtimestamp(current_period_start)
            current_period_end = datetime.fromtimestamp(current_period_end)
            print(f"current_period_start: {current_period_start}, current_period_end: {current_period_end}")

            plan_id = subscription_item["price"]["id"]
            subscription_plan = get_object_or_404(SubscriptionPlan, price_id=plan_id)

            try:
                subscription = Subscription.objects.get(user=user)
                subscription.start_date = current_period_start
                subscription.end_date = current_period_end
                subscription.is_active = True
                subscription.plan = subscription_plan
                subscription.price = subscription_plan.amount
                subscription.status = "premium"
                subscription.stripe_subscription_id = stripe_subscription_id
                subscription.save()
            except Subscription.DoesNotExist:
                Subscription.objects.create(
                    user=user,
                    plan=subscription_plan,
                    start_date=current_period_start,
                    end_date=current_period_end,
                    is_active=True,
                    price=subscription_plan.amount,
                    status="premium",
                    stripe_subscription_id=stripe_subscription_id
                )
        except Exception as e:
            print(f"Error processing subscription for user {user_id}: {str(e)}")
            return Response({"error": "Error processing subscription"}, status=400)

    elif event["type"] == "invoice.payment_failed" or event["type"] == "customer.subscription.deleted":
        session = event["data"]["object"]
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")

        if user_id:
            try:
                user = get_object_or_404(CustomUser, id=user_id)
                subscription = Subscription.objects.get(user=user)
                subscription.is_active = False
                subscription.save()
            except Subscription.DoesNotExist:
                pass
    elif event["type"] == "invoice.paid":
        invoice = event["data"]["object"]
        subscription_id = invoice.get("subscription")

        try:
            stripe_subscription = stripe.Subscription.retrieve(subscription_id)
            user_id = stripe_subscription.get("metadata", {}).get("user_id")

            if not user_id:
                print(f"Missing user_id in metadata for renewal: {stripe_subscription}")
                return Response({"error": "Missing user_id for renewal"}, status=400)

            user = get_object_or_404(CustomUser, id=user_id)

            subscription_item = stripe_subscription["items"]["data"][0]
            current_period_start = datetime.fromtimestamp(subscription_item["current_period_start"])
            current_period_end = datetime.fromtimestamp(subscription_item["current_period_end"])

            plan_id = subscription_item["price"]["id"]
            subscription_plan = get_object_or_404(SubscriptionPlan, price_id=plan_id)

            # Update subscription for renewal
            subscription = Subscription.objects.get(user=user)
            subscription.start_date = current_period_start
            subscription.end_date = current_period_end
            subscription.plan = subscription_plan
            subscription.price = subscription_plan.amount
            subscription.status = "premium"
            subscription.is_active = True
            subscription.save()

            print(f"Subscription renewed for user {user.email}")

        except Exception as e:
            print(f"Error processing renewal for subscription {subscription_id}: {str(e)}")
            return Response({"error": "Error processing renewal"}, status=400)

    return Response({"status": "success"}, status=200)


def checkout_success(request):
    return HttpResponse("Your checkout was successful!", status=200)


def checkout_cencel(request):
    return HttpResponse("Your checkout was successful!", status=200)



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
        return Response({"message": "No subscription found for this user."}, status=404)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_subscription(request):
    subscriptions = Subscription.objects.select_related('user').all()
    serializer = SubscriptionSerializer(subscriptions, many=True)
    return Response({"subscriptions": serializer.data}, status=200)


@api_view(['GET'])
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

        period_end = subscription.end_date.strftime('%m/%d/%Y') if subscription.end_date else None

        invoices = stripe.Invoice.list(subscription=stripe_subscription_id)
        print("invoices",len(invoices))

        invoice_data = []
        for inv in invoices.auto_paging_iter():
            invoice_data.append({
                "plan": subscription.plan.name,
                "issue_date": datetime.fromtimestamp(inv.created).strftime('%m/%d/%Y'),
                "expire_date": period_end,
                "amount": f"${inv.amount_paid / 100:.2f}",
                "invoice_pdf": inv.invoice_pdf
            })

        return Response({"invoices": invoice_data}, status=200)

    except Subscription.DoesNotExist:
        # Return empty invoices list instead of 404
        return Response({"invoices": []}, status=200)
    except Exception as e:
        print("Error:", str(e))
        return Response({"error": str(e)}, status=500)





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







