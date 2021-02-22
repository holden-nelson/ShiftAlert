import json
from datetime import date, datetime, timedelta
import pytz

from django.test import TestCase
from unittest.mock import patch

from timecardsite import services
from timecardsite.tests import generate_random_token, generate_random_account

class ServicesTests(TestCase):

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
    def test_get_employees(self, mocked_next):
        with open('timecardsite/tests/employee_test_file.json') as jf:
            test_employee_info = json.load(jf)[0]

        mocked_next.return_value = test_employee_info

        employee_list = services.get_employee_ids_and_names(generate_random_account())

        self.assertTrue(isinstance(employee_list, list))
        self.assertTrue(isinstance(employee_list[0], tuple))
        self.assertEqual(len(employee_list[0]), 2)

    @patch('timecardsite.services.Plaw.employee_hours')
    def test_get_shifts_and_totals_for_given_employee_correctly_calls_api(self, mocked_employee_hours):
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

    @patch('timecardsite.services.next')
    @patch('timecardsite.services.Plaw.employee_hours')
    def test_get_shifts_and_totals_for_given_employee_converts_api_response_to_shifts_and_totals(self, mocked_employee_hours, mocked_next):
        self.maxDiff = None

        with open('timecardsite/tests/employee_hours_test_file.json') as jf:
            test_api_response = json.load(jf)

        mocked_employee_hours.return_value = iter([test_api_response])

        mocked_next.return_value = {
            'Shop': {
                'name': 'The Wildflower-Ketchum'
            }
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



