from django.shortcuts import render
from django.contrib.auth.hashers import make_password
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import OTP, UserProfile , CustomUser
from .serializers import (
    CustomUserSerializer,
    CustomUserCreateSerializer,
    UserProfileSerializer,
    OTPSerializer,
    LoginSerializer
)
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
import uuid
import secrets
import logging
import requests as http_requests
from django.conf import settings
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from sara_main.utils import error_response
from sara_main.authentication import set_auth_cookies, set_access_cookie, clear_auth_cookies

logger = logging.getLogger(__name__)

MAX_OTP_ATTEMPTS = 5


def generate_otp():
    return f"{secrets.randbelow(1_000_000):06d}"


def check_otp(otp_obj, otp_value):
    """Validate an OTP, counting failed attempts. Returns an error Response or None."""
    if otp_obj.attempts >= MAX_OTP_ATTEMPTS:
        otp_obj.delete()
        return error_response(
            code=429,
            details={"otp": ["Too many failed attempts. Please request a new OTP"]}
        )
    if not secrets.compare_digest(otp_obj.otp, str(otp_value)):
        otp_obj.attempts += 1
        otp_obj.save(update_fields=["attempts"])
        return error_response(
            code=400,
            details={"otp": ["The provided OTP is invalid"]}
        )
    if otp_obj.is_expired():
        return error_response(
            code=400,
            details={"otp": ["The OTP has expired"]}
        )
    return None

User = get_user_model()

def verify_google_access_token(access_token):
    """
    Verify a Google OAuth access token (from the frontend's useGoogleLogin) and
    return the user's info, or None if the token is invalid or was issued to
    another app.
    """
    try:
        token_info = http_requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"access_token": access_token},
            timeout=10,
        )
        if token_info.status_code != 200:
            return None
        # The token must have been issued to one of our OAuth clients
        if token_info.json().get("aud") not in settings.GOOGLE_CLIENT_IDS:
            return None

        user_info = http_requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if user_info.status_code != 200:
            return None
        return user_info.json()
    except http_requests.RequestException:
        logger.exception("Failed to verify Google access token")
        return None


def send_otp_email(email, otp):
    html_content = render_to_string('otp_email_template.html', {'otp': otp, 'email': email})
    msg = EmailMultiAlternatives(
        subject='Your OTP Code',
        body=f'Your OTP is {otp}',
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email]
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=False)



@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    serializer = CustomUserCreateSerializer(data=request.data)
    if serializer.is_valid():
        if serializer.validated_data.get('role') == 'admin':
            return error_response(
                code=403,
                message="Admin role cannot be assigned during registration",
                details={"role": ["Admin role is restricted"]}
            )
        user = serializer.save()
        otp = generate_otp()
        otp_data = {'email': user.email, 'otp': otp}
        otp_serializer = OTPSerializer(data=otp_data)
        if otp_serializer.is_valid():
            otp_serializer.save()
            try:
                send_otp_email(email=user.email, otp=otp)
            except Exception:
                logger.exception("Failed to send OTP email to %s", user.email)
                return error_response(code=500, message="Failed to send OTP email")
        return Response({
            "message": "User registered. Please verify your email with the OTP sent",
            "user_id": user.id,
            "email": user.email,
        }, status=status.HTTP_201_CREATED)
    return error_response(code=400, details=serializer.errors)



@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data

        # Unverified accounts get a fresh OTP instead of tokens
        if not user.is_verified:
            otp = generate_otp()
            OTP(email=user.email, otp=otp).save()
            try:
                send_otp_email(email=user.email, otp=otp)
            except Exception:
                logger.exception("Failed to send OTP email to %s", user.email)
                return error_response(code=500, message="Failed to send OTP email")
            return Response({
                "code": 403,
                "message": "Please verify your email. We have sent a new OTP to your inbox.",
                "details": {"email": ["Email is not verified"]},
                "user_id": user.id,
                "is_verified": False,
            }, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)

        is_verified = user.is_verified
        try:
            profile = user.user_profile
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=user, first_name=user.email.split('@')[0])
        profile_serializer = UserProfileSerializer(profile)
        response = Response({
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "email_address": user.email,
            "role": user.role,
            "is_verified" : is_verified,
            "profile": profile_serializer.data,
            "access_token_valid_till": int(refresh.access_token.lifetime.total_seconds()*1000),
        }, status=status.HTTP_200_OK)
        return set_auth_cookies(response, refresh)
    return error_response(code=401, details=serializer.errors)



