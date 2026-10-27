# accounts/forms.py

from django import forms
from django.contrib.auth.models import User
from .models import UserProfile


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


class ProfileSettingsForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            "profile_visibility",
            "email_notifications",
            "auto_share_photos",
            "allow_event_invites",
        ]