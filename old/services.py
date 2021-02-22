"""
Services for Lightspeed API interaction
"""

import requests
import environ
from datetime import datetime

from plaw import Plaw

### Globals
env = environ.Env()
AUTH_URL = 'https://cloud.lightspeedapp.com/oauth/access_token.php'
BASE_URL = 'https://api.lightspeedapp.com/'
CLIENT_ID = env('CLIENT_ID')
CLIENT_SECRET = env('CLIENT_SECRET')

### Custom Exceptions
class InvalidGrant(Exception):
    pass

class InvalidToken(Exception):
    pass

### Service Functions
def get_access_token(code):
    """
    uses the temporary code from lightspeed to request
    access token, refresh token. Returns those two values
    in a dict.
    """
    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code'
    }

    response = requests.request('POST', AUTH_URL, data=payload)

    # TODO throw an error on response 400 invalid_grant
    # likely means our servers were too busy and the temp
    # token expired before we got the chance to use it

    tokens = {
        'access_token': response.json()['access_token'],
        'refresh_token': response.json()['refresh_token']
    }
    return tokens

def refresh_access_token(refresh_token):
    """
    uses refresh_token to request another access token
    returns the access token
    """
    payload = {
        'refresh_token': refresh_token,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'refresh_token',
    }

    response = requests.request('POST', AUTH_URL, data=payload)

    if response.status_code == 400:
        raise InvalidGrant('Your refresh token is invalid.')
    return response.json()['access_token']

def get_account_info(access_token):
    """
    uses access token to request basic account information
    returns accountID and name
    """
    account_url = BASE_URL + 'API/Account.json'
    bearer = {
        'Authorization': 'Bearer ' + access_token
    }


    response = requests.request('GET', account_url, headers=bearer)
    if response.status_code == 401:
        raise InvalidToken('Access Token has expired')

    account_info = {
        'account_id': response.json()['Account']['accountID'],
        'name': response.json()['Account']['name']
    }

    return account_info

def get_shops(account_id, access_token):
    """
    returns a list of shop dictionaries
        - shop id
        - shop name
    """
    shop_url =  BASE_URL + f'API/Account/{account_id}/Shop.json'
    bearer = {
        'Authorization': 'Bearer ' + access_token
    }
    response = requests.request('GET', shop_url, headers=bearer)
    if response.status_code == 401:
        raise InvalidToken('Access Token has expired')

    shops = []
    for shop in response.json()['Shop']:
        shops.append({
            'shop_id': shop['shopID'],
            'name': shop['name']
        })

    return shops


def get_employees_info(account_id, access_token):
    """
    Retrieves a list of every employee
    Returns a dict with
        - employee ID as key
        - name
        - email
    """
    # TODO handle pagination (in case more than 100 employees)

    employee_url = BASE_URL + f'API/Account/{account_id}/Employee.json?load_relations=["Contact"]'
    bearer = {
        'Authorization': 'Bearer ' + access_token
    }

    response = requests.request('GET', employee_url, headers=bearer)
    if response.status_code == 401:
        raise InvalidToken('Access Token has expired')

    employees = dict()
    for employee in response.json()['Employee']:
        employee_id = employee['employeeID']
        employee_name = employee['firstName'] + ' ' + employee['lastName']
        try:
            employee_email = employee['Contact']['Emails']['ContactEmail']['address']
        except TypeError:
            employee_email = ''
        employees[employee_id] = {
            'name': employee_name,
            'email': employee_email
        }

    return employees

def get_employee_hours(start_date, end_date, account_id,
                       access_token, employee_id=None, offset='0'):
    """
    Retrieves shifts for given employee in given date range
    start and end dates are tz aware datetime objects
    Returns a list of dicts:
        - check_in: the in punch
        - check_out: the out punch (might be None)
        - shop_id: id of the store they're working in
        - employee_id: id of the employee that worked the shift
    """
    # todo make sure end date is inclusive
    # build and make our request
    if employee_id:
        queries = { # maybe I have to url encode this manually?
            'employeeID': employee_id,
            'checkIn': '>,' + start_date.isoformat(),
            'checkOut': '<,' + end_date.isoformat(),
            'orderby': 'employeeHoursID',
            'orderby_desc': '1', # most recent shifts first
            'offset': offset,
        }
    else:
        queries = {
            'checkIn': '>,' + start_date.isoformat(),
            'checkOut': '<,' + end_date.isoformat(),
            'orderby': 'employeeHoursID',
            'orderby_desc': '1',  # most recent shifts first
            'offset': offset,
        }

    employee_hours_url = BASE_URL + f'API/Account/{account_id}/EmployeeHours.json'
    bearer = {
        'Authorization': 'Bearer ' + access_token
    }

    response = requests.request('GET', employee_hours_url,
                                headers=bearer, params=queries)
    if response.status_code == 401:
        raise InvalidToken('Access Token has expired')

    # check for shifts
    attributes = response.json()['@attributes']
    count = int(attributes['count'])
    shifts = []

    if count > 0:
        # process the data
        for shift in response.json()['EmployeeHours']:
            shift_d = dict()
            shift_d['check_in'] = datetime.fromisoformat(shift['checkIn'])
            try:
                shift_d['check_out'] = datetime.fromisoformat(shift['checkOut'])
            except KeyError:
                shift_d['check_out'] = None
            shift_d['shop_id'] = shift['shopID']
            shift_d['employee_id'] = shift['employeeID']

            shifts.append(shift_d)

        # check for pagination requirements
        offset = int(attributes['offset'])
        limit = int(attributes['limit'])

        # get the next list of shifts recursively
        if count - offset > limit:
            offset += limit
            shifts += get_employee_hours(employee_id, start_date, end_date,
                                         account_id, access_token, offset=str(offset))

    return shifts

