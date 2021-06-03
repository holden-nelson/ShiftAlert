from django import forms
from timezone_field import TimeZoneFormField

from timecardsite.services import get_employee_ids_and_names

class OnboardingForm(forms.Form):
    pay_period_choices = [
        ('biweekly', 'Bi-weekly'),
    ]

    pay_periods = forms.ChoiceField(
        choices=pay_period_choices
    )
    reference_date = forms.DateField()

    def __init__(self, *args, **kwargs):
        account = kwargs.pop('account')
        employee_choices = get_employee_ids_and_names(account)
        employee_choices.append(
            ('00', 'I am not one of these employees')
        )
        super(OnboardingForm, self).__init__(*args, **kwargs)

        self.fields['timezone'] = TimeZoneFormField(
            choices_display='WITH_GMT_OFFSET', initial=account.timezone)

        self.fields['employees'] = forms.ChoiceField(
            choices=employee_choices)

class NameForm(forms.Form):
    name = forms.CharField(max_length=64)

class RangeForm(forms.Form):
    range_choices = [
        ('current', 'Current Pay Period'),
        ('previous', 'Previous Pay Period'),
        ('custom', 'Custom Date Range'),
    ]

    range = forms.ChoiceField(
        choices=range_choices
    )
    start_date = forms.DateField(required=False)
    end_date = forms.DateField(required=False)