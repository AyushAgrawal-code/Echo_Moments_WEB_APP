# accounts/views.py

from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.timezone import now
from django.http import JsonResponse
from django.http import FileResponse, HttpResponse
import mimetypes
import os
from django.db.models import Count, Q
from django.views.decorators.http import require_POST
from django.conf import settings

from events.models import Event, EventMember, Photo
from .forms import UserUpdateForm, ProfileUpdateForm


def _create_account(name, email, password):
    name = (name or "").strip()
    email = (email or "").strip().lower()
    if not name:
        raise ValidationError("Enter your name.")
    if not email:
        raise ValidationError("Enter your email address.")
    if not password:
        raise ValidationError("Enter a password.")
    validate_email(email)
    if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
        raise ValidationError("This email is already registered.")
    candidate = User(username=email, email=email, first_name=name)
    validate_password(password, user=candidate)
    return User.objects.create_user(
        username=email,
        email=email,
        password=password,
        first_name=name,
    )


# -----------------------------------------------------------
# LOGIN VIEW
# -----------------------------------------------------------
def login_view(request):
    if request.method == "POST":
        email = request.POST.get("login-email", "").strip().lower()
        password = request.POST.get("login-password", "")

        user = authenticate(
            request,
            username=email,
            password=password
        )

        if user:
            auth_login(request, user)
            return redirect("accounts:dashboard")

        messages.error(request, "Invalid email or password.")
        return redirect("accounts:login")

    return render(request, "accounts/login.html", {"google_login_enabled": settings.GOOGLE_LOGIN_ENABLED})


# -----------------------------------------------------------
# AUTH (LOGIN + SIGNUP) COMBINED
# -----------------------------------------------------------
def auth_view(request):
    if request.method == "POST":
        form_type = request.POST.get("form_type")

        # ---------------------------------------------------
        # SIGNUP
        # ---------------------------------------------------
        if form_type == "signup":

            name = request.POST.get(
                "signup-name",
                ""
            ).strip()

            email = request.POST.get(
                "signup-email",
                ""
            ).strip().lower()

            password = request.POST.get(
                "signup-password",
                ""
            )

            try:
                _create_account(name, email, password)
            except ValidationError as exc:
                for error in exc.messages:
                    messages.error(request, error)
                return redirect("accounts:signup")

            messages.success(
                request,
                "Account created successfully!"
            )

            return redirect("accounts:login")

        # ---------------------------------------------------
        # LOGIN
        # ---------------------------------------------------
        elif form_type == "login":

            email = request.POST.get(
                "login-email",
                ""
            ).strip().lower()

            password = request.POST.get(
                "login-password",
                ""
            )

            user = authenticate(
                request,
                username=email,
                password=password
            )

            if user:
                auth_login(request, user)
                return redirect("accounts:dashboard")

            messages.error(
                request,
                "Invalid credentials."
            )

            return redirect("accounts:auth")

    return render(
        request,
        "accounts/login.html",
        {"google_login_enabled": settings.GOOGLE_LOGIN_ENABLED},
    )


# -----------------------------------------------------------
# LOGOUT VIEW
# -----------------------------------------------------------
@require_POST
def logout_view(request):
    auth_logout(request)

    messages.success(
        request,
        "Logged out successfully."
    )

    return redirect("accounts:auth")


# -----------------------------------------------------------
# DELETE ACCOUNT
# -----------------------------------------------------------
@login_required
def delete_account(request):

    if request.method == "POST":

        request.user.delete()

        messages.success(
            request,
            "Your account has been deleted."
        )

        return redirect("accounts:auth")

    return redirect("accounts:profile")


# -----------------------------------------------------------
# PROFILE VIEW + UPDATE
# -----------------------------------------------------------
@login_required
def profile_view(request):

    user = request.user
    profile = user.profile

    # =======================================================
    # PROFILE STATISTICS
    # =======================================================

    hosted_count = Event.objects.filter(
        created_by=user
    ).count()

    joined_count = EventMember.objects.filter(
        user=user
    ).exclude(
        role="host"
    ).count()

    photos_count = Photo.objects.filter(
        uploaded_by=user
    ).count()

    memories_count = (
        hosted_count
        + joined_count
        + photos_count
    )

    # =======================================================
    # DEFAULT FORMS
    # =======================================================

    user_form = UserUpdateForm(
        instance=user
    )

    profile_form = ProfileUpdateForm(
        instance=profile
    )

    # =======================================================
    # POST REQUEST
    # =======================================================

    if request.method == "POST":

        form_type = request.POST.get(
            "form_type"
        )

        # ===================================================
        # AVATAR UPDATE
        # ===================================================

        if form_type == "avatar":

            # Create a mutable copy of POST data.
            #
            # ProfileUpdateForm may contain fields which are
            # not present inside the small avatar form.
            #
            # We preserve their current database values so
            # changing the avatar does not fail validation.
            data = request.POST.copy()

            for field in ProfileUpdateForm.Meta.fields:

                if field == "profile_pic":
                    continue

                if field not in data:

                    value = getattr(
                        profile,
                        field,
                        ""
                    )

                    if value is None:
                        value = ""

                    data[field] = value

            profile_form = ProfileUpdateForm(
                data,
                request.FILES,
                instance=profile
            )

            if profile_form.is_valid():

                profile_form.save()

                messages.success(
                    request,
                    "Profile picture updated successfully!"
                )

                return redirect(
                    "accounts:profile"
                )

            messages.error(
                request,
                "Unable to update profile picture. "
                "Please try again."
            )

        # ===================================================
        # PERSONAL PROFILE UPDATE
        # ===================================================

        elif form_type == "profile":

            user_form = UserUpdateForm(
                request.POST,
                instance=user
            )

            data = request.POST.copy()

            for field in ProfileUpdateForm.Meta.fields:

                if field == "profile_pic":
                    continue

                if field not in data:
                    value = getattr(profile, field, "")

                    if value is None:
                        value = ""

                    data[field] = value

            profile_form = ProfileUpdateForm(
                data,
                request.FILES,
                instance=profile
            )

            user_valid = user_form.is_valid()
            profile_valid = profile_form.is_valid()

            if user_valid and profile_valid:

                user_form.save()
                profile_form.save()

                messages.success(
                    request,
                    "Profile updated successfully!"
                )

                return redirect("accounts:profile")

            else:

                messages.error(
                    request,
                    "Profile update failed. Check terminal for exact error."
                )
        # ===================================================
        # UNKNOWN FORM TYPE
        # ===================================================

        else:

            messages.error(
                request,
                "Invalid profile form submission."
            )

    # =======================================================
    # RENDER PROFILE PAGE
    # =======================================================

    return render(
        request,
        "accounts/profile.html",
        {
            "user_form": user_form,
            "profile_form": profile_form,

            "hosted_count": hosted_count,
            "joined_count": joined_count,
            "photos_count": photos_count,
            "memories_count": memories_count,

            "profile": profile,
        }
    )


