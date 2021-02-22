import random, string

from timecardsite.models import Account

def generate_random_token(length=16):
    return ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase
                                 + string.digits) for _ in range(length))

def generate_random_account():
    return Account(
        account_id=generate_random_token(5),
        access_token=generate_random_token(),
        refresh_token=generate_random_token(),
        name='Manager Store for Managers',
        timezone='America/Boise',
        is_onboarded=True
    )