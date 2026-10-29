from django.urls import path
from . import views

app_name = "events"

urlpatterns = [
    path("create/", views.create_event, name="create_event"),
    path("join/", views.join_event, name="join_event"),
    path("invite/<uuid:invite_token>/", views.accept_event_invite, name="accept_event_invite"),
    path("scan/", views.scan_qr_page, name="scan_qr"),
    path("<str:event_code>/", views.event_detail, name="event_detail"),
    path("<str:event_code>/toggle-upload/", views.toggle_upload_status, name="toggle_upload"),
    path("<str:event_code>/upload-photo/", views.upload_photo, name="upload_photo"),
    path("<str:event_code>/uploads/<uuid:job_id>/status/", views.upload_job_status, name="upload_job_status"),
    path("<str:event_code>/uploads/<uuid:job_id>/retry/", views.retry_upload_job, name="retry_upload_job"),
    path("<str:event_code>/my-photos/", views.my_photos, name="my_photos"),
    path("<str:event_code>/my-photos/scan-status/", views.face_scan_status, name="face_scan_status"),
    path("<str:event_code>/my-photos/enroll/", views.enroll_face, name="enroll_face"),
    path("<str:event_code>/my-photos/revoke/", views.revoke_face_enrollment, name="revoke_face_enrollment"),
    path("<str:event_code>/my-photos/retry-scans/", views.retry_face_indexing, name="retry_face_indexing"),
    path("<str:event_code>/my-photos/download-all/", views.download_my_photos, name="download_my_photos"),
    path("<str:event_code>/my-photos/<int:photo_id>/hide/", views.hide_face_match, name="hide_face_match"),
    path("<str:event_code>/photo-limits/", views.update_photo_limits, name="update_photo_limits"),
    path("<str:event_code>/members/<int:user_id>/photo-limit/", views.update_member_photo_limit, name="update_member_photo_limit"),
    path("<str:event_code>/remove-member/<int:user_id>/", views.remove_member, name="remove_member"),
    path("<str:event_code>/end/", views.end_event, name="end_event"),
    path("<str:event_code>/photos/<int:photo_id>/delete/", views.delete_photo, name="delete_photo"),
    path("<str:event_code>/photos/<int:photo_id>/view/", views.view_photo, name="view_photo"),
    path("<str:event_code>/cover/", views.view_event_cover, name="view_event_cover"),
    path("<str:event_code>/photos/<int:photo_id>/download/", views.download_photo, name="download_photo"),
]
