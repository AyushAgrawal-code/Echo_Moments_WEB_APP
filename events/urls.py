from django.urls import path
from . import views

app_name = "events"

urlpatterns = [
    path("create/", views.create_event, name="create_event"),
    path("join/", views.join_event, name="join_event"),
    path("scan/", views.scan_qr_page, name="scan_qr"),
    path("<str:event_code>/", views.event_detail, name="event_detail"),
    path("<str:event_code>/toggle-upload/", views.toggle_upload_status, name="toggle_upload"),
    path("<str:event_code>/upload-photo/", views.upload_photo, name="upload_photo"),
    path("<str:event_code>/remove-member/<int:user_id>/", views.remove_member, name="remove_member"),
    path("<str:event_code>/end/", views.end_event, name="end_event"),
    path("<str:event_code>/photos/<int:photo_id>/delete/", views.delete_photo, name="delete_photo"),
    path("<str:event_code>/photos/<int:photo_id>/download/", views.download_photo, name="download_photo"),
]