@login_required
def profile_photo(request):
    """Serve the signed-in user's profile image from private storage."""
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.profile_pic:
        return HttpResponse("Profile photo not found.", status=404)
    response = FileResponse(
        profile.profile_pic.open("rb"),
        as_attachment=False,
        filename=os.path.basename(profile.profile_pic.name),
        content_type=mimetypes.guess_type(profile.profile_pic.name)[0] or "application/octet-stream",
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


# -----------------------------------------------------------
# SIGNUP VIEW (SIMPLE)
# -----------------------------------------------------------
def signup_view(request):

    if request.method == "POST":

        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")

        try:
            _create_account(username, email, password)
        except ValidationError as exc:
            for error in exc.messages:
                messages.error(request, error)
            return redirect("accounts:signup")

        messages.success(
            request,
            "Account created!"
        )

        return redirect(
            "accounts:login"
        )

    return render(
        request,
        "accounts/signup.html",
        {"google_login_enabled": settings.GOOGLE_LOGIN_ENABLED},
    )


# -----------------------------------------------------------
# DASHBOARD VIEW
# -----------------------------------------------------------
@login_required
def dashboard_view(request):

    user = request.user

    # =======================================================
    # HOSTED EVENTS
    # =======================================================

    hosted_events = Event.objects.filter(created_by=user).annotate(active_members_count=Count("memberships", filter=Q(memberships__is_active=True)))

    # =======================================================
    # JOINED EVENTS
    # =======================================================

    joined_events = Event.objects.filter(memberships__user=user, memberships__is_active=True).exclude(created_by=user).annotate(active_members_count=Count("memberships", filter=Q(memberships__is_active=True))).distinct()

    # =======================================================
    # STATS
    # =======================================================

    total_photos = Photo.objects.filter(
        uploaded_by=user
    ).count()

    total_events_joined = joined_events.count()

    current_time = now()
    week_ago = current_time - __import__("datetime").timedelta(days=7)
    month_start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total_guests = EventMember.objects.filter(event__created_by=user, is_active=True).exclude(role="host").count()
    stats = {
        "hosted_events": hosted_events.count(),
        "joined_events": total_events_joined,
        "total_photos": total_photos,
        "hosted_events_trend": hosted_events.filter(created_at__gte=month_start).count(),
        "joined_events_trend": EventMember.objects.filter(user=user, is_active=True, joined_at__gte=month_start).exclude(role="host").count(),
        "photos_trend": Photo.objects.filter(uploaded_by=user, uploaded_at__gte=week_ago).count(),
        "total_guests": total_guests,
        "guests_trend": EventMember.objects.filter(event__created_by=user, is_active=True, joined_at__gte=week_ago).exclude(role="host").count(),
    }

    from .models import Activity
    activity_rows = list(Activity.objects.filter(user=user).order_by("-created_at")[:10])
    notifications = [{"title": row.title, "message": row.description, "created_at": row.created_at, "type": "event", "is_read": False} for row in activity_rows]
    activities = activity_rows

    # =======================================================
    # CONTEXT
    # =======================================================

    context = {
        "hosted_events": hosted_events,
        "joined_events": joined_events,

        "stats": stats,

        "notifications": notifications,
        "activities": activities,

        "profile": getattr(
            user,
            "profile",
            None
        ),
    }

    return render(
        request,
        "accounts/dashboard.html",
        context
    )


# -----------------------------------------------------------
# NOTIFICATIONS API
# -----------------------------------------------------------
@login_required
def notifications_api(request):
    from .models import Activity
    rows = Activity.objects.filter(user=request.user).order_by("-created_at")[:20]
    return JsonResponse({"notifications": [
        {"title": row.title, "message": row.description, "created_at": row.created_at.isoformat(), "type": "event", "is_read": False}
        for row in rows
    ]})










