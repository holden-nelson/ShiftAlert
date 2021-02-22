"""
Production settings for Heroku
"""
import requests
from timesheet.settings.base import *

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

# Parse database connection url strings like psql://user:pass@127.0.0.1:8458/db
DATABASES = {
    # read os.environ['DATABASE_URL'] and raises ImproperlyConfigured exception if not found
    'default': env.db(),
}

mailtrap_api_token = env('MAILTRAP_API_TOKEN')
response = requests.get(f'https://mailtrap.io/api/v1/inboxes.json?api_token={mailtrap_api_token}')
credentials = response.json()[0]

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = credentials['domain']
EMAIL_HOST_USER = credentials['username']
EMAIL_HOST_PASSWORD = credentials['password']
EMAIL_PORT = credentials['smtp_ports'][0]
EMAIL_USE_TLS = True