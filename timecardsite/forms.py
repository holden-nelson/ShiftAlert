from django import forms
from timezone_field import TimeZoneFormField

from timecardsite.services import get_employee_ids_and_names

class OnboardingForm(forms.Form):
    timezone = TimeZoneFormField(choices_display='WITH_GMT_OFFSET')

    def __init__(self, *args, **kwargs):
        account = kwargs.pop('account')
        super(OnboardingForm, self).__init__(*args, **kwargs)

        self.fields['employees'] = forms.ChoiceField(
            choices=get_employee_ids_and_names(account))