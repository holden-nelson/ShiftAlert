import json
from datetime import date, datetime, timedelta
import pytz
from types import GeneratorType

from django.test import TestCase
from unittest.mock import Mock, patch

from timecardsite import services
from timecardsite.tests import generate_random_token, generate_random_account
from timecardsite.secrets import CLIENT_ID, CLIENT_SECRET

class ServicesTests(TestCase):
    def setUp(self):
        self.acct = generate_random_account()

    def test_refresh_access_token_POSTs_to_correct_URL_with_proper_payload(self):
        with patch('timecardsite.services.request') as mocked_request:
            services._refresh_access_token(self.acct)

            mocked_request.assert_called_with('POST',
                'https://cloud.lightspeedapp.com/oauth/access_token.php',
                data={
                    'refresh_token': self.acct.refresh_token,
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET,
                    'grant_type': 'refresh_token'
                })

    def test_refresh_access_token_raises_on_400(self):
        with patch('timecardsite.services.request') as mocked_request:
            mocked_request.return_value.status_code = 400

            with self.assertRaises(services.InvalidGrant):
                    services._refresh_access_token(self.acct)

    def test_refresh_access_token_returns_new_access_token(self):
        with patch('timecardsite.services.request') as mocked_request:
            mocked_request.return_value.status_code = 200
            mocked_response = {
                'access_token': generate_random_token(),
                'expires_in': 3600,
                'token_type': 'bearer',
                'scope': 'employee:all systemuserid:152663'
            }
            mocked_request.return_value.json.return_value = mocked_response

            self.assertEqual(services._refresh_access_token(self.acct), mocked_response['access_token'])

    def test_call_handles_endpoint_and_header(self):
        with patch('timecardsite.services.request') as mocked_request:
            services._call('API/Example/Endpoint.json', self.acct, None)

            mocked_request.assert_called_with('GET',
                'https://api.lightspeedapp.com/API/Example/Endpoint.json',
                headers={'Authorization': 'Bearer ' + self.acct.access_token},
                params=None)

    def test_call_raises_on_400_and_401(self):
        with patch('timecardsite.services.request') as mocked_request:
            mocked_request.return_value.status_code = 400

            with self.assertRaises(services.InvalidToken):
                services._call('/API/Example.json', self.acct, None)

            mocked_request.return_value.status_code = 401

            with self.assertRaises(services.InvalidToken):
                services._call('/API/Example.json', self.acct, None)

    def test_call_returns_decoded_json_from_response(self):
        with patch('timecardsite.services.request') as mocked_request:
            mocked_request.return_value.status_code = 200
            mocked_response = {
                '@attributes': {
                    'count': '1'
                },
                'Account': {
                    'accountID': '12345',
                    'name': 'Test Store for API Testing',
                    'link': {
                        '@attributes': {
                            'href': '/API/Account/12345'
                        }
                    }
                }
            }
            mocked_request.return_value.json.return_value = mocked_response

            decoded_response = services._call('/API/Example.json', self.acct, params=None)

            self.assertEqual(decoded_response, mocked_response)

    def test_call_api_converts_datetimes_to_iso(self):
        test_date = pytz.timezone('America/Boise').localize(datetime(2021, 1, 1, 10, 58), is_dst=None)

        with patch('timecardsite.services._call') as mocked_call:
            # without query op
            next(services._call_api(f'API/Account/{self.acct.account_id}/EmployeeHours.json',
                                    self.acct,
                                    params={'checkIn': test_date}))

            mocked_call.assert_called_with(f'API/Account/{self.acct.account_id}/EmployeeHours.json',
                                           self.acct,
                                           {'checkIn': f'{test_date.isoformat()}'})

            # with query op
            next(services._call_api(f'API/Account/{self.acct.account_id}/EmployeeHours.json',
                                    self.acct,
                                    params={'checkIn': ['>', test_date]}))

            mocked_call.assert_called_with(f'API/Account/{self.acct.account_id}/EmployeeHours.json',
                                           self.acct,
                                           {'checkIn': f'>,{test_date.isoformat()}'})

    def test_call_api_refreshes_access_token_if_necessary(self):
        new_access_token = generate_random_token()

        with patch('timecardsite.services._refresh_access_token') as mocked_refresh, \
             patch('timecardsite.services._call') as mocked_call:

            mocked_refresh.return_value = new_access_token

            refreshed_call_response = {
                '@attributes': {
                    'count': '1'
                },
                'Account': {
                    'accountID': '12345',
                    'name': 'Test Store for API Testing',
                    'link': {
                        '@attributes': {
                            'href': '/API/Account/12345T'
                        }
                    }
                }
            }
            mocked_call.side_effect = [services.InvalidToken, refreshed_call_response]

            response_gen = services._call_api('/API/Account.json', self.acct)
            decoded_response = next(response_gen)

            self.assertEqual(new_access_token, self.acct.access_token)
            self.assertEqual(decoded_response, refreshed_call_response)

    def test_call_api_handles_pagination(self):
        with open('timecardsite/tests/pagination_test_file.json') as jf:
            mocked_responses = json.load(jf)

        with patch('timecardsite.services._call') as mocked_call:
            mocked_call.side_effect = mocked_responses

            test_date = pytz.timezone('America/Boise').localize(datetime(2021, 2, 1, 1), is_dst=None)
            shifts_since_february = services._call_api(f'API/Account/{self.acct.account_id}/EmployeeHours.json',
                                                       self.acct,
                                                       params={'checkIn': ['>', test_date]})

            self.assertTrue(isinstance(shifts_since_february, GeneratorType))

            first_page = next(shifts_since_february)
            self.assertEqual('0', first_page['@attributes']['offset'])
            self.assertEqual(first_page, mocked_responses[0])

            second_page = next(shifts_since_february)
            self.assertEqual('100', second_page['@attributes']['offset'])
            self.assertEqual(second_page, mocked_responses[1])

            third_page = next(shifts_since_february)
            self.assertEqual('200', third_page['@attributes']['offset'])
            self.assertEqual(third_page, mocked_responses[2])

            with self.assertRaises(StopIteration):
                next(shifts_since_february)

    def test_call_api_handles_query_ops(self):
        # the default operator is =
        # so if the user intends equals they don't pass in a query op
        # if they intend another op they pass in a list, with the op first
        with patch('timecardsite.services._call') as mocked_call:

            equals_params = {
                'shopID': '1'
            }
            next(services._call_api(f'API/Account/{self.acct.account_id}/Shop.json',
                                    self.acct,
                                    equals_params))

            mocked_call.assert_called_with(f'API/Account/{self.acct.account_id}/Shop.json',
                                           self.acct,
                                           {'shopID': '1'})

            less_than_params = {
                'shopID': ['<', '3']
            }

            next(services._call_api(f'API/Account/{self.acct.account_id}/Shop.json',
                                    self.acct,
                                    less_than_params))

            mocked_call.assert_called_with(f'API/Account/{self.acct.account_id}/Shop.json',
                                           self.acct,
                                           {'shopID': '<,3'})

    def test_get_tokens_POSTs_to_correct_URL_with_proper_payload(self):
        with patch('timecardsite.services.request') as mocked_request:
            code = generate_random_token()
            services.get_tokens(code)

            mocked_request.assert_called_with('POST',
                'https://cloud.lightspeedapp.com/oauth/access_token.php',
                data={
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET,
                    'code': code,
                    'grant_type': 'authorization_code'
                })
            
    def test_get_tokens_raises_on_400(self):
        with patch('timecardsite.services.request') as mocked_request:
            mocked_request.return_value.status_code = 400

            with self.assertRaises(services.InvalidGrant):
                services.get_tokens(generate_random_token())

    def test_get_tokens_actually_returns_tokens(self):
        with patch('timecardsite.services.request') as mocked_request:
            test_access_token = generate_random_token()
            test_refresh_token = generate_random_token()
            test_code = generate_random_token()

            mocked_request.return_value.json.return_value = {
                'access_token': test_access_token,
                'expires_in': 1800,
                'token_type': 'bearer',
                'scope': f'employee:all systemuserid:{generate_random_token(length=5)}',
                'refresh_token': test_refresh_token
            }

            access_token, refresh_token = services.get_tokens(test_code)

            self.assertEqual(access_token, test_access_token)
            self.assertEqual(refresh_token, test_refresh_token)

    def test_get_account_info_gets_account_info(self):
        with patch('timecardsite.services._call') as mocked_call, \
             patch('timecardsite.services.get_tokens') as mocked_get_tokens:

            test_access_token = generate_random_token()
            test_refresh_token = generate_random_token()
            mocked_get_tokens.return_value = (test_access_token, test_refresh_token)

            test_account_id = generate_random_token(5)
            test_account_data = {
                "@attributes": {
                    "count": "1"
                },
                "Account": {
                    "accountID": f'{test_account_id}',
                    "name": "Test Store for Testing",
                    "link": {
                        "@attributes": {
                            "href": f"/API/Account/{test_account_id}"
                        }
                    }
                }
            }
            mocked_call.return_value = test_account_data

            account_info = services.get_account_info(generate_random_token())
            expected_account_info = {
                'access_token': test_access_token,
                'refresh_token': test_refresh_token,
                'account_id': test_account_data['Account']['accountID'],
                'name': test_account_data['Account']['name']
            }
            self.assertEqual(account_info, expected_account_info)

    def test_get_account_info_returns_correct_access_code_if_refresh_required(self):
        with patch('timecardsite.services._refresh_access_token') as mocked_refresh, \
             patch('timecardsite.services._call') as mocked_call, \
             patch('timecardsite.services.get_tokens') as mocked_get_tokens:

            new_access_token = generate_random_token()
            mocked_refresh.return_value = new_access_token

            test_account_id = generate_random_token(5)
            test_account_data = {
                "@attributes": {
                    "count": "1"
                },
                "Account": {
                    "accountID": f'{test_account_id}',
                    "name": "Test Store for Testing",
                    "link": {
                        "@attributes": {
                            "href": f"/API/Account/{test_account_id}"
                        }
                    }
                }
            }

            mocked_call.side_effect = [services.InvalidToken, test_account_data]

            test_access_token = generate_random_token()
            test_refresh_token = generate_random_token()
            mocked_get_tokens.return_value = (test_access_token, test_refresh_token)

            account_info = services.get_account_info(generate_random_token())
            expected_account_info = {
                'access_token': new_access_token,
                'refresh_token': test_refresh_token,
                'account_id': test_account_data['Account']['accountID'],
                'name': test_account_data['Account']['name']
            }
            self.assertEqual(account_info, expected_account_info)

    
