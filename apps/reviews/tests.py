from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status as http_status
from django.contrib.auth import get_user_model

from apps.reviews.models import Review
from apps.clinics.models import Clinic

User = get_user_model()


class ReviewRespondTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='rev_admin@t.com', first_name='A', last_name='B',
            password='x12345678A!', user_type='super_admin',
        )
        self.patient = User.objects.create_user(
            email='rev_pat@t.com', first_name='P', last_name='X',
            password='x12345678A!', user_type='patient',
        )
        self.clinic = Clinic.objects.create(
            name='Test Clinic',
            slug='test-clinic',
            email='clinic@t.com',
            phone='+5511999999999',
            street='Rua A',
            number='10',
            neighborhood='Centro',
            city='Sao Paulo',
            state='SP',
            zip_code='01000-000',
        )
        self.review = Review.objects.create(
            patient=self.patient, review_type='clinic', clinic=self.clinic,
            rating=4, comment='ok', status='approved',
        )

    def test_admin_can_respond(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            f'/api/v1/reviews/{self.review.id}/respond/',
            {'response': 'Gracias!'}, format='json'
        )
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.review.refresh_from_db()
        self.assertEqual(self.review.response, 'Gracias!')
        self.assertIsNotNone(self.review.response_date)

    def test_patient_cannot_respond(self):
        self.client.force_authenticate(self.patient)
        resp = self.client.post(
            f'/api/v1/reviews/{self.review.id}/respond/',
            {'response': 'no'}, format='json'
        )
        self.assertEqual(resp.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_empty_response_rejected(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            f'/api/v1/reviews/{self.review.id}/respond/',
            {'response': '  '}, format='json'
        )
        self.assertEqual(resp.status_code, http_status.HTTP_400_BAD_REQUEST)