@api_view(['POST'])
@permission_classes([AllowAny])
def google_login(request):
    id_token = request.data.get("id_token")
    access_token = request.data.get("access_token")
    if not id_token and not access_token:
        return error_response(code=400, details={"access_token": ["This field is required"]})

    if not settings.GOOGLE_CLIENT_IDS:
        logger.error("GOOGLE_CLIENT_IDS is not configured")
        return error_response(code=500, message="Google login is not configured")

    # Verify the token with Google instead of trusting client-supplied data
    if id_token:
        try:
            id_info = google_id_token.verify_oauth2_token(
                id_token, google_requests.Request(), audience=settings.GOOGLE_CLIENT_IDS
            )
        except ValueError:
            return error_response(code=401, details={"id_token": ["Invalid Google token"]})
    else:
        id_info = verify_google_access_token(access_token)
        if id_info is None:
            return error_response(code=401, details={"access_token": ["Invalid Google token"]})

    email = id_info.get("email")
    if not email or str(id_info.get("email_verified")).lower() != "true":
        return error_response(code=401, details={"email": ["Google account email is not verified"]})

    name = id_info.get("name", "")
    picture = id_info.get("picture", "")

    # Split full name into first and last
    first_name, *rest = name.split(" ")
    last_name = " ".join(rest) if rest else ""

    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "is_verified": True,
            "role": "user",
        }
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    elif not user.is_verified:
        # Google has verified this email address
        user.is_verified = True
        user.save(update_fields=["is_verified"])

    # Always get or create profile to avoid "profile not defined" error
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "google_profile_picture": picture,
        }
    )

    # Update profile if needed (e.g. if picture or name changed from Google)
    if not created:
        updated = False
        if not profile.first_name and first_name:
            profile.first_name = first_name
            updated = True
        if not profile.last_name and last_name:
            profile.last_name = last_name
            updated = True
        if picture and profile.google_profile_picture != picture:
            profile.google_profile_picture = picture
            updated = True
        if updated:
            profile.save()

    profile_serializer = UserProfileSerializer(profile)
    refresh = RefreshToken.for_user(user)

    response = Response({
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
        "email_address": user.email,
        "role": user.role,
        "is_verified": user.is_verified,
        "profile": profile_serializer.data,
        "access_token_valid_till": int(refresh.access_token.lifetime.total_seconds() * 1000),
    })
    return set_auth_cookies(response, refresh)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_users(request):
    users = User.objects.all()
    serializer = CustomUserSerializer(users, many=True)
    return Response(serializer.data)



@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    try:
        profile = request.user.user_profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user, first_name=request.user.email.split('@')[0])

    if request.method == 'GET':
        user = CustomUser.objects.get(id=request.user.id)
        serializer = CustomUserSerializer(user)
        return Response(serializer.data)

    if request.method == 'PUT':
        serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return error_response(code=400, details=serializer.errors)




