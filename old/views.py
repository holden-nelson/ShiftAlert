from collections import defaultdict
from datetime import datetime, date, timedelta, timezone
import pytz

from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from invitations.utils import get_invitation_model

import timecardsite.services as services
from timecardsite.models import Account, Profile, InvitationMeta, Shop
from timecardsite.forms import OnboardingForm

def test(request, code):
    return HttpResponse(f'Test Page {code}')

def index(request):
    if request.user.is_authenticated:
        return redirect('post_login')
    return redirect('account_login')

def auth(request):
    # capture code from url
    code = request.GET.get('code')

    if code:
        # request tokens
        tokens = services.get_access_token(code)

        # request account info
        account_info = services.get_account_info(tokens['access_token'])

        # create Account object
        account = Account(
            account_id = account_info['account_id'],
            access_token = tokens['access_token'],
            refresh_token = tokens['refresh_token'],
            name = account_info['name']
        )
        account.save()

        for shop in services.get_shops(account.account_id, account.access_token):
            shop = Shop(
                account = account,
                shop_id = shop['shop_id'],
                name = shop['name']
            )
            shop.save()

        profile = Profile(
            user = request.user,
            account = account,
            role = 'mgr'
        )
        profile.save()

        return redirect('post_login')

@login_required()
def post_login(request):
    try:
        request.user.profile
    except Profile.DoesNotExist:
        return redirect('connect')

    if request.user.profile.role == 'mgr':
        if request.user.profile.account.is_onboarded:
            return redirect('employee')
        return redirect('onboard')
    else:
        return redirect('employee')

@login_required()
def connect(request):
    link = 'https://cloud.lightspeedapp.com/oauth/authorize.php?response_type=code&client_id=aedd49fc98a386cbf6a8939d89cf671683078bd7ba349292a226772024adc466&scope=employee:all'
    return render(request, 'connect.html', {'link': link})

@login_required()
def onboard(request):
    # get list of employees
    try:
        employees_dict = services.get_employees_info(
            account_id=request.user.profile.account.account_id,
            access_token=request.user.profile.account.access_token
        )
    except services.InvalidToken:
        new_access_token = services.refresh_access_token(request.user.profile.account.refresh_token)
        request.user.profile.account.access_token = new_access_token
        request.user.profile.account.save()
        employees_dict = services.get_employees_info(
            account_id=request.user.profile.account.account_id,
            access_token=request.user.profile.account.access_token
        )

    # transform into iterable of tuples
    employees = [(id, info['name']) for id, info in employees_dict.items()]

    if request.method == 'POST':
        form = OnboardingForm(request.POST, employees=employees)
        if form.is_valid():
            timezone = form.cleaned_data['timezone']
            employee_id = form.cleaned_data['employee']
            name = employees_dict[employee_id]['name']

            request.user.profile.account.timezone = timezone
            request.user.profile.employee_id = employee_id
            request.user.profile.name = name



            request.user.profile.account.is_onboarded = True
            request.user.profile.account.save()
            request.user.profile.save()
            return redirect('employee')
    else:
        form = OnboardingForm(employees=employees)

    return render(request, 'onboard.html', {'form': form})

