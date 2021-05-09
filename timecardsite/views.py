from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required

from timecardsite import services
from timecardsite.models import Account, Profile
from timecardsite.forms import OnboardingForm, NameForm

@login_required()
def index(request):
    return render(request, 'index.html')

def auth(request):
    '''
    takes the code from Lightspeed Auth Servers and
    requests new tokens, which it saves to an account object
    redirects to post_login for onboard check
    '''
    code = request.GET.get('code')

    if code:

        account_info = services.get_initial_account_data(code)
        account = Account(**account_info)
        account.save()

        profile_info = {
            'user': get_user_model().objects.get(id=request.GET.get('state')),
            'account': account,
            'role': 'mgr'
        }
        Profile(**profile_info).save()

        return redirect('post_login')
    else:
        raise Http404('No code provided.')

@login_required()
def post_login(request):
    '''
    determines where the user should be routed after being logged in
    if the user is an employee it should redirect to timecard view
    if the user is a manager
        and has not been onboarded it should redirect to onboard view
        and has been onboarded it should redirect to dashboard view
    '''
    try:
        request.user.profile
    except Profile.DoesNotExist:
        return redirect('connect') # for now

    if request.user.profile.role == 'mgr':
        if request.user.profile.account.is_onboarded:
            return redirect('dashboard')
        else:
            return redirect('onboard')
    else:
        return redirect('timecard')

@login_required()
def connect(request):
    access_link = f'https://cloud.lightspeedapp.com/oauth/authorize.php?response_type=code&client_id=aedd49fc98a386cbf6a8939d89cf671683078bd7ba349292a226772024adc466&scope=employee:all&state={request.user.id}'

    return render(request, 'connect.html', {'access_link': access_link})

@login_required()
def onboard(request):
    if request.method == 'POST':
        form = OnboardingForm(request.POST,
                              account=request.user.profile.account)
        if form.is_valid():
            request.user.profile.account.timezone = form.cleaned_data['timezone']

            if ',' in form.cleaned_data['employees']:
                id, name = form.cleaned_data['employees'].split(',')
                request.user.profile.employee_id = id
                request.user.profile.name = name
            else:
                id = form.cleaned_data['employees']
                request.user.profile.employee_id = id

            request.user.profile.account.is_onboarded = True

            request.user.profile.account.save()
            request.user.profile.save()

            if id == '00':
                return redirect('name')
            else:
                return redirect('dashboard')
    else:
        form = OnboardingForm(account=request.user.profile.account)

    return render(request, 'onboard.html', {'form': form})

def name(request):
    if request.method == 'POST':
        form = NameForm(request.POST)
        if form.is_valid():
            request.user.profile.name = form.cleaned_data['name']
            request.user.profile.save()
            return redirect('dashboard')
    else:
        form = NameForm()

        return render(request, 'name.html', {'form': form})

@login_required()
def timecard(request):
    timezone.activate(request.user.profile.account.timezone)

    if request.GET:
        start = request.GET.get('start')
        end = request.GET.get('end')

        employee_shift_data = services.get_shifts_and_totals_for_given_employee(
            request.user.profile.account,
            request.user.profile.employee_id,
            start_date=start,
            end_date=end
        )
    else:
        employee_shift_data = services.get_shifts_and_totals_for_given_employee(
            request.user.profile.account,
            request.user.profile.employee_id
        )

    # TODO take the context from data and pass it to template
    return render(request, 'timecard.html', employee_shift_data)

def dashboard(request):
    return HttpResponse()