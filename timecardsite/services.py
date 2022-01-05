"""
Services for Lightspeed API interatcion
"""
from collections import defaultdict
import time
from dataclasses import dataclass
import json

from datetime import datetime, date, timedelta, timezone
import pytz
from requests import request

from timecardsite.secrets import CLIENT_ID, CLIENT_SECRET

AUTH_URL = 'https://cloud.lightspeedapp.com/oauth/access_token.php'
BASE_URL = 'https://api.lightspeedapp.com/'


class InvalidGrant(Exception):
    pass

class InvalidToken(Exception):
    pass

def _refresh_access_token(account):
        '''
        uses refresh token to retrieve a new access token
        :return: new access token
        '''
        payload = {
            'refresh_token': account.refresh_token,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'refresh_token',
        }

        response = request('POST', AUTH_URL, data=payload)

        if response.status_code == 400:
            raise InvalidGrant('Refresh token is invalid. Perhaps it was revoked?')
        return response.json()['access_token']

def _call(endpoint, account, params):
    '''
    just calls the API with the parameters given. used exclusively by _call_api()
    :param endpoint: string of the endpoint being called.
    :param params: dict of query parameters used in api call
    :return: the decoded JSON from response
    '''
    endpoint = BASE_URL + endpoint
    bearer = {
        'Authorization': 'Bearer ' + account.access_token
    }

    response = request('GET', endpoint, headers=bearer, params=params)

    if response.status_code == 401 or response.status_code == 400:
        raise InvalidToken('Access Token is Expired.')
    return response.json()

def _call_api(endpoint, account, params=None):
    '''
    utility function for calling API. handles:
        Token refreshes
        Converting datetimes to iso format
        Pagination
        Rate Limiting (soon)

    :param endpoint: string of the endpoint being called.
                     passed on to _call()
    :param params: dict of query parameters used in the api call
    :return: a generator for each page of the decoded JSON from response
    '''
    if params:
        # look for datetimes to convert and query ops
        for key, param in params.items():
            # datetimes may not have query op passed in
            if isinstance(param, datetime):
                params[key] = param.isoformat()

            # datetimes may be passed in with query op
            if isinstance(param, list):
                if len(param) > 1:
                    if isinstance(param[1], datetime):
                        params[key][1] = param[1].isoformat()

                    # necessary for between date lookups
                    if len(param) == 3:
                        if isinstance(param[2], datetime):
                            params[key][2] = param[2].isoformat()

                    # also, join the list
                    params[key] = ','.join(params[key])
    else:
        # we make an empty params dict to make pagination simpler
        params = dict()
    while True:
        try:
            response = _call(endpoint, account, params)
            yield response
        except InvalidToken: # refreshing access token when necessary
            account.access_token = _refresh_access_token(account)
            account.save()

            response = _call(endpoint, account, params)
            yield response

        if 'offset' in response['@attributes']:
            count = int(response['@attributes']['count'])
            offset = int(response['@attributes']['offset'])
            limit = int(response['@attributes']['limit'])

            if count - offset > limit:
                params['offset'] = str(offset + 100)

            else:
                break
        else:
            break
            
def get_tokens(code):
    '''
    uses temp code from lightspeed to request and save initial tokens
    :param code: temporary code from LS
    :return: the tokens
    '''

    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code'
    }

    response = request('POST', AUTH_URL, data=payload)

    if response.status_code == 400:
        raise InvalidGrant("Temporary code not honored. Maybe it expired?")

    access_token = response.json()['access_token']
    refresh_token = response.json()['refresh_token']

    return (access_token, refresh_token)