@login_required()
def manager(request):
    # manager dashboard lists hours totals for each store,
    # hours totals for each employee, and every shift for the
    # requested date interval

    # fetch users timezone and activate it
    users_timezone = request.user.profile.account.timezone
    timezone.activate(users_timezone)

    if request.GET:
        # pull start and end dates out of the query string
        # add min and max times to cover full days


        requested_start = datetime.combine(
            date.fromisoformat(request.GET.get('start')),
            datetime.min.time()
        )
        requested_end = datetime.combine(
            date.fromisoformat(request.GET.get('end')),
            datetime.max.time()
        )

    else:
        # defaults
        requested_start = datetime.combine(
            date.today() - timedelta(weeks=2),
            datetime.min.time()
        )
        requested_end = datetime.combine(date.today(), datetime.max.time())

    # localize dates
    start_date = pytz.timezone(str(users_timezone)).localize(requested_start, is_dst=None)
    end_date = pytz.timezone(str(users_timezone)).localize(requested_end, is_dst=None)

    # Query the API for employees shifts - all employees
    try:
        shifts = services.get_employee_hours(
            start_date=start_date,
            end_date=end_date,
            account_id=request.user.profile.account_id,
            access_token=request.user.profile.account.access_token
        )
    except services.InvalidToken:
        new_access_token = services.refresh_access_token(request.user.profile.account.refresh_token)
        request.user.profile.account.access_token = new_access_token
        request.user.profile.account.save()
        shifts = services.get_employee_hours(
            start_date=start_date,
            end_date=end_date,
            account_id=request.user.profile.account_id,
            access_token=request.user.profile.account.access_token
        )
        # TODO handle token still not working

    # 3. Pass this info to template
    #   - Dictionary
    #       Total Hours dict:
    #           Shops Default Dict
    #               Shop: Num Hours,
    #               Shop: Num Hours, etc..
    #           Employees Default Dict
    #               Name: Num Hours,
    #               Name: Num Hours, etc...
    #       Shifts:
    #           List of Dicts
    #               Employee: Name
    #               CheckIn: Datetime
    #               CheckOut: Datetime (if there is one)
    #               Shop: Name
    #               Hours: Num Hours
    try:
        employees = services.get_employees_info(request.user.profile.account.account_id,
                                                request.user.profile.account.access_token)
    except services.InvalidToken:
        new_access_token = services.refresh_access_token(request.user.profile.account.refresh_token)
        request.user.profile.account.access_token = new_access_token
        request.user.profile.account.save()
        employees = services.get_employees_info(request.user.profile.account.account_id,
                                                    request.user.profile.account.access_token)

    employee_shifts = []
    total_hours_shops = defaultdict(int)
    total_hours_employees = defaultdict(int)

    for shift in shifts:
        shop_name = Shop.objects.get(account_id=request.user.profile.account.account_id,
                                     shop_id=shift['shop_id']).name
        employee_name = employees[shift['employee_id']]['name']
        if shift['check_out']:
            shift_delta = shift['check_out'] - shift['check_in']
        else:
            shift_delta = datetime.now(timezone.utc) - shift['check_in']
        hours = shift_delta.total_seconds() / 3600
        total_hours_shops[shop_name] += hours
        total_hours_employees[employee_name] += hours
        employee_shifts.append({
            'employee': employee_name,
            'check_in': shift['check_in'],
            'check_out': shift['check_out'],
            'hours': hours,
            'shop': shop_name
        })
    employee_hours = {
        'total_hours': {
            'shops': dict(total_hours_shops),
            'employees': dict(total_hours_employees)
        },
        'shifts': employee_shifts
    }

    return render(request, 'managers.html', {
        'employee_hours': employee_hours
    })

