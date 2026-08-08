from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import Appointment, Service, StaffMember


class AppointmentForm(forms.ModelForm):
    starts_at = forms.DateTimeField(
        label='Datum und Uhrzeit',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        input_formats=['%Y-%m-%dT%H:%M'],
    )

    class Meta:
        model = Appointment
        fields = ('service', 'staff', 'starts_at')
        labels = {
            'service': 'Terminart',
            'staff': 'Ansprechpartner/in (optional)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service'].queryset = Service.objects.filter(active=True, bookable_in_app=True)
        self.fields['staff'].queryset = StaffMember.objects.filter(active=True)
        self.fields['staff'].required = False

    def clean_starts_at(self):
        value = self.cleaned_data['starts_at']
        if value < timezone.now() + timedelta(hours=1):
            raise forms.ValidationError('Bitte wählen Sie einen Termin mindestens eine Stunde in der Zukunft.')
        return value

    def clean(self):
        cleaned = super().clean()
        service = cleaned.get('service')
        start = cleaned.get('starts_at')
        if service and start:
            cleaned['ends_at'] = start + timedelta(minutes=service.duration_minutes + service.buffer_minutes)
        return cleaned

    def save(self, commit=True, user=None):
        obj = super().save(commit=False)
        obj.user = user
        obj.ends_at = self.cleaned_data['ends_at']
        obj.source = 'app'
        obj.status = 'requested'
        obj.notes_customer = ''
        obj.consent_acknowledged = False
        obj.full_clean()
        if commit:
            obj.save()
        return obj
