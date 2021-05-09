from django import forms
from timezone_field import TimeZoneFormField

from timecardsite.services import get_employee_ids_and_names

class OnboardingForm(forms.Form):

    def __init__(self, *args, **kwargs):
        account = kwargs.pop('account')
        choices = get_employee_ids_and_names(account)
        choices.append(
            ('00', 'I am not one of these employees')
        )
        super(OnboardingForm, self).__init__(*args, **kwargs)

        self.fields['timezone'] = TimeZoneFormField(
            choices_display='WITH_GMT_OFFSET', initial=account.timezone)

        self.fields['employees'] = forms.ChoiceField(
            choices=choices)

class NameForm(forms.Form):
    name = forms.CharField(max_length=64)