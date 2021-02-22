from django.db import models
from django.contrib.auth import get_user_model

from invitations.models import Invitation
from timezone_field import TimeZoneField
import environ

env = environ.Env()

class Account(models.Model):
    account_id = models.CharField(max_length=8, primary_key=True)
    access_token = models.CharField(max_length=64)
    refresh_token = models.CharField(max_length=64)
    name = models.CharField(max_length=64)
    timezone = TimeZoneField(choices_display='WITH_GMT_OFFSET',
                             default='America/Boise')
    is_onboarded = models.BooleanField(default=False)



class Profile(models.Model):
    roles = [
        ('mgr', 'Manager'),
        ('emp', 'Employee')
    ]

    user = models.OneToOneField(
        get_user_model(),
        on_delete=models.CASCADE,
        primary_key=True
    )
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    role = models.CharField(max_length=8, choices=roles,
                            default='emp', blank=False)
    employee_id = models.CharField(max_length=8, default='', blank=True)
    name = models.CharField(max_length=64, default='', blank=True)

    @property
    def is_manager(self):
        return self.role == 'mgr'


class Shop(models.Model):
    class Meta:
        unique_together = (('shop_id', 'account'),)

    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    shop_id = models.CharField(max_length=4)
    name = models.CharField(max_length=64)

class InvitationMeta(models.Model):
    invite = models.OneToOneField(
        Invitation,
        on_delete=models.CASCADE,
        primary_key=True
    )
    employee_id = models.CharField(max_length=8)
    name = models.CharField(max_length=64)



