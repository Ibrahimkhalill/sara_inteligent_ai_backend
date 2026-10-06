# notifications/jobs.py
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from django.utils import timezone
from .models import Notification, FCMToken
from .send_fcm_notification import send_fcm_notification

logger = logging.getLogger(__name__)

_scheduler = None


def send_due_notifications():
    now = timezone.now()
    due_notifications = Notification.objects.filter(sent=False, notify_at__lte=now).select_related("user")

    for notification in due_notifications:
        # Claim the notification atomically so it is never sent twice, even if
        # more than one process runs this job
        claimed = Notification.objects.filter(pk=notification.pk, sent=False).update(sent=True)
        if not claimed:
            continue

        tokens = list(notification.user.fcm_tokens.values_list("token", flat=True))
        for token in tokens:
            result = send_fcm_notification(token, "Booking Reminder", notification.message)
            if result.get("unregistered"):
                # The app was uninstalled or the token expired - stop sending to it
                FCMToken.objects.filter(token=token).delete()


def start():
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(send_due_notifications, 'interval', minutes=1)  # every 1 min check
    _scheduler.start()
    logger.info("Notification scheduler started")
