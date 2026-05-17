import csv
import io
from datetime import datetime

from django.http import StreamingHttpResponse
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Appointment
from .serializers import AppointmentListSerializer


class ReportsAppointmentsView(APIView):
    """GET /reports/appointments/?date_from=&date_to=&format=json|csv

    Permisos:
    - super_admin: puede exportar cualquier clínica
    - clinic_admin: puede exportar citas de sus clínicas
    - doctor: puede ver JSON de sus citas
    - patient: solo JSON de sus propias citas

    CSV está restringido a super_admin y clinic_admin.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        fmt = request.query_params.get('format', 'json').lower()

        qs = Appointment.objects.all().select_related('clinic', 'doctor__user', 'patient')

        # Apply role-based filtering
        if user.user_type == 'super_admin':
            pass
        elif user.user_type == 'clinic_admin':
            qs = qs.filter(clinic__admins=user)
        elif user.user_type == 'doctor':
            qs = qs.filter(doctor__user=user)
        elif user.user_type == 'patient':
            qs = qs.filter(patient=user)
        else:
            return Response({'detail': 'No tienes permiso.'}, status=status.HTTP_403_FORBIDDEN)

        # Date filters (parse YYYY-MM-DD)
        try:
            if date_from:
                date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
                qs = qs.filter(date__gte=date_from_parsed)
            if date_to:
                date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
                qs = qs.filter(date__lte=date_to_parsed)
        except ValueError:
            return Response({'detail': 'Formato de fecha inválido. Usa YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        qs = qs.order_by('date', 'start_time')

        # CSV restricted
        if fmt == 'csv':
            if user.user_type not in ['super_admin', 'clinic_admin']:
                return Response({'detail': 'CSV export solo disponible para super_admin o clinic_admin.'}, status=status.HTTP_403_FORBIDDEN)

            filename = f"appointments_{slugify(date_from or 'all')}_{slugify(date_to or 'all')}.csv"

            def row_generator(queryset):
                """Generator that yields CSV bytes in streaming fashion."""
                buffer = io.StringIO()
                writer = csv.writer(buffer)

                # Write header + BOM for Excel compatibility
                writer.writerow(['appointment_number', 'date', 'start_time', 'clinic', 'doctor', 'patient_email', 'status', 'payment_amount'])
                data = '\ufeff' + buffer.getvalue()
                yield data.encode('utf-8')
                buffer.seek(0)
                buffer.truncate(0)

                # Iterate using iterator() to avoid loading all rows in memory
                for appt in queryset.iterator():
                    payment_amount = ''
                    if hasattr(appt, 'payment') and appt.payment is not None:
                        payment_amount = str(getattr(appt.payment, 'amount', ''))

                    doctor_name = ''
                    try:
                        doctor_name = appt.doctor.user.get_full_name()
                    except Exception:
                        doctor_name = ''

                    row = [
                        appt.appointment_number,
                        appt.date.isoformat() if appt.date else '',
                        appt.start_time.strftime('%H:%M') if appt.start_time else '',
                        appt.clinic.name if appt.clinic else '',
                        doctor_name,
                        appt.patient.email if appt.patient else '',
                        appt.status,
                        payment_amount,
                    ]

                    writer.writerow(row)
                    yield buffer.getvalue().encode('utf-8')
                    buffer.seek(0)
                    buffer.truncate(0)

            response = StreamingHttpResponse(row_generator(qs), content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        # JSON response
        serializer = AppointmentListSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)
