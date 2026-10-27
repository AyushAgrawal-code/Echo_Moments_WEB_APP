# EchoMoments implementation audit

The working root is this directory (`manage.py` and `echoMoments/settings.py`). The supplied archive contains this same project structure. Existing `db.sqlite3`, media, and all migration files have been retained. A SQLite backup named `db.sqlite3.prechange.bak` was created alongside the workspace project; it is not duplicated inside the ZIP. No schema changes were made, so no migration was generated.

## Feature status

| Area | Status | Implemented behavior / remaining work |
|---|---|---|
| Event creation | Completed in code; runtime verification pending | Validates name/date/settings, creates event and host membership atomically, returns reversed detail URL and code. |
| Event roles and dashboards | Completed in code; runtime verification pending | Event pages distinguish the event owner from active members. The host manages the event; a guest gets album and upload functions. Dashboard joined events are event records, not membership rows. |
| Join by event code | Completed for public events | Prevents duplicate membership and rejects invalid, inactive, private, hidden, or deactivated memberships. Private invitation flow remains pending. |
| Event management authorization | Completed in code; runtime verification pending | Host-only POST endpoints manage uploads, members, and event status. Guest requests are denied server-side. |
| Photo upload and album | Completed in code; runtime verification pending | Requires active membership, active event, and uploads enabled; validates image format/content and a 10 MB per-file limit; stores `Photo` records; lists saved photos and supports permitted download and owner/uploader deletion. |
| QR generation and sharing | Completed in code; runtime verification pending | Host dashboard generates an event-specific PNG-capable QR and copyable join-code URL. |
| QR scanning | Partial | Camera permission is requested after the user presses Start; a manual code form is available. Scanning depends on the existing external Instascan CDN, which needs browser/internet verification. |
| Notifications and activity | Partial | Notification and activity views use stored `Activity` rows. There is no read/unread persistence or mark-read operation. |
| Profile/account | Partial | Existing Django authentication, profile forms, avatar handling, account deletion, and POST logout remain. Full form, signup validation, and account deletion regression checks could not run here. |
| Comments, tags, invitations, bulk download | Pending | Not represented as fake working controls in the new event views. Private-event invitations are required to join private events but are not implemented. |
| Facial recognition, payments, cloud storage | Future work | Not implemented. Local Django media storage is used. No payment or AI success is simulated. |
| Deployment hardening | Partial | `SECRET_KEY`, `DEBUG`, and `ALLOWED_HOSTS` are environment-configurable. Production media serving, HTTPS, deployment settings, and operational controls still need configuration. |

## New automated coverage

`events/tests.py` covers event creation and host membership, duplicate public joining, guest dashboard access, unrelated-user denial, private join denial, membership-gated image upload, and guest denial of host actions. Existing profile regression coverage remains in `accounts/tests.py`.

## Verification

Python and static JavaScript syntax checks pass using the bundled runtimes. Django checks and tests were not executable because the bundled environment does not include Django and repeated package-index downloads of Django 5.2.1 timed out at `files.pythonhosted.org`. After installing `requirements.txt`, run the commands in `README.md` from the project root. The original DB and migration history were not reset or rewritten.

