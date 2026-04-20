from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.appointments.models import Appointment
from apps.clinics.models import Clinic, Doctor
from apps.notifications.models import Notification
from apps.services.models import Service, Specialty

User = get_user_model()


class AppointmentReviewRequestSignalTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email='p_sig@t.com',
            first_name='P',
            last_name='P',
            password='x12345678A!',
            user_type='patient',
            phone='+5511999999991',
        )
        self.doc_user = User.objects.create_user(
            email='d_sig@t.com',
            first_name='D',
            last_name='D',
            password='x12345678A!',
            user_type='doctor',
            phone='+5511999999992',
        )
        self.clinic = Clinic.objects.create(
            name='Test Clinic',
            slug='test-clinic',
            email='clinic@t.com',
            phone='+5511999999990',
            street='Rua Teste',
            number='100',
            neighborhood='Centro',
            city='Sao Paulo',
            state='SP',
            zip_code='01000-000',
        )
        self.specialty = Specialty.objects.create(
            name='General Medicine',
            slug='general-medicine',
        )
        self.doctor = Doctor.objects.create(
            user=self.doc_user,
            clinic=self.clinic,
            license_number='L1',
            specialty=self.specialty,
        )
        self.service = Service.objects.create(
            clinic=self.clinic,
            specialty=self.specialty,
            name='Consulta',
            price=100,
            duration_minutes=30,
        )

    def test_review_request_notification_on_completion(self):
        appt = Appointment.objects.create(
            patient=self.patient,
            clinic=self.clinic,
            doctor=self.doctor,
            service=self.service,
            date=date.today() + timedelta(days=1),
            start_time=time(10, 0),
            status='confirmed',
        )
        Notification.objects.filter(recipient=self.patient).delete()
        appt.status = 'completed'
        appt.save()

        notif = Notification.objects.filter(
            recipient=self.patient, notification_type='review_request'
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn(str(appt.id), notif.action_url)
        self.assertTrue(notif.action_url.startswith('/reviews/new/'))
