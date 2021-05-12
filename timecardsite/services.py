"""
Services for Lightspeed API interatcion
"""
from collections import defaultdict

import environ
from datetime import datetime, date, timedelta, timezone
import pytz

from plaw import Plaw

### Globals
env = environ.Env()
CLIENT_ID = env('CLIENT_ID')
CLIENT_SECRET = env('CLIENT_SECRET')

def get_initial_account_data(code):
    api = Plaw(CLIENT_ID, CLIENT_SECRET)
    (access_token, refresh_token) = api.get_tokens(code)
    account_info = api.account()

    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'account_id': account_info['Account']['accountID'],
        'name': account_info['Account']['name']
    }

def get_employee_ids_and_names(account):
    api = Plaw(CLIENT_ID, CLIENT_SECRET,
               account_id=account.account_id,
               refresh_token=account.refresh_token,
               access_token=account.access_token)

    employee_list = []
    for employee in next(api.employee())['Employee']:
        employee_list.append(
            (employee['employeeID'] + ',' + employee['firstName'] + ' ' + employee['lastName'],
             employee['firstName'] + ' ' + employee['lastName'])
        )

    return employee_list

def get_employee_ids_names_and_emails(account):
    api = Plaw(CLIENT_ID, CLIENT_SECRET,
               account_id=account.account_id,
               refresh_token=account.refresh_token,
               access_token=account.access_token)

    employee_list = []
    for employee in next(api.employee(load_contact=True))['Employee']:
        employee_id = employee['employeeID']
        employee_name = employee['firstName'] + ' ' + employee['lastName']
        try:
            employee_email = employee['Contact']['Emails']['ContactEmail']['address']
        except TypeError:
            employee_email = None

        employee_list.append(
            {
                'id': employee_id,
                'name': employee_name,
                'email': employee_email
            }
        )

    return employee_list

def get_shifts_and_totals_for_given_employee(account, employee_id,
                                             start_date=None, end_date=None):
    api = Plaw(CLIENT_ID, CLIENT_SECRET,
               account_id=account.account_id,
               refresh_token=account.refresh_token,
               access_token=account.access_token)

    if not start_date:
        start_date = datetime.combine(
            date.today() - timedelta(weeks=2),
            datetime.min.time()
        )
        end_date = datetime.combine(date.today(), datetime.max.time())
    else:
        start_date = datetime.combine(start_date, datetime.min.time())
        end_date = datetime.combine(end_date, datetime.max.time())

    start_date = pytz.timezone(str(account.timezone)).localize(start_date, is_dst=None)
    end_date = pytz.timezone(str(account.timezone)).localize(end_date, is_dst=None)

    employee_shifts = []
    shops = dict()
    employee_totals = defaultdict(int)

    for page in api.employee_hours({
        'checkIn': ['><', start_date, end_date],
        'orderby': 'employeeHoursID',
        'orderby_desc': '1', # most recent shifts first
        'employeeID': employee_id
    }):
        if not isinstance(page['EmployeeHours'], list):
            page['EmployeeHours'] = [page['EmployeeHours']]

        for shift in page['EmployeeHours']:
            if shift['shopID'] not in shops:
                shops[shift['shopID']] = next(api.shop({'shopID': shift['shopID']}))['Shop']['name']

            check_in = datetime.fromisoformat(shift['checkIn'])
            if 'checkOut' in shift:
                check_out = datetime.fromisoformat(shift['checkOut'])
                shift_delta = check_out - check_in
            else:
                check_out = None
                shift_delta = datetime.now(timezone.utc) - check_in
            shift_time = shift_delta.total_seconds() / 3600

            employee_totals['total'] += shift_time
            employee_totals[shops[shift['shopID']]] += shift_time

            employee_shifts.append({
                'check_in': check_in,
                'check_out': check_out,
                'shift_time': shift_time,
                'shop': shops[shift['shopID']]
            })

    return {
        'shifts': employee_shifts,
        'totals': employee_totals
    }