@api_view(['POST'])
@permission_classes([AllowAny])
def create_otp(request):
    user_id = request.data.get('user_id')
    if not user_id:
        return error_response(
            code=400,
            details={"user_id": ["This field is required"]}
        )
    user = User.objects.filter(id=user_id).first()
    if not user:
        return error_response(
            code=404,
            details={"user_id": ["User does not exist."]}
        )
    email = user.email

    try:
        user = User.objects.get(email=email)
        if user.is_verified:
            return error_response(
                code=400,
                details={"email": ["This account is already verified"]}
            )
    except User.DoesNotExist:
        return error_response(
            code=404,
            details={"email": ["No user exists with this email"]}
        )

    otp = generate_otp()
    otp_data = {'email': email, 'otp': otp}
    OTP.objects.filter(email=email).delete()
    serializer = OTPSerializer(data=otp_data)
    if serializer.is_valid():
        serializer.save()
        try:
            send_otp_email(email=email, otp=otp)
        except Exception:
            logger.exception("Failed to send OTP email to %s", email)
            return error_response(code=500, message="Failed to send OTP email")
        return Response({"message": "OTP sent to your email"}, status=status.HTTP_201_CREATED)
    return error_response(code=400, details=serializer.errors)

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp_reset(request):
    user_id = request.data.get('user_id')
    otp_value = request.data.get('otp')
    user = User.objects.filter(id=user_id).first()
    if not user:
        return error_response(
            code=400,
            details={"user_id": ["User does not exist."]}
        )

    # Now it's safe to use user.email
    email = user.email

    if not email or not otp_value:
        details = {}
        if not email:
            details["user id"] = ["This field is required"]
        if not otp_value:
            details["otp"] = ["This field is required"]
        return error_response(code=400, details=details)

    try:
        otp_obj = OTP.objects.get(email=email)
        otp_error = check_otp(otp_obj, otp_value)
        if otp_error:
            return otp_error

        secret_key = str(uuid.uuid4())
        otp_obj.secret_key = secret_key
        otp_obj.save()
        return Response({"message": "OTP verified successfully","secret_key" : secret_key, "user_id" : user_id}, status=status.HTTP_200_OK)
    except OTP.DoesNotExist:
        return error_response(
            code=404,
            details={"email": ["No OTP found for this email"]})


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp(request):
    user_id = request.data.get('user_id')
    otp_value = request.data.get('otp')

    if not user_id or not otp_value:
        details = {}
        if not user_id:
            details["user_id"] = ["This field is required"]
        if not otp_value:
            details["otp"] = ["This field is required"]
        return error_response(code=400, details=details)

    user = User.objects.filter(id=user_id).first()
    if not user:
        return error_response(
            code=404,
            details={"user_id": ["User does not exist."]}
        )

    try:
        otp_obj = OTP.objects.get(email=user.email)
        otp_error = check_otp(otp_obj, otp_value)
        if otp_error:
            return otp_error

        # Verify the user
        try:
            user = User.objects.get(email=user.email)
            if user.is_verified:
                return error_response(
                    code=400,
                    details={"email": ["This account is already verified"]}
                )
            user.is_verified = True
            user.is_active = True  # Activate user after verification
            user.save()
            otp_obj.delete()

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            # Ensure UserProfile exists
            try:
                profile = user.user_profile
            except UserProfile.DoesNotExist:
                profile = UserProfile.objects.create(user=user, first_name=user.email.split('@')[0])

            profile_serializer = UserProfileSerializer(profile)
            response = Response({
                "message": "Email verified successfully",
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "email_address": user.email,
                "role": user.role,
                "is_verified": user.is_verified,
                "profile": profile_serializer.data
            }, status=status.HTTP_200_OK)
            return set_auth_cookies(response, refresh)
        except User.DoesNotExist:
            return error_response(
                code=404,
                details={"email": ["No user exists with this email"]}
            )
    except OTP.DoesNotExist:
        return error_response(
            code=404,
            details={"email": ["No OTP found for this email"]}
        )

