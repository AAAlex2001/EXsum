import os
from celery import Celery
from celery.schedules import crontab
#import django

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "oae.settings")

app = Celery("oae")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
#django.setup()
app.conf.enable_utc = False

app.conf.beat_schedule = {
	#'check_usdts': {
                #'task': 'operation.tasks.check_usdts',
                #'schedule': 60 * 5,
            #}

}