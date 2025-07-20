from rest_framework.response import Response

def error_response(code, message=None, details=None):
    """
    Generate a standardized error response with a user-friendly message.
    Args:
        code (int): HTTP status code (e.g., 400, 401).
        message (str, optional): User-friendly error message. If None, derived from details.
        details (dict or list, optional): Detailed errors for debugging.
    Returns:
        Response: Standardized error response.
    """
    # Derive message from details if not provided
    if not message and details:
        if isinstance(details, dict):
            # Extract missing fields
            missing_fields = [
                key for key, value in details.items()
                if isinstance(value, list) and any("This field is required" in str(v) for v in value)
            ]
            if missing_fields:
                message = f"{', '.join(key.title() for key in missing_fields)} {'are' if len(missing_fields) > 1 else 'is'} required"
            else:
                # Extract first error message from details
                for key, value in details.items():
                    if isinstance(value, list) and value:
                        message = str(value[0])
                        break
        elif isinstance(details, list) and details:
            message = str(details[0])

    # Fallback message
    message = message or "An error occurred"

    return Response({
        "code": code,
        "error": message,
        "details": details if details else {}
    }, status=code)