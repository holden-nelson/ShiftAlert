import random, string
import json
from datetime import datetime
import pytz

from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from invitations.utils import get_invitation_model

import timecardsite.services as services
from timecardsite.models import Account, Profile

# Helper
def generate_random_token(length=16):
    return ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase
                                 + string.digits) for _ in range(length))

@patch('timecardsite.services.requests.request')
class ServicesTests(TestCase):

    def test_get_access_code(self, mock_request):
        # Configure mock to return a response with:
        #   - 200 ok status code
        #   - JSON with codes etc.
        mock_request.return_value.status_code = 200

        mock_response_json = {
            'access_token': generate_random_token(),
            'expires in': 3600,
            'token_type': 'bearer',
            'scope': 'employee:admin_employees systemuserid:152663',
            'refresh_token': generate_random_token()
        }
        mock_request.return_value.json.return_value = mock_response_json

        tokens = services.get_access_token(generate_random_token())

        self.assertIn('access_token', tokens)
        self.assertIn('refresh_token', tokens)
        self.assertIsNotNone(tokens['access_token'])
        self.assertIsNotNone(tokens['refresh_token'])

    def test_refresh_access_token(self, mock_request):
        # Configure mock to return a response with
        #   - 200 ok
        #   - JSON with codes etc.
        mock_request.return_value.status_code = 200

        mock_response_json = {
            'access_token': generate_random_token(),
            'expires_in': 3600,
            'token_type': 'bearer',
            'scope': 'employee:all systemuserid:152663'
        }
        mock_request.return_value.json.return_value = mock_response_json

        access_token = services.refresh_access_token(generate_random_token())

        self.assertIsNotNone(access_token)

    def test_refresh_access_token_handles_400_response(self, mock_request):
        # Configure mock to return a response with
        #   - 400 Bad Request
        mock_request.return_value.status_code = 400

        with self.assertRaises(services.InvalidGrant):
            access_token = services.refresh_access_token(generate_random_token())

    def test_get_account_info(self, mock_request):
        # Configure mock to return a response with
        #   - 200 ok
        #   - JSON with account ID, name
        mock_request.return_value.status_code = 200
        mock_response_json = {
            '@attributes': {
                'count': '1',
            },
            'Account': {
                'accountID': generate_random_token(length=6),
                'name': 'Domestic Grasses Boutique and Coffee Shop'
            },
        }

        mock_request.return_value.json.return_value = mock_response_json

        account_info = services.get_account_info(generate_random_token())

        self.assertIn('account_id', account_info)
        self.assertIn('name', account_info)
        self.assertIsNotNone(account_info['account_id'])
        self.assertIsNotNone(account_info['name'])

    def test_get_account_info_handles_401_response(self, mock_request):
        # Configure mock to return a response with
        #   - 401 Unauthorized
        mock_request.return_value.status_code = 401

        with self.assertRaises(services.InvalidToken):
            services.get_account_info(generate_random_token())

    def test_get_employee_info(self, mock_request):
        # Configure mock to return a response with
        #   - 200 ok
        #   - JSON with employee info
        mock_request.return_value.status_code = 200
        with open('timecardsite/tests/employees.json') as employee_f:
            mock_response_json = json.load(employee_f)
        mock_request.return_value.json.return_value = mock_response_json

        employees = services.get_employees_info(
            generate_random_token(length=5), # account ID
            generate_random_token() # access token
        )

        self.assertIn('63', employees) # look for a known employee ID
        self.assertEquals(employees['39']['name'], 'Shanti LaRue')
        self.assertEquals(employees['1']['email'], 'thewildfloweridaho@gmail.com')

    def test_get_employee_info_handles_401_response(self, mock_request):
        # Configure mock with
        #   - 401 Unauthorized
        mock_request.return_value.status_code = 401

        with self.assertRaises(services.InvalidToken):
            services.get_employees_info(
                generate_random_token(length=5),
                generate_random_token()
            )

    def test_get_employee_hours(self, mock_request):
        # Configure mock to return a response with
        #   - 200 ok
        #   - JSON with employeeHours info
        mock_request.return_value.status_code = 200
        with open('timecardsite/tests/employeeHours.json') as employeeHours_f:
            mock_response_json = json.load(employeeHours_f)
        mock_request.return_value.json.return_value = mock_response_json

        # build tz aware datetime objects
        naive_start_date = datetime(2021,2,1,0,0,0)
        naive_end_date = datetime(2021,2,28,23,59,0)
        start_date = pytz.timezone('US/Mountain').localize(naive_start_date, is_dst=None)
        end_date = pytz.timezone('US/Mountain').localize(naive_end_date, is_dst=None)

        shifts = services.get_employee_hours(
            employee_id='63',
            start_date=start_date,
            end_date=end_date,
            account_id=generate_random_token(length=5),
            access_token=generate_random_token()
        )

        self.assertIsNotNone(shifts)
        self.assertEqual(25, len(shifts))
        self.assertEqual(shifts[0]['check_out'], None)

    def test_get_employee_hours_handles_401_response(self, mock_request):
        # Configure mock with
        #   - 401 Unauthorized
        mock_request.return_value.status_code = 401

        with self.assertRaises(services.InvalidToken):
            services.get_employee_hours(
                employee_id='63',
                start_date=datetime.now(),
                end_date=datetime.now(),
                account_id=generate_random_token(length=5),
                access_token=generate_random_token()
            )

    # TODO test pagination functionality