def get_account_info(code):
    '''
    This is kind of a special case as it does make a direct call to API 
    but it never needs an account ID, just client ID and secret, and tokens. 
    Also, we need to call this once before we ever construct the account object, 
    as this call is what will give us the account ID and name and allow us to make 
    more API calls. 

    What we'll do is construct some kind of alternative account-like object, like a 
    Record type or whatever, to pass into `_call_api` that looks and behaves like an 
    account from the perspective of _call_api and _call. 
    :param access_token: LS temporary code
    :return: a dict with access tokens, account ID, and account name,
             that can be unpacked when we create account object
    '''
    @dataclass
    class DuckAccount:
        access_token: str
        refresh_token: str
        
        def save(self):
            pass

    access_token, refresh_token = get_tokens(code)
    account = DuckAccount(access_token, refresh_token)

    account_info = next(_call_api('API/Account.json', account))

    return {
        'access_token': account.access_token,
        'refresh_token': account.refresh_token,
        'account_id': account_info['Account']['accountID'],
        'name': account_info['Account']['name']
    }

def map_employee_ids_to_names(account):
    employee_id_map = dict()
    for page in _call_api(
        f'API/Account/{account.account_id}/Employee.json',
        account, params={'archived': True}):

        for employee in page['Employee']:
            employee_id_map[employee['employeeID']] = employee['firstName'] + ' ' + employee['lastName']

    return employee_id_map

def get_employee_ids_and_names(account):
    employee_list = []
    for employee in next(_call_api(
        f'API/Account/{account.account_id}/Employee.json',
        account))['Employee']:

        employee_list.append(
            (employee['employeeID'] + ',' + employee['firstName'] + ' ' + employee['lastName'],
             employee['firstName'] + ' ' + employee['lastName'])
        )
    return employee_list

def get_employee_ids_names_and_emails(account):
    employee_list = []
    for page in _call_api(f'API/Account/{account.account_id}/Employee.json',
            account, params={'load_relations': json.dumps(['Contact'])}):

        for employee in page['Employee']:

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
    shop_id_map = dict()
    for shop in next(_call_api(
        f'API/Account/{account.account_id}/Shop.json', 
        account))['Shop']:

        shop_id_map[shop['shopID']] = shop['name']

    return shop_id_map

def get_punch_log_by_employee(account, employee_id,
                                start_date=None, end_date=None):

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

    for page in _call_api(f'API/Account/{account.account_id}/EmployeeHours.json',
        account,
        params={
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

def get_punch_log(account, start_date=None, end_date=None):
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
    punch_log_dd = defaultdict(lambda: defaultdict(list))
    total_hours = 0
    shop_totals = defaultdict(float)
    employee_totals = defaultdict(float)

    # shops and employees
    shops = map_shop_ids_to_names(account)
    employees = map_employee_ids_to_names(account) 

    for page in _call_api(f'API/Account/{account.account_id}/EmployeeHours.json',
        account,
        params={
            'checkIn': ['><', start_date, end_date],
            'orderby': 'employeeHoursID',
            'orderby_desc': '1', # most recent shifts first
        }):

        # if 0 shifts
        if int(page['@attributes']['count']) == 0:
            break

        if not isinstance(page['EmployeeHours'], list):
            # if only one shift 
            page['EmployeeHours'] = [page['EmployeeHours']]
        
        for shift in page['EmployeeHours']:

            # pull the check in date from the shift
            # convert it to timezone associated with account
            # truncate it to just a date and hold on to this info
            check_in = datetime.fromisoformat(shift['checkIn'])
            localized_check_in = check_in.astimezone(pytz.timezone(str(account.timezone)))
            shift_date = localized_check_in.date()

            # get employee and shop names
            shop_name = shops[shift['shopID']]
            employee_name = employees[shift['employeeID']]

            # pull check out time or use current time
            # calculate shift time
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
            punch_log_dd[shift_date][shop_name].append({
                'name': employee_name,
                'check_in': check_in,
                'check_out': check_out,
                'shift_time': shift_time,
            })

    # now we have to convert all of our defaultdicts to dicts
    # for proper template rendering
    punch_log = dict()
    for day in punch_log_dd:
        punch_log[day] = dict(punch_log_dd[day])

    return {
        'punch_log': punch_log,
        'total_hours': total_hours,
        'shop_totals': dict(shop_totals),
        'employee_totals': dict(employee_totals)
    }