@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    email = request.data.get('email')
    if not email:
        return error_response(
            code=400,
            details={"email": ["This field is required"]}
        )

    try:
        user = User.objects.get(email=email)
        if not user.is_verified:
            return error_response(
                code=400,
                details={"email": ["Please verify your email before resetting your password"]}
            )
    except User.DoesNotExist:
        return error_response(
            code=404,
            details={"email": ["No user exists with this email"]}
        )

    otp = generate_otp()
    otp_data = {'email': email, 'otp': otp}
    OTP.objects.filter(email=email).delete()
    serializer = OTPSerializer(data=otp_data)
    user_id = User.objects.get(email=email).id
    if serializer.is_valid():
        serializer.save()
        try:
            send_otp_email(email=email, otp=otp)
        except Exception:
            logger.exception("Failed to send OTP email to %s", email)
            return error_response(code=500, message="Failed to send OTP email")
        return Response({"message": "OTP sent to your email","user_id":user_id }, status=status.HTTP_201_CREATED)
    return error_response(code=400, details=serializer.errors)

@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    user_id = request.data.get('user_id')
    secret_key = request.data.get('secret_key')

    user = User.objects.filter(id=user_id).first()
    if not user:
        return error_response(
            code=400,
            details={"user_id": ["User does not exist."]}
        )

    # Now it's safe to use user.email
    email = user.email
    new_password = request.data.get('new_password')

    if not all([email, new_password , secret_key]):
        details = {}
        if not email:
            details["user id"] = ["This field is required"]
        if not secret_key:
            details["secret_key"] = ["This field is required"]
        if not new_password:
            details["new_password"] = ["This field is required"]
        return error_response(code=400, details=details)

    try:
        otp_obj = OTP.objects.get(email=email)
        if not otp_obj.secret_key or not secrets.compare_digest(otp_obj.secret_key, str(secret_key)):
            return error_response(
                code=400,
                details={"secret_key": ["The provided secret key is invalid"]}
            )


        user = User.objects.get(email=email)
        if not user.is_verified:
            return error_response(
                code=400,
                details={"user": ["Please verify your email before resetting your password"]}
            )
        try:
            validate_password(new_password, user)
        except ValidationError as e:
            return error_response(
                code=400,
                details={"new_password": e.messages}
            )

        user.set_password(new_password)
        user.save()
        otp_obj.delete()
        return Response({'message': 'Password reset successful'})
    except OTP.DoesNotExist:
        return error_response(
            code=404,
            details={"email": ["No OTP found for this email"]}
        )
    except User.DoesNotExist:
        return error_response(
            code=404,
            details={"email": ["No user exists with this email"]}
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')

    if not current_password or not new_password:
        details = {}
        if not current_password:
            details["current_password"] = ["This field is required"]
        if not new_password:
            details["new_password"] = ["This field is required"]
        return error_response(code=400, details=details)

    user = request.user
    if not user.has_usable_password():
        return error_response(
            code=400,
            details={"current_password": ["This account signs in with Google and has no password"]}
        )
    if not user.check_password(current_password):
        return error_response(
            code=400,
            details={"current_password": ["The current password is incorrect"]}
        )

    try:
        validate_password(new_password, user)
    except ValidationError as e:
        return error_response(
            code=400,
            details={"new_password": e.messages}
        )

    user.set_password(new_password)
    user.save()
    return Response({'message': 'Password changed successfully'}, status=status.HTTP_200_OK)





@api_view(['POST'])
@permission_classes([AllowAny])
def get_access_token_by_refresh_token(request):
    # Mobile clients send the token in the body; the web app uses the httpOnly cookie
    refresh_token = request.data.get('refresh_token') or request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
    if not refresh_token:
        return error_response(
            code=401,
            details={"refresh_token": ["This field is required"]}
        )
    try:
        refresh = RefreshToken(refresh_token)
        access_token = refresh.access_token
    except Exception:
        return clear_auth_cookies(error_response(
            code=401,
            details={"refresh_token": ["Invalid or expired refresh token"]}
        ))
    response = Response({"access_token": str(access_token)}, status=status.HTTP_200_OK)
    return set_access_cookie(response, access_token)


@api_view(['POST'])
@permission_classes([AllowAny])
def logout(request):
    """Clear the httpOnly auth cookies."""
    return clear_auth_cookies(Response({"message": "Logged out"}, status=status.HTTP_200_OK))
