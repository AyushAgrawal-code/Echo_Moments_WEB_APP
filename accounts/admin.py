# from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import UserProfile
from events.image_validation import safe_image_filename, validate_image_upload


class UserProfileAdminForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = "__all__"

    def clean_profile_pic(self):
        image = self.cleaned_data.get("profile_pic")
        if image and not getattr(image, "_committed", False):
            _, extension = validate_image_upload(image)
            image.name = safe_image_filename(image.name, extension)
        return image

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    form = UserProfileAdminForm
    can_delete = False
    verbose_name_plural = 'Profile'

class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)

# Re-register User with inline
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Optional: separate section bhi dikhe
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    form = UserProfileAdminForm
    list_display = ('user', 'phone', 'bio')