@login_required()
def employee(request):
    # employee dashboard lists shifts and total hours
    # for a given date interval - default is current work week

    # fetch users timezone and activate it
    users_timezone = request.user.profile.account.timezone
    timezone.activate(users_timezone)

    if request.GET:
        # pull start and end dates out of the query string
        # add min and max times to cover full days


        requested_start = datetime.combine(
            date.fromisoformat(request.GET.get('start')),
            datetime.min.time()
        )
        requested_end = datetime.combine(
            date.fromisoformat(request.GET.get('end')),
            datetime.max.time()
        )

    else:
        # defaults
        requested_start = datetime.combine(
            date.today() - timedelta(weeks=2),
            datetime.min.time()
        )
        requested_end = datetime.combine(date.today(), datetime.max.time())

    # localize dates
    start_date = pytz.timezone(str(users_timezone)).localize(requested_start, is_dst=None)
    end_date = pytz.timezone(str(users_timezone)).localize(requested_end, is_dst=None)

    # Query the API for employees shifts
    try:
        shifts = services.get_employee_hours(
            employee_id=request.user.profile.employee_id,
            start_date=start_date,
            end_date=end_date,
            account_id=request.user.profile.account_id,
            access_token=request.user.profile.account.access_token
        )
    except services.InvalidToken:
        new_access_token = services.refresh_access_token(request.user.profile.account.refresh_token)
        request.user.profile.account.access_token = new_access_token
        request.user.profile.account.save()
        shifts = services.get_employee_hours(
            employee_id=request.user.profile.employee_id,
            start_date=start_date,
            end_date=end_date,
            account_id=request.user.profile.account_id,
            access_token=request.user.profile.account.access_token
        )
        # TODO handle token still not working

    # 3. Pass this info to template
    #   - Dictionary
    #       Total Hours default dict:
    #           Shop: Num Hours,
    #           Shop: Num Hours, etc..
    #       Shifts:
    #           List of Dicts
    #               CheckIn: Datetime
    #               CheckOut: Datetime (if there is one)
    #               Shop: Name
    #               Hours: Num Hours
    employee_shifts = []
    total_hours = defaultdict(int)

    for shift in shifts:
        shop_name = Shop.objects.get(account_id=request.user.profile.account.account_id,
                                     shop_id=shift['shop_id']).name
        if shift['check_out']:
            shift_delta = shift['check_out'] - shift['check_in']
        else:
            shift_delta = datetime.now(timezone.utc) - shift['check_in']
        hours = round((shift_delta.total_seconds() / 3600), 2)
        total_hours[shop_name] += hours
        employee_shifts.append({
            'check_in': shift['check_in'],
            'check_out': shift['check_out'],
            'hours': str(hours),
            'shop': shop_name
        })
    # create a dictionary called employee_hours
    # key total_hours is total_hours defaultdict
    # key shifts is employee_shifts list
    employee_hours = {
        'total_hours': dict(total_hours),
        'shifts': employee_shifts
    }

    return render(request, 'employees.html', {
        'employee_hours': employee_hours,
    })

@login_required()
def invite(request):
    """
    managers can invite employees to the platform
    They can choose whether the employee has manager or just employee permissions
    They are required to put an email into Lightspeed to send the invite
    From here they can also see which employees have invites out, and who has accepted
    """
    Invitation = get_invitation_model()

    if request.POST:
        id = request.POST.get('id')
        name = request.POST.get('name')
        email = request.POST.get('email')

        invite = Invitation.create(email, inviter=request.user)
        invite.send_invitation(request)
        invite_meta = InvitationMeta.objects.create(
            invite=invite,
            employee_id=id,
            name=name
        )
        invite_meta.save()
        # todo invite successful message
        return redirect('invite')
    else:
        # first thing we do is get a list of employees
        try:
            employees = services.get_employees_info(
                account_id=request.user.profile.account_id,
                access_token=request.user.profile.account.access_token
            )
        except services.InvalidToken:
            new_access_token = services.refresh_access_token(request.user.profile.account.refresh_token)
            request.user.profile.account.access_token = new_access_token
            request.user.profile.account.save()
            employees = services.get_employees_info(
                account_id=request.user.profile.account_id,
                access_token=request.user.profile.account.access_token
            )
            # TODO handle token still not working

        # from here we need to parse the list into
        #   - able to be invited
        #   - unable cause no email
        #   - invite is pending
        #   - invite is accepted
        # we also need to remove the employee that's currently logged in
        invitable = []
        missing_email = []
        pending_invite = []
        accepted_invite = []

        for id, employee in employees.items():
            # remove the logged in employee from the list
            if id == request.user.profile.employee_id:
                pass

            # if missing email, put them in missing email list
            elif not employee['email']:
                missing_email.append({
                    'id': id,
                    'name': employee['name']
                })
            else:
                # check for invites
                try:
                    employee_invite = Invitation.objects.get(email=employee['email'])
                    if employee_invite.accepted:
                        accepted_invite.append({
                            'id': id,
                            'name': employee['name'],
                            'email': employee['email']
                        })
                    else:
                        pending_invite.append({
                            'id': id,
                            'name': employee['name'],
                            'email': employee['email']
                        })
                except Invitation.DoesNotExist:
                    # employee has not been invited
                    invitable.append({
                        'id': id,
                        'name': employee['name'],
                        'email': employee['email']
                    })

        # now we just pass everything to the template
        return render(request, 'invite.html', {
            'invitable': invitable,
            'missing_email': missing_email,
            'pending_invite': pending_invite,
            'accepted_invite': accepted_invite
        })



