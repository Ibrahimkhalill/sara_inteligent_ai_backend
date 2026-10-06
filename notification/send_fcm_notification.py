# notification/send_fcm_notification.py
import logging

from .firebase_init import *  # MUST be imported first
from firebase_admin import messaging

logger = logging.getLogger(__name__)


def send_fcm_notification(token, title, body):
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        token=token
    )
    try:
        response = messaging.send(message)
        return {"success": True, "response": response}
    except messaging.UnregisteredError as e:
        return {"success": False, "unregistered": True, "error": str(e)}
    except Exception as e:
        logger.warning("Error sending FCM message: %s", e)
        return {"success": False, "error": str(e)}
