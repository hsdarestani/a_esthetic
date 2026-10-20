from django.contrib.auth.models import User, Group
from django.test import TestCase

from platform_app.mobile_api import _token_for
from platform_app.models import UserProfile


class DoctorIdentityTests(TestCase):
    def test_verified_staff_doctor_has_identity_but_no_admin_access(self):
        user = User.objects.create_user(
            'doctor-qamar', password='test-password', first_name='Qamar',
            last_name='Hameed', is_staff=True,
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = 'specialist'
        profile.save(update_fields=['role'])
        user.groups.add(Group.objects.get_or_create(name='aesthetic_qamar_doctor')[0])
        auth = {'HTTP_AUTHORIZATION': 'Bearer ' + _token_for(user)}
        response = self.client.get('/api/mobile/doctor/', **auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['doctor']['name'], 'Qamar Hameed')
        self.assertEqual(self.client.get('/api/mobile/admin/', **auth).status_code, 403)
        self.assertEqual(self.client.get('/api/mobile/admin/customers/', **auth).status_code, 403)

    def test_self_registered_identity_is_not_promoted(self):
        user = User.objects.create_user('qamar-customer', password='test-password',
            first_name='Qamar', last_name='Hameed')
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = 'specialist'
        profile.save(update_fields=['role'])
        response = self.client.get('/api/mobile/doctor/',
            HTTP_AUTHORIZATION='Bearer ' + _token_for(user))
        self.assertEqual(response.status_code, 403)
