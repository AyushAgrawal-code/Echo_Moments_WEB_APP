import logging

from allauth.account.models import EmailAddress
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Seamless Google OAuth Adapter:
    - If user exists with the Google email: links social account and logs in.
    - If user does not exist: creates user and logs in without intermediate forms.
    - Never wipes existing passwords.

    How it works:
    We do NOT call sociallogin.connect() here (that crashes because the
    SocialAccount hasn't been saved yet). Instead we:
    1. Ensure a *verified* EmailAddress row exists for the existing user
       — this prevents allauth's wipe_password() from destroying the
       user's password during _accept_login().
    2. Set sociallogin.user to the existing user and mark
       _did_authenticate_by_email so allauth's EMAIL_AUTHENTICATION +
       AUTO_CONNECT settings handle the actual linking in _accept_login().
    """

    def on_authentication_error(
        self,
        request,
        provider,
        error=None,
        exception=None,
        extra_context=None,
    ):
        provider_name = getattr(provider, "name", getattr(provider, "id", str(provider)))
        logger.error(
            "OAuth authentication error for provider [%s]: error=%s, exception=%r, extra_context=%s, GET=%s",
            provider_name,
            error,
            exception,
            extra_context,
            dict(request.GET.items()) if request else {},
            exc_info=exception,
        )
        super().on_authentication_error(
            request,
            provider,
            error=error,
            exception=exception,
            extra_context=extra_context,
        )

    def pre_social_login(self, request, sociallogin):
        # 1. Already linked? Nothing to do.
        if sociallogin.is_existing:
            return

        # 2. Extract email from the social provider.
        email = None
        if sociallogin.email_addresses:
            email = sociallogin.email_addresses[0].email
        elif sociallogin.account.extra_data:
            email = sociallogin.account.extra_data.get("email")

        if not email:
            return

        email = email.lower().strip()

        # 3. Look up existing user by email.
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # No existing account — allauth auto-signup will create one.
            return
        except User.MultipleObjectsReturned:
            user = User.objects.filter(email__iexact=email).first()

        # 4. Ensure a verified EmailAddress exists for the user.
        #    This is critical: allauth's wipe_password() checks for a
        #    verified EmailAddress. If one doesn't exist, it sets an
        #    unusable password on the user.
        email_address, created = EmailAddress.objects.get_or_create(
            user=user,
            email=email,
            defaults={"verified": True, "primary": True},
        )
        if not email_address.verified:
            email_address.verified = True
            email_address.save(update_fields=["verified"])

        # 5. Point the sociallogin at the existing user so allauth
        #    treats this as an existing-user login, not a new signup.
        sociallogin.user = user
        # Tell allauth's _accept_login that we authenticated by email,
        # which enables AUTO_CONNECT to link the social account.
        sociallogin._did_authenticate_by_email = email

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
