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
    - Fully guarded against 500 crashes and database constraint errors.
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
        session_keys = list(request.session.keys()) if request and hasattr(request, "session") else []
        cookies = list(request.COOKIES.keys()) if request and hasattr(request, "COOKIES") else []
        has_sessionid = "sessionid" in cookies
        logger.error(
            "OAuth authentication error for provider [%s]: error=%s, exception=%r, extra_context=%s, GET=%s, "
            "has_sessionid_cookie=%s, session_keys=%s",
            provider_name,
            error,
            exception,
            extra_context,
            dict(request.GET.items()) if request else {},
            has_sessionid,
            session_keys,
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
        try:
            self._handle_pre_social_login(request, sociallogin)
        except Exception as exc:
            logger.exception("Error in pre_social_login: %s", exc)

    def _handle_pre_social_login(self, request, sociallogin):
        # 1. Already linked to an existing database social account? Nothing to do.
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
            return
        except User.MultipleObjectsReturned:
            user = User.objects.filter(email__iexact=email).first()

        # 4. Ensure a verified EmailAddress exists for the user.
        #    This is critical: allauth's wipe_password() checks for a
        #    verified EmailAddress. If one doesn't exist, it sets an
        #    unusable password on the user.
        try:
            email_address = EmailAddress.objects.filter(email__iexact=email).first()
            if email_address:
                needs_save = False
                if email_address.user_id != user.pk:
                    email_address.user = user
                    needs_save = True
                if not email_address.verified:
                    email_address.verified = True
                    needs_save = True
                if needs_save:
                    email_address.save()
            else:
                has_primary = EmailAddress.objects.filter(user=user, primary=True).exists()
                EmailAddress.objects.create(
                    user=user,
                    email=email,
                    verified=True,
                    primary=not has_primary,
                )
        except Exception as exc:
            logger.warning("Could not synchronize EmailAddress for user %s: %s", user, exc)

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
