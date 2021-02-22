from django.contrib.auth import get_user_model
from django.dispatch import receiver

from invitations.utils import get_invitation_model
from invitations.signals import invite_accepted

from timecardsite.models import Profile, InvitationMeta

@receiver(invite_accepted)
def receive_invite_signal(sender, email, **kwargs):
    invite = get_invitation_model().objects.get(email=email)
    invite_meta = InvitationMeta.objects.get(invite=invite)

    user = get_user_model().objects.get(email=email)
    account = get_user_model().objects.get(id=invite.inviter_id).profile.account
    employee_id = invite_meta.employee_id
    name = invite_meta.name


    profile = Profile.objects.create(
        account=account,
        user=user,
        role='emp',
        employee_id=employee_id,
        name=name
    )
    profile.save()

