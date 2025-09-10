# notification/send_fcm_notification.py
from .firebase_init import *  # MUST be imported first
from firebase_admin import messaging

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
        print("Successfully sent message:", response)
        return {"success": True, "response": response}
    except Exception as e:
        print("Error sending message:", e)
        return {"success": False, "error": str(e)}
