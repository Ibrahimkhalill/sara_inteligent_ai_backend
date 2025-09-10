# notifications/jobs.py
from apscheduler.schedulers.background import BackgroundScheduler
from django.utils import timezone
from .models import Notification
from .send_fcm_notification import send_fcm_notification
def send_due_notifications():
    print("filter notification")
    now = timezone.now()
    print(now)
    due_notifications = Notification.objects.filter(sent=False, notify_at__lte=now)
    
    print("due_notifications",due_notifications)

    for notification in due_notifications:
        tokens = list(notification.user.fcm_tokens.values_list("token", flat=True))
        print("Tokens to send:", tokens)

        for token in tokens:
            data = send_fcm_notification(token, "Booking Reminder", notification.message)
            print("daya sent",data)
        notification.sent = True
        notification.save()
def start():
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_due_notifications, 'interval', minutes=1)  # every 1 min check
    scheduler.start()
