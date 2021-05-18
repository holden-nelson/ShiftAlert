from django.test import TestCase
from unittest.mock import patch
from django.shortcuts import reverse
from django.contrib.auth import get_user_model

from invitations.utils import get_invitation_model

from timecardsite.tests import generate_random_token
from timecardsite.models import Account, Profile, InvitationMeta

class ViewsTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        # create some user accounts for tests that require users to be a
        # certain level of authenticated

        # for auth test - no account or profile
        cls.unauthed_user = get_user_model().objects.create_user(
            email='unauthed@user.com',
            password='unauthedpassword'
        )

        # manager user - onboarded
        cls.manager_user = get_user_model().objects.create_user(
            email='manager@user.com',
            password='managerpassword'
        )

        cls.manager_account = Account(
            account_id=generate_random_token(5),
            access_token=generate_random_token(),
            refresh_token=generate_random_token(),
            name='Manager Store for Managers',
            timezone='America/Boise',
            is_onboarded=True
        )
        cls.manager_account.save()

        cls.manager_profile = Profile(
            user=cls.manager_user,
            account=cls.manager_account,
            role='mgr',
            employee_id=generate_random_token(5),
            name='Jane Doe'
        )
        cls.manager_profile.save()

        # employee user
        cls.employee_user = get_user_model().objects.create_user(
            email='employee@user.com',
            password='employeepassword'
        )

        cls.employee_account = Account(
            account_id=generate_random_token(5),
            access_token=generate_random_token(),
            refresh_token=generate_random_token(),
            name='Test Store for Employees'
        )
        cls.employee_account.save()

        cls.employee_profile = Profile(
            user=cls.employee_user,
            account=cls.employee_account,
            role='emp'
        )
        cls.employee_profile.save()

    def test_auth_view_404s_when_there_is_no_code(self):
        self.client.login(email='unauthed@user.com', password='unauthedpassword')

        response = self.client.get('/auth/')
        self.assertEqual(response.status_code, 404)

    @patch('timecardsite.views.services.get_initial_account_data')
    def test_auth_view_passes_code_to_service_function(self, mocked_initial):
        code = generate_random_token()
        user_id = get_user_model().objects.get(email='unauthed@user.com').id

        self.client.login(email='unauthed@user.com', password='unauthedpassword')
        self.client.get(f'/auth/?code={code}&state={user_id}')

        mocked_initial.assert_called_with(code)

    @patch('timecardsite.views.services.get_initial_account_data')
    def test_auth_view_creates_new_account_object(self, mocked_initial):
        test_initial = {
            'access_token': generate_random_token(),
            'refresh_token': generate_random_token(),
            'account_id': generate_random_token(5),
            'name': 'Test Store for Testing'
        }
        mocked_initial.return_value = test_initial

        user_id = get_user_model().objects.get(email='unauthed@user.com').id

        self.client.login(email='unauthed@user.com', password='unauthedpassword')
        self.client.get(f'/auth/?code={generate_random_token()}&state={user_id}')

        self.assertTrue(Account.objects.filter(account_id=test_initial['account_id']).exists())
        new_account = Account.objects.get(account_id=test_initial['account_id'])
        self.assertEqual(new_account.name, test_initial['name'])
        self.assertEqual(new_account.access_token, test_initial['access_token'])
        self.assertEqual(new_account.refresh_token, test_initial['refresh_token'])

    @patch('timecardsite.views.services.get_initial_account_data')
    def test_auth_view_creates_new_manager_profile(self, mocked_initial):
        test_initial = {
            'access_token': generate_random_token(),
            'refresh_token': generate_random_token(),
            'account_id': generate_random_token(5),
            'name': 'Test Store for Testing'
        }
        mocked_initial.return_value = test_initial

        user_id = get_user_model().objects.get(email='unauthed@user.com').id

        self.client.login(email='unauthed@user.com', password='unauthedpassword')
        self.client.get(f'/auth/?code={generate_random_token()}&state={user_id}')

        self.assertTrue(Profile.objects.filter(account_id=test_initial['account_id']).exists())
        new_profile = Profile.objects.get(account_id=test_initial['account_id'])
        self.assertEqual(new_profile.role, 'mgr')


    @patch('timecardsite.views.services.get_initial_account_data')
    def test_auth_view_redirects_to_post_login(self, mocked_initial):
        user_id = get_user_model().objects.get(email='unauthed@user.com').id

        self.client.login(email='unauthed@user.com', password='unauthedpassword')
        response = self.client.get(f'/auth/?code={generate_random_token()}&state={user_id}')

        self.assertRedirects(response, reverse('post_login'), fetch_redirect_response=False)

    def test_post_login_redirects_to_timecard_view_for_employee(self):
        self.client.login(email='employee@user.com', password='employeepassword')
        response = self.client.get(reverse('post_login'))

        self.assertRedirects(response, reverse('timecard'), fetch_redirect_response=False)

    @patch('timecardsite.views.services.get_initial_account_data')
    def test_post_login_redirects_to_onboard_view_for_new_user(self, mocked_initial):
        test_initial = {
            'access_token': generate_random_token(),
            'refresh_token': generate_random_token(),
            'account_id': generate_random_token(5),
            'name': 'Test Store for Testing'
        }
        mocked_initial.return_value = test_initial

        user_id = get_user_model().objects.get(email='unauthed@user.com').id

        self.client.login(email='unauthed@user.com', password='unauthedpassword')
        self.client.get(f'/auth/?code={generate_random_token()}&state={user_id}', follow=False)
        response = self.client.get('/post_login/')

        self.assertRedirects(response, reverse('onboard'), fetch_redirect_response=False)

    def test_post_login_view_redirects_to_aggregate_view_for_manager(self):
        self.client.login(email='manager@user.com', password='managerpassword')
        response = self.client.get(reverse('post_login'))

        self.assertRedirects(response, reverse('aggregate'))

    def test_post_login_view_redirects_to_connect_view_for_unconnected_user(self):
        self.client.login(email='unauthed@user.com', password='unauthedpassword')
        response = self.client.get('/post_login/')

        self.assertRedirects(response, reverse('connect'))

    @patch('timecardsite.views.OnboardingForm')
    def test_onboarding_view_saves_account_and_profile_info_to_db_on_post(self, mocked_form):
        test_cleaned_data = {
            'timezone': 'America/Boise',
            'employees': '11,Joe Manager',
        }

        mocked_form.return_value.is_valid.return_value = True
        mocked_form.return_value.cleaned_data = test_cleaned_data

        self.client.login(email='manager@user.com', password='managerpassword')
        response = self.client.post('/onboard/')

        id, name = test_cleaned_data['employees'].split(',')

        self.assertEqual(response.wsgi_request.user.profile.account.timezone, test_cleaned_data['timezone'])
        self.assertEqual(response.wsgi_request.user.profile.employee_id, id)
        self.assertEqual(response.wsgi_request.user.profile.name, name)

    @patch('timecardsite.views.OnboardingForm')
    def test_onboarding_view_redirects_to_manager_aggregate_on_valid_form_submission(self, mocked_form):
        test_cleaned_data = {
            'timezone': 'America/Boise',
            'employees': '11,Joe Manager',
        }

        mocked_form.return_value.is_valid.return_value = True
        mocked_form.return_value.cleaned_data = test_cleaned_data

        self.client.login(email='manager@user.com', password='managerpassword')
        response = self.client.post('/onboard/')

        self.assertRedirects(response, reverse('aggregate'))

    @patch('timecardsite.views.OnboardingForm')
    def test_onboarding_view_redirects_to_name_view_on_non_employee_selection(self, mocked_form):
        test_cleaned_data = {
            'timezone': 'America/Boise',
            'employees': '00',
        }

        mocked_form.return_value.is_valid.return_value = True
        mocked_form.return_value.cleaned_data = test_cleaned_data

        self.client.login(email='manager@user.com', password='managerpassword')
        response = self.client.post('/onboard/')

        self.assertRedirects(response, reverse('name'))

    @patch('timecardsite.views.NameForm')
    def test_name_view_saves_given_name_to_db(self, mocked_form):
        test_cleaned_data = {
            'name': 'Joe Administrator'
        }

        mocked_form.return_value.is_valid.return_value = True
        mocked_form.return_value.cleaned_data = test_cleaned_data

        self.client.login(email='manager@user.com', password='managerpassword')
        response = self.client.post('/name/')

        self.assertEqual(response.wsgi_request.user.profile.name, test_cleaned_data['name'])

    @patch('timecardsite.views.NameForm')
    def test_name_view_redirects_to_aggregate_view(self, mocked_form):
        test_cleaned_data = {
            'name': 'Joe Administrator'
        }

        mocked_form.return_value.is_valid.return_value = True
        mocked_form.return_value.cleaned_data = test_cleaned_data

        self.client.login(email='manager@user.com', password='managerpassword')
        response = self.client.post('/name/')

        self.assertRedirects(response, reverse('aggregate'))

    def test_invite_view_redirects_on_post(self):
        self.client.login(email='manager@user.com', password='managerpassword')

        response = self.client.post('/invite/',
                                    data={'invites': '67,Test User,test@user.com'})

        self.assertRedirects(response, '/invite/', fetch_redirect_response=False)

    def test_invite_view_saves_invite_to_db(self):
        self.client.login(email='manager@user.com', password='managerpassword')

        response = self.client.post('/invite/',
                                    data={'invites': '67,Test User,test@user.com'})

        Invitation = get_invitation_model()
        self.assertEqual(Invitation.objects.count(), 1)
        self.assertEqual(Invitation.objects.first().email, 'test@user.com')

    def test_invite_view_saves_invite_meta_to_db(self):
        self.client.login(email='manager@user.com', password='managerpassword')

        response = self.client.post('/invite/',
                                    data={'invites': '67,Test User,test@user.com'})

        self.assertEqual(InvitationMeta.objects.count(), 1)
        self.assertEqual(InvitationMeta.objects.first().invite, get_invitation_model().objects.first())
        self.assertEqual(InvitationMeta.objects.first().employee_id, '67')
        self.assertEqual(InvitationMeta.objects.first().name, 'Test User')

    def test_invite_view_creates_multiple_invites_if_necessary(self):
        self.client.login(email='manager@user.com', password='managerpassword')

        response = self.client.post('/invite/', data={'invites': [
                                        '67,Test User,test@user.com',
                                        '73,Another User,another@user.com'
                                        ]})

        self.assertEqual(get_invitation_model().objects.count(), 2)
        self.assertEqual(InvitationMeta.objects.count(), 2)









