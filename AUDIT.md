# EchoMoments MVP implementation audit

Last reviewed: 2026-10-28. This audit describes the current working tree; deployment credentials and provider state are not part of this repository.

## Agreed MVP behavior

| Area | Current state | Remaining verification or work |
|---|---|---|
| Account-based event access | Hosts create events; signed-in members join public events using the host's event code/link. A member must join before viewing the album. No viewer/member-count cap is applied. | Private/hidden invitation and password flows are not implemented. |
| Upload capacity | Host can configure event total, host allocation, shared guest pool, optional default member cap, and individual member overrides. Upload permission can be disabled per member. Queued jobs reserve capacity; caps cannot be reduced below existing saved/queued usage through the host UI. | Exercise cap edits and simultaneous uploads against a hosted Postgres database. |
| Upload queue | Each file becomes its own database-backed job with a private staged object, idempotency key, status, retry count, and host priority. Transient browser/network and worker save failures retry automatically; terminal failures can be requeued without selecting the file again. A guest anti-starvation interval is configured. | Run multi-user queue scenarios against the actual object store and hosted database. |
| Shared album | Saved event photos are membership-gated and paginated; the album remains available after the host ends uploads. View/download endpoints check membership and downloads respect the host setting. | Confirm behavior after deployment and decide whether local event data/photos should be imported. |
| Personal photo album | Optional selfie enrollment requires consent and exactly one detected face. YuNet/SFace suggestions are private to the member; wrong matches can be hidden; one, selected, or all visible matches can be downloaded; revocation deletes the encrypted template and suggestions. The selfie is not retained. | Check recognition quality on representative event photos and monitor scan cost/latency. |
| Privacy and storage | Event images, covers, profile photos, and staged uploads use private local storage in development or S3-compatible private storage when `USE_S3=True`. Django serves files after authorization. Face embeddings are encrypted. File cleanup runs after commit on record deletion/replacement. Production settings require private S3 storage and a valid dedicated face key. | Verify the configured private bucket and credentials in the actual deployment. |
| Admin | Django admin exposes event/member controls, capacity and upload status, and read-only queue/photo/face-scan inspection. Raw encrypted face embeddings and direct private file URLs are not exposed. | Confirm staff/superuser accounts and permissions after deployment. |
| Free demo setup | `render.yaml` configures one Render web process with Waitress and queue threads; Postgres and private S3-compatible storage are external. Python is pinned to 3.12.10 for deployment. | Create/configure provider resources, deploy, and exercise the live app. |

## Verification completed locally

- Installed the declared deployment dependencies in an ignored local `.venv` and ran Django 5.2.18.
- `manage.py check`: passed. `makemigrations --check --dry-run`: no changes detected. `migrate --check`: passed.
- Four changed templates compiled; `collectstatic` copied 146 files and post-processed 436 files.
- OpenCV 4.14 loaded both downloaded, SHA-256-verified YuNet/SFace models. The private photo and upload S3 storage classes initialized using placeholder credentials and a placeholder endpoint; no real bucket connection was made.
- `pip check` reported no broken requirements. Python syntax compilation and `git diff --check` passed.
- `manage.py check --deploy` reported only Django's optional `security.W021` warning because HSTS preload is intentionally disabled.
- Automated tests and a full browser/E2E flow were not run. Local checks used Python 3.14.7; Render is configured for Python 3.12.10.

## Known gaps before a public demo

- The Render service, Supabase database, private storage bucket, and their credentials have not been created/configured. No live deployment or upload to a real bucket has been verified.
- Local SQLite data and `private_media/` files do not automatically transfer to the hosted services.
- Private-event invites, password-gated join links, and no-account upload-only token links are not implemented. The current MVP uses signed-in accounts and event codes.
- Comments, tags, email notifications, payments, and extended role delegation are outside the current MVP implementation.
- Full face-match quality and the complete host/member/upload/retry/download flow still need real user-photo and browser validation.

