from django.conf import settings
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


class CookieJWTAuthentication(JWTAuthentication):
    """
    JWT auth from the `Authorization: Bearer` header (mobile/API clients) or,
    for the web app, from an httpOnly cookie that JavaScript cannot read.
    """

    def authenticate(self, request):
        if self.get_header(request) is not None:
            return super().authenticate(request)

        raw_token = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS)
        if not raw_token:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
        except (InvalidToken, TokenError):
            # Expired/invalid cookie: treat as anonymous so public endpoints
            # (sign in, refresh) still work; protected ones return 401.
            return None

        # Cookies are sent automatically, so unsafe requests must also carry a
        # custom header. Browsers only allow that cross-origin after a CORS
        # preflight, which is restricted to CORS_ALLOWED_ORIGINS (CSRF defence).
        if request.method not in SAFE_METHODS and request.headers.get("X-Requested-With") != "XMLHttpRequest":
            raise exceptions.PermissionDenied("CSRF check failed: missing X-Requested-With header.")

        return self.get_user(validated_token), validated_token


def set_auth_cookies(response, refresh):
    """Attach access/refresh tokens to the response as httpOnly cookies."""
    common = {
        "httponly": True,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "domain": settings.AUTH_COOKIE_DOMAIN,
    }
    response.set_cookie(
        settings.AUTH_COOKIE_ACCESS,
        str(refresh.access_token),
        max_age=int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        path="/",
        **common,
    )
    response.set_cookie(
        settings.AUTH_COOKIE_REFRESH,
        str(refresh),
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=settings.AUTH_COOKIE_REFRESH_PATH,  # only sent to refresh/logout
        **common,
    )
    return response


def set_access_cookie(response, access_token):
    response.set_cookie(
        settings.AUTH_COOKIE_ACCESS,
        str(access_token),
        max_age=int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        path="/",
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        domain=settings.AUTH_COOKIE_DOMAIN,
    )
    return response


def clear_auth_cookies(response):
    response.delete_cookie(
        settings.AUTH_COOKIE_ACCESS, path="/", domain=settings.AUTH_COOKIE_DOMAIN,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    response.delete_cookie(
        settings.AUTH_COOKIE_REFRESH, path=settings.AUTH_COOKIE_REFRESH_PATH,
        domain=settings.AUTH_COOKIE_DOMAIN, samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    return response