"""
    @patch('timecardsite.services.Plaw.get_tokens')
    @patch('timecardsite.services.Plaw.account')
    def test_get_initial_account_data(self, mocked_account, mocked_token):

        test_access_token = generate_random_token()
        test_refresh_token = generate_random_token()
        mocked_token.return_value = (test_access_token, test_refresh_token)

        test_account_id = generate_random_token(5)
        test_account_data = {
            "@attributes": {
                "count": "1"
            },
            "Account": {
                "accountID": f"{test_account_id}",
                "name": "Test Store for Testing",
                "link": {
                    "@attributes": {
                        "href": f"/API/Account/{test_account_id}"
                    }
                }
            }
        }
        mocked_account.return_value = test_account_data

        test_code = generate_random_token()
        initial_account_data = services.get_initial_account_data(test_code)

        self.assertEqual(initial_account_data['access_token'], test_access_token)
        self.assertEqual(initial_account_data['refresh_token'], test_refresh_token)
        self.assertEqual(initial_account_data['account_id'], test_account_id)
        self.assertEqual(initial_account_data['name'], 'Test Store for Testing')

        mocked_token.assert_called_with(test_code)

    @patch('timecardsite.services.next')
    def test_get_employee_ids_and_names(self, mocked_next):
        with open('timecardsite/tests/employee_test_file.json') as jf:
            test_employee_info = json.load(jf)[0]

        mocked_next.return_value = test_employee_info

        employee_list = services.get_employee_ids_and_names(generate_random_account())

        self.assertTrue(isinstance(employee_list, list))
        self.assertTrue(isinstance(employee_list[0], tuple))
        self.assertEqual(len(employee_list[0]), 2)

    @patch('timecardsite.services.next')
    def test_get_employee_ids_names_emails(self, mocked_next):
        with open('timecardsite/tests/employee_test_file.json') as jf:
            test_employee_info = json.load(jf)[1]

        mocked_next.return_value = test_employee_info

        employee_list = services.get_employee_ids_names_and_emails(generate_random_account())

        self.assertTrue(isinstance(employee_list, list))
        self.assertTrue(isinstance(employee_list[0], dict))
        self.assertEqual(len(employee_list), 10)
        self.assertEqual(employee_list[1]['email'], None)


    @patch('timecardsite.services.map_shop_ids_to_names')
    @patch('timecardsite.services.Plaw.employee_hours')
    def test_get_shifts_and_totals_for_given_employee_correctly_calls_api(self, mocked_employee_hours, mocked_map):
        services.get_shifts_and_totals_for_given_employee(
            generate_random_account(),
            '63',
            start_date=(date.today() - timedelta(weeks=1)),
            end_date=date.today()
        )

        expected_start = datetime.combine(
            date.today() - timedelta(weeks=1),
            datetime.min.time()
        )
        expected_end = datetime.combine(
            date.today(), datetime.max.time()
        )
        expected_start = pytz.timezone('America/Boise').localize(expected_start, is_dst=None)
        expected_end = pytz.timezone('America/Boise').localize(expected_end, is_dst=None)

        expected_params = {
            'checkIn': ['><', expected_start, expected_end],
            'orderby': 'employeeHoursID',
            'orderby_desc': '1',
            'employeeID': '63'
        }

        mocked_employee_hours.assert_called_with(expected_params)

    @patch('timecardsite.services.map_shop_ids_to_names')
    @patch('timecardsite.services.Plaw.employee_hours')
    def test_get_shifts_and_totals_for_given_employee_converts_api_response_to_shifts_and_totals(self, mocked_employee_hours, mocked_map):
        self.maxDiff = None

        with open('timecardsite/tests/employee_hours_test_file.json') as jf:
            test_api_response = json.load(jf)

        mocked_employee_hours.return_value = iter([test_api_response])

        mocked_map.return_value = {
            '1': 'The Wildflower-Hailey',
            '2': 'The Wildflower-Ketchum',
            '9': 'Inventory Compiler'
        }

        timecard = services.get_shifts_and_totals_for_given_employee(
            generate_random_account(),
            '63',
            start_date=date(2021, 2, 26),
            end_date=date(2021, 2, 26)
        )

        expected_response = {
            'shifts': [
                {
                    'check_in': datetime.fromisoformat('2021-02-26T18:10:19+00:00'),
                    'check_out': datetime.fromisoformat('2021-02-26T19:06:21+00:00'),
                    'shift_time': 0.9338888888888889,
                    'shop': 'The Wildflower-Ketchum'
                }
            ],
            'totals': {
                'total': 0.9338888888888889,
                'The Wildflower-Ketchum': 0.9338888888888889
            }
        }

        self.assertEqual(timecard, expected_response)

    @patch('timecardsite.services.map_employee_ids_to_names')
    @patch('timecardsite.services.map_shop_ids_to_names')
    @patch('timecardsite.services.Plaw.employee_hours')
    def test_get_shifts_and_totals_correctly_calls_api(self, mocked_employee_hours, mocked_map, mocked_employee):
        services.get_shifts_and_totals(
            generate_random_account(),
            start_date=(date.today() - timedelta(weeks=1)),
            end_date=date.today()
        )

        expected_start = datetime.combine(
            date.today() - timedelta(weeks=1),
            datetime.min.time()
        )
        expected_end = datetime.combine(
            date.today(), datetime.max.time()
        )
        expected_start = pytz.timezone('America/Boise').localize(expected_start, is_dst=None)
        expected_end = pytz.timezone('America/Boise').localize(expected_end, is_dst=None)

        expected_params = {
            'checkIn': ['><', expected_start, expected_end],
            'orderby': 'employeeHoursID',
            'orderby_desc': '1',
        }

        mocked_employee_hours.assert_called_with(expected_params)

"""


