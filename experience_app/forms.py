from django import forms
from django.core.exceptions import ValidationError
from PIL import Image
from django.utils import timezone

from platform_app.models import Service, StaffMember

from .models import (
    AccountDeletionRequest,
    BeautyPlan,
    CabinetProduct,
    CallbackRequest,
    Complaint,
    ConciergeRequest,
    Feedback,
    ProgressAlbum,
    ProgressPhoto,
    ShopOrder,
)


class SlotSearchForm(forms.Form):
    service = forms.ModelChoiceField(queryset=Service.objects.none(), label="Leistung")
    staff = forms.ModelChoiceField(queryset=StaffMember.objects.none(), label="Behandler/in")
    day = forms.DateField(label="Datum", widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = Service.objects.filter(active=True, bookable_in_app=True)
        self.fields["staff"].queryset = StaffMember.objects.filter(active=True)
        self.fields["day"].initial = timezone.localdate()

    def clean_day(self):
        value = self.cleaned_data["day"]
        if value < timezone.localdate():
            raise forms.ValidationError("Bitte wählen Sie ein zukünftiges Datum.")
        return value


class SlotBookingForm(forms.Form):
    service_id = forms.IntegerField(widget=forms.HiddenInput)
    staff_id = forms.IntegerField(widget=forms.HiddenInput)
    starts_at = forms.DateTimeField(widget=forms.HiddenInput)
    notes = forms.CharField(label="Hinweis für A+ Esthetic", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    consent_acknowledged = forms.BooleanField(
        label="Ich bestätige, dass die Buchung keine medizinische Beratung oder Behandlungszusage darstellt."
    )


class AppointmentChangeForm(forms.Form):
    request_type = forms.ChoiceField(
        label="Anfrage",
        choices=[("cancel", "Termin stornieren"), ("reschedule", "Termin verschieben"), ("late", "Verspätung melden"), ("on_way", "Ich bin unterwegs")],
    )
    requested_start = forms.DateTimeField(label="Neuer Wunschtermin", required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    delay_minutes = forms.IntegerField(label="Verspätung in Minuten", required=False, min_value=0, max_value=180)
    message = forms.CharField(label="Nachricht", required=False, widget=forms.Textarea(attrs={"rows": 3}))


class ProgressAlbumForm(forms.ModelForm):
    class Meta:
        model = ProgressAlbum
        fields = ["title", "description", "private"]
        labels = {"title": "Albumname", "description": "Beschreibung", "private": "Privat"}


class ProgressPhotoForm(forms.ModelForm):
    ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
    MAX_SIZE = 10 * 1024 * 1024

    def clean_image(self):
        upload = self.cleaned_data["image"]
        if upload.size > self.MAX_SIZE:
            raise ValidationError("Das Foto darf maximal 10 MB groß sein.")
        content_type = getattr(upload, "content_type", "")
        if content_type not in self.ALLOWED_CONTENT_TYPES:
            raise ValidationError("Erlaubt sind JPEG-, PNG- und WebP-Dateien.")
        try:
            image = Image.open(upload)
            image.verify()
            upload.seek(0)
        except Exception as exc:
            raise ValidationError("Die Bilddatei ist beschädigt oder ungültig.") from exc
        return upload

    class Meta:
        model = ProgressPhoto
        fields = ["kind", "image", "taken_at", "angle", "lighting_note", "visible_to_customer"]
        labels = {
            "kind": "Bildtyp",
            "image": "Foto",
            "taken_at": "Aufnahmezeit",
            "angle": "Aufnahmewinkel",
            "lighting_note": "Hinweis zur Beleuchtung",
            "visible_to_customer": "Für mich sichtbar",
        }
        widgets = {"taken_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}


class FollowUpResponseForm(forms.Form):
    response = forms.CharField(label="Ihre Rückmeldung", widget=forms.Textarea(attrs={"rows": 5}))
    request_contact = forms.BooleanField(label="Ich möchte von A+ Esthetic kontaktiert werden", required=False)


class BeautyPlanForm(forms.ModelForm):
    class Meta:
        model = BeautyPlan
        fields = ["title", "journey_type", "goal", "target_date", "monthly_budget_cents", "annual_budget_cents"]
        labels = {
            "title": "Name des Plans",
            "journey_type": "Journey",
            "goal": "Organisatorisches Ziel",
            "target_date": "Zieldatum",
            "monthly_budget_cents": "Monatliches Budget in Cent",
            "annual_budget_cents": "Jährliches Budget in Cent",
        }
        widgets = {"target_date": forms.DateInput(attrs={"type": "date"}), "goal": forms.Textarea(attrs={"rows": 4})}


class CabinetProductForm(forms.ModelForm):
    class Meta:
        model = CabinetProduct
        fields = ["name", "brand", "barcode", "category", "opened_on", "expires_on", "pao_months", "estimated_empty_on", "personal_note", "personal_rating"]
        labels = {
            "name": "Produktname",
            "brand": "Marke",
            "barcode": "Barcode",
            "category": "Kategorie",
            "opened_on": "Geöffnet am",
            "expires_on": "Ablaufdatum",
            "pao_months": "PAO in Monaten",
            "estimated_empty_on": "Voraussichtlich leer am",
            "personal_note": "Persönliche Notiz",
            "personal_rating": "Eigene Bewertung (1–5)",
        }
        widgets = {
            "opened_on": forms.DateInput(attrs={"type": "date"}),
            "expires_on": forms.DateInput(attrs={"type": "date"}),
            "estimated_empty_on": forms.DateInput(attrs={"type": "date"}),
            "personal_note": forms.Textarea(attrs={"rows": 3}),
        }


class CheckoutForm(forms.ModelForm):
    use_credit_cents = forms.IntegerField(label="A+ Credit verwenden (Cent)", required=False, min_value=0)
    giftcard_code = forms.CharField(label="Gift-Card-Code", required=False)

    class Meta:
        model = ShopOrder
        fields = ["delivery_method"]
        labels = {"delivery_method": "Lieferart"}


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ["appointment", "overall_rating", "cleanliness_rating", "staff_rating", "waiting_time_rating", "comment", "private_to_management"]
        labels = {
            "appointment": "Termin",
            "overall_rating": "Gesamterlebnis (1–5)",
            "cleanliness_rating": "Sauberkeit (1–5)",
            "staff_rating": "A+ Team (1–5)",
            "waiting_time_rating": "Wartezeit (1–5)",
            "comment": "Ihre Rückmeldung",
            "private_to_management": "Nur für das A+ Management",
        }
        widgets = {"comment": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["appointment"].queryset = user.appointments.filter(status="completed")
        self.fields["appointment"].required = False


class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ["subject", "description", "priority"]
        labels = {"subject": "Betreff", "description": "Beschreibung", "priority": "Priorität"}
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}


class CallbackRequestForm(forms.ModelForm):
    class Meta:
        model = CallbackRequest
        fields = ["subject", "preferred_time", "phone", "note"]
        labels = {"subject": "Thema", "preferred_time": "Bevorzugte Zeit", "phone": "Telefon", "note": "Hinweis"}
        widgets = {"preferred_time": forms.DateTimeInput(attrs={"type": "datetime-local"}), "note": forms.Textarea(attrs={"rows": 3})}


class ConciergeRequestForm(forms.ModelForm):
    class Meta:
        model = ConciergeRequest
        fields = ["request_type", "title", "details"]
        labels = {"request_type": "Anfrageart", "title": "Titel", "details": "Details"}
        widgets = {"details": forms.Textarea(attrs={"rows": 4})}


class AccountDeletionForm(forms.ModelForm):
    confirm = forms.BooleanField(label="Ich möchte die Kontolöschung verbindlich anfordern")

    class Meta:
        model = AccountDeletionRequest
        fields = ["reason"]
        labels = {"reason": "Optionaler Grund"}
        widgets = {"reason": forms.Textarea(attrs={"rows": 3})}
