"""
Services for Lightspeed API interatcion
"""
from collections import defaultdict

from datetime import datetime, date, timedelta, timezone
import pytz
from plaw import Plaw

from timecardsite.secrets import CLIENT_ID, CLIENT_SECRET

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

def map_employee_ids_to_names(account):
    # todo write a test for this :/
    api = Plaw(CLIENT_ID, CLIENT_SECRET,
               account_id=account.account_id,
               refresh_token=account.refresh_token,
               access_token=account.access_token)

    employee_id_map = dict()
    for employee in next(api.employee(params={'archived': True}))['Employee']:
        employee_id_map[employee['employeeID']] = employee['firstName'] + ' ' + employee['lastName']

    return employee_id_map

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

def map_shop_ids_to_names(account):
    # todo write a test for this :/
    api = Plaw(CLIENT_ID, CLIENT_SECRET,
               account_id=account.account_id,
               refresh_token=account.refresh_token,
               access_token=account.access_token)

    shop_id_map = dict()
    for shop in next(api.shop())['Shop']:
        shop_id_map[shop['shopID']] = shop['name']

    return shop_id_map

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
    shops = map_shop_ids_to_names(account)
    employee_totals = defaultdict(int)

    for page in api.employee_hours({
        'checkIn': ['><', start_date, end_date],
        'orderby': 'employeeHoursID',
        'orderby_desc': '1', # most recent shifts first
        'employeeID': employee_id
    }):
        num_shifts = int(page['@attributes']['count'])
        if num_shifts != 0:
            if not isinstance(page['EmployeeHours'], list):
                page['EmployeeHours'] = [page['EmployeeHours']]

            for shift in page['EmployeeHours']:

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
        'totals': dict(employee_totals)
    }

def get_shifts_and_totals(account, start_date=None, end_date=None):
    # todo write a test for this
    api = Plaw(CLIENT_ID, CLIENT_SECRET,
               account_id=account.account_id,
               refresh_token=account.refresh_token,
               access_token=account.access_token)

    # date wrangling
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

    # counters
    days_dd = defaultdict(lambda: defaultdict(list))
    total_hours = 0
    shop_totals = defaultdict(float)
    employee_totals = defaultdict(float)

    # shops and employees
    shops = map_shop_ids_to_names(account)
    employees = map_employee_ids_to_names(account)

    for page in api.employee_hours({
        'checkIn': ['><', start_date, end_date],
        'orderby': 'employeeHoursID',
        'orderby_desc': '1', # most recent shifts first
    }):
        if not isinstance(page['EmployeeHours'], list):
            page['EmployeeHours'] = [page['EmployeeHours']]

        for shift in page['EmployeeHours']:

            # pull the check in date from the shift
            # convert it to timezone associated with account
            # truncate it to just a date and hold on to this info
            check_in = datetime.fromisoformat(shift['checkIn'])
            localized_check_in = check_in.astimezone(pytz.timezone(str(account.timezone)))
            shift_date = localized_check_in.date()

            # pull the shop id from the shift
            # get its name from dict and hold on to this info
            shop_name = shops[shift['shopID']]

            # get employee name from dict
            # pull check out time or use current time
            # calculate shift time
            employee_name = employees[shift['employeeID']]
            if 'checkOut' in shift:
                check_out = datetime.fromisoformat(shift['checkOut'])
                shift_delta = check_out - check_in
            else:
                check_out = None
                shift_delta = datetime.now(timezone.utc) - check_in
            shift_time = shift_delta.total_seconds() / 3600

            # add totals
            total_hours += shift_time
            shop_totals[shop_name] += shift_time
            employee_totals[employee_name] += shift_time

            # append shift to proper location in nested dict
            days_dd[shift_date][shop_name].append({
                'name': employee_name,
                'check_in': check_in,
                'check_out': check_out,
                'shift_time': shift_time,
            })

    # now we have to convert all of our defaultdicts to dicts
    days = dict()
    for d in days_dd:
        days[d] = dict(days_dd[d])

    return {
        'days': days,
        'total_hours': total_hours,
        'shop_totals': dict(shop_totals),
        'employee_totals': dict(employee_totals)
    }









