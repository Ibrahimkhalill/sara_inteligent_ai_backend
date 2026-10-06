import os
import sys

from django.apps import AppConfig
from django.conf import settings


class NotificationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notification'


    def ready(self):
        if not settings.ENABLE_SCHEDULER:
            return

        # Under manage.py, only start for runserver - not migrate, shell, etc.
        if os.path.basename(sys.argv[0]) == 'manage.py':
            if len(sys.argv) < 2 or sys.argv[1] != 'runserver':
                return
            # The autoreloader starts a parent and a child process; only run in the child
            if '--noreload' not in sys.argv and os.environ.get('RUN_MAIN') != 'true':
                return

        from . import jobs
        jobs.start()