class ViewsTests(TestCase):
    def setUp(self):
        # these are used to mock responses in auth view test
        self.tokens = {
            'access_token': generate_random_token(),
            'refresh_token': generate_random_token()
        }

        self.account_info = {
            'account_id': generate_random_token(length=5),
            'name': 'Domestic Grasses Boutique and Coffee Shop'
        }
        self.code = generate_random_token()

        # used for mocking in invite test
        self.employees = {'1': {'name': 'Lisa Patterson', 'email': 'thewildfloweridaho@gmail.com'},
                          '39': {'name': 'Shanti LaRue', 'email': ''},
                          '48': {'name': 'Hattie Patterson', 'email': ''},
                          '55': {'name': 'Kathy Lederman', 'email': 'kathymlederman@aol.com'},
                          '56': {'name': 'Emily Todd', 'email': ''},
                          '62': {'name': 'Sofia Calcagno', 'email': 'fiasoco123@gmail.com'},
                          '63': {'name': 'Elizabeth Carter', 'email': 'yellowannie@gmail.com'},
                          '64': {'name': 'Christy Avison', 'email': ''},
                          '65': {'name': 'Kerry Guggenheim', 'email': 'kguggy@hotmail.com'},
                          '67': {'name': 'Kary Kjesbo', 'email': 'kary@karykjesbodesigns.com'}
        }

        # user for the auth test - also has no profile
        self.unauthed_user = get_user_model().objects.create_user(
            email = 'unauthed@user.com',
            password = 'examplepassword'
        )

        # user with manager permissions and profile
        self.manager_user = get_user_model().objects.create_user(
            email = 'manager@user.com',
            password = 'managerpassword'
        )
        self.manager_account = Account(
            account_id = generate_random_token(length=5),
            access_token = generate_random_token(),
            refresh_token = generate_random_token(),
            name = 'Managed Store for Managers'
        )
        self.manager_account.save()
        self.manager_profile = Profile(
            user = self.manager_user,
            account = self.manager_account,
            role = 'mgr'
        )
        self.manager_profile.save()

        # user with employee permissions and profile
        self.employee_user = get_user_model().objects.create_user(
            email = 'employee@user.com',
            password = 'employeepassword'
        )
        self.employee_account = Account(
            account_id=generate_random_token(length=5),
            access_token=generate_random_token(),
            refresh_token=generate_random_token(),
            name='Employee Store for Employees'
        )
        self.employee_account.save()
        self.employee_profile = Profile(
            user=self.employee_user,
            account=self.employee_account,
            role='emp'
        )
        self.employee_profile.save()


    def test_auth_view(self):

        self.client.login(email='unauthed@user.com', password='examplepassword')

        # Mock both get_access_token and get_account_info
        with patch('timecardsite.views.services') as mocked_services:
            mocked_services.get_access_token.return_value = self.tokens
            mocked_services.get_access_token.__getitem__.side_effect = self.tokens.__getitem__
            mocked_services.get_account_info.return_value = self.account_info
            mocked_services.get_account_info.__getitem__.side_effect = self.account_info.__getitem__
            response = self.client.get(f'/auth/?code={self.code}', follow=True)

        # test account creation
        self.assertTrue(Account.objects.filter(account_id=self.account_info['account_id']).exists())
        new_account = self.unauthed_user.profile.account
        self.assertEqual(new_account.account_id, self.account_info['account_id'])
        self.assertEqual(new_account.name, self.account_info['name'])
        self.assertEqual(new_account.access_token, self.tokens['access_token'])
        self.assertEqual(new_account.refresh_token, self.tokens['refresh_token'])

        # test profile creation
        self.assertTrue(Profile.objects.filter(user=self.unauthed_user).exists())
        new_profile = self.unauthed_user.profile
        self.assertEqual(self.unauthed_user.id, new_profile.user_id)
        self.assertEqual(new_account.account_id, new_profile.account_id)
        self.assertEqual(new_profile.role, 'mgr')

        # test onboarding redirect
        self.assertRedirects(response, reverse('onboard'))

    def test_post_login_view(self):
        # no profile should redirect to connect page
        self.client.login(email='unauthed@user.com', password='examplepassword')
        response = self.client.get('/post_login/')
        self.assertRedirects(response, reverse('connect'))

        # existing profile, not onboarded, manager user
        self.client.login(email='manager@user.com', password='managerpassword')
        response = self.client.get('/post_login/')
        self.assertRedirects(response, reverse('onboard'))

        # existing profile, onboarded, manager user
        self.manager_account.is_onboarded = True
        self.manager_account.save()
        response = self.client.get('/post_login/')
        self.assertRedirects(response, reverse('manager'))

        # existing profile, employee user
        self.client.login(email='employee@user.com', password='employeepassword')
        response = self.client.get('/post_login/')
        self.assertRedirects(response, reverse('employee'))


    def test_invite_view(self):
        # todo test invited employees not included in page layout
        # todo test only available for managers
        # todo test id feature I added
        self.client.login(email='manager@user.com', password='managerpassword')
        with patch('timecardsite.views.services') as mocked_services:
            mocked_services.get_employees_info.return_value = self.employees
            mocked_services.get_employees_info.__getitem__.side_effect = self.employees.__getitem__
            response = self.client.get('/invite/?name=Holden Nelson&email=example@email.com&id=99')

        # test that it actually made the invite
        Invitations = get_invitation_model()
        self.assertEqual(Invitations.objects.count(), 1)
        self.assertEqual(Invitations.objects.first().email, 'example@email.com')

    def test_employee_dash_view(self):
        pass



