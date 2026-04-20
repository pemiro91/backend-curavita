from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()


class AdminCreateUserTests(APITestCase):
    def setUp(self):
        self.super_admin = User.objects.create_user(
            email='admin@test.com',
            first_name='Admin',
            last_name='Root',
            password='StrongPass123!',
            user_type='super_admin',
        )
        self.patient = User.objects.create_user(
            email='patient@test.com',
            first_name='Pat',
            last_name='User',
            password='StrongPass123!',
            user_type='patient',
        )

    def test_super_admin_can_create_doctor_user(self):
        self.client.force_authenticate(self.super_admin)
        payload = {
            'email': 'newdoc@test.com',
            'first_name': 'New',
            'last_name': 'Doctor',
            'password': 'TempDoc1234!',
            'user_type': 'doctor',
            'phone': '',
        }
        resp = self.client.post('/api/v1/auth/users/admin-create/', payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email='newdoc@test.com', user_type='doctor').exists())

    def test_patient_cannot_admin_create(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.post('/api/v1/auth/users/admin-create/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_filter_users_by_type_requires_admin(self):
        self.client.force_authenticate(self.super_admin)
        resp = self.client.get('/api/v1/auth/users/?user_type=patient')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        emails = [u['email'] for u in resp.data.get('results', resp.data)]
        self.assertIn('patient@test.com', emails)

    def test_has_doctor_profile_false_returns_users_without_profile(self):
        self.client.force_authenticate(self.super_admin)
        resp = self.client.get('/api/v1/auth/users/?user_type=patient&has_doctor_profile=false')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        emails = [u['email'] for u in resp.data.get('results', resp.data)]
        self.assertIn('patient@test.com', emails)
