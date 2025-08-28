import os
from celery import Celery
from celery.schedules import crontab
from django.conf import settings

# Set the default Django settings module for the 'celery' program
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'budget_management.settings')

# Create the Celery app
app = Celery('budget_management')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps
app.autodiscover_tasks()

# Celery Beat Schedule for periodic tasks
app.conf.beat_schedule = {
    'check-dayparting-every-hour': {
        'task': 'budget_system.tasks.check_campaign_dayparting',
        'schedule': crontab(minute=0),  # Every hour on the hour
    },
    'reset-daily-budgets': {
        'task': 'budget_system.tasks.reset_daily_budgets',
       'schedule': crontab(minute=0, hour=0),  # Every day at midnight
    },
    'reset-monthly-budgets': {
        'task': 'budget_system.tasks.reset_monthly_budgets',
        'schedule': crontab(minute=0, hour=0, day_of_month=1),  # First day of every month at midnight
    },
    'update-campaign-status-every-5min': {
        'task': 'budget_system.tasks.update_campaign_status',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
}

# Timezone configuration
app.conf.timezone = 'UTC'

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')