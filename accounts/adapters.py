from allauth.account.models import EmailAddress
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

User = get_user_model()


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Seamless Google OAuth Adapter:
    - If user exists with the Google email: automatically links social account and logs in directly.
    - If user does not exist: automatically creates user and logs in directly without intermediate forms.
    - Never wipes existing passwords.
    """

    def pre_social_login(self, request, sociallogin):
        # 1. If this social account is already linked to a user, proceed.
        if sociallogin.is_existing:
            return

        # 2. Extract email from Google
        email = None
        if sociallogin.email_addresses:
            email = sociallogin.email_addresses[0].email
        elif sociallogin.account.extra_data:
            email = sociallogin.account.extra_data.get("email")

        if not email:
            return

        email = email.lower().strip()

        # 3. Check if an account with this email already exists
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # User doesn't exist yet; allauth auto-signup will create it
            return
        except User.MultipleObjectsReturned:
            user = User.objects.filter(email__iexact=email).first()

        # 4. Connect social account directly to the existing user
        sociallogin.connect(request, user)

        # 5. Ensure allauth EmailAddress record exists and is marked verified
        EmailAddress.objects.get_or_create(
            user=user,
            email=email,
            defaults={"verified": True, "primary": True},
        )

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        email = data.get("email") or ""
        if email:
            email = email.lower().strip()
            user.email = email
            if not user.username:
                if not User.objects.filter(username__iexact=email).exists():
                    user.username = email
                else:
                    user.username = self.generate_unique_username([email, "user"])
        return user
