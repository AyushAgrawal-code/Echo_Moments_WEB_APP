# accounts/urls.py
from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    # Auth
    path("login/", views.login_view, name="login"),
    path("auth/", views.auth_view, name="auth"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),

    # Profile
    path("profile/", views.profile_view, name="profile"),
    path("profile/photo/", views.profile_photo, name="profile_photo"),
    path("delete/", views.delete_account, name="delete_account"),

    # Dashboard
    path("dashboard/", views.dashboard_view, name="dashboard"),

    # Notifications API
    path("notifications/", views.notifications_api, name="notifications_api"),
    path("api/notifications/", views.notifications_api, name="notifications_api_legacy"),
]


