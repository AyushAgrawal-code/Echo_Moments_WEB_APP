# accounts/forms.py

from django import forms
from django.contrib.auth.models import User
from .models import UserProfile
from events.image_validation import safe_image_filename, validate_image_upload


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-input"}),
            "last_name": forms.TextInput(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make every field optional
        for field in self.fields.values():
            field.required = False


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            "profile_pic",
            "phone",
            "date_of_birth",
            "location",
            "bio",
            "profile_visibility",
            "email_notifications",
            "auto_share_photos",
            "allow_event_invites",
        ]

        widgets = {
            "phone": forms.TextInput(attrs={"class": "form-input"}),
            "date_of_birth": forms.DateInput(
                attrs={"type": "date", "class": "form-input"}
            ),
            "location": forms.TextInput(attrs={"class": "form-input"}),
            "bio": forms.Textarea(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make EVERY profile field optional
        for field in self.fields.values():
            field.required = False

    def clean_profile_pic(self):
        image = self.cleaned_data.get("profile_pic")
        if image and not getattr(image, "_committed", False):
            _, extension = validate_image_upload(image)
            image.name = safe_image_filename(image.name, extension)
        return image


class ProfileSettingsForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            "profile_visibility",
            "email_notifications",
            "auto_share_photos",
            "allow_event_invites",
        ]


from django.contrib.auth.forms import PasswordResetForm


class CustomPasswordResetForm(PasswordResetForm):
    """
    Password reset form that sends reset links to any active user account,
    even if the user previously only signed in via Google OAuth (unusable password).
    """

    def get_users(self, email):
        email_field_name = User.get_email_field_name()
        return list(
            User.objects.filter(**{
                f"{email_field_name}__iexact": email,
                "is_active": True,
            })
        )
