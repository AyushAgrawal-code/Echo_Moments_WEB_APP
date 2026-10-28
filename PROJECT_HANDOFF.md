# EchoMoments Project Handoff

**Updated:** 2026-10-28
**Workspace:** `C:\Users\Hp\OneDrive\Desktop\codes\oopm\echo-moments Django\echoMoments (4)\echoMoments`
**GitHub target:** [AyushAgrawal-code/Echo_Moments_WEB_APP](https://github.com/AyushAgrawal-code/Echo_Moments_WEB_APP)
**Branch / last committed base:** `main` / `78b826f Build EchoMoments free-demo MVP foundations`

## Important current status

- This is a handoff of the **local working tree**. The changes listed below are local edits after the last committed base; they have not been pushed as part of this work.
- **Do not deploy yet.** The user explicitly asked to pause deployment. No Render service, Supabase project/database, or hosted storage bucket has been configured or verified.
- Do not put secrets, passwords, database URLs, face-encryption keys, or storage credentials into this file or Git.
- Before the next implementation step, review the working tree and preserve the user's uncommitted work.

## What EchoMoments is

EchoMoments is an event-centered photo-sharing and memory-preservation app. A host makes a private, organized event space; participants contribute photos; authorized members revisit the shared album after the event. Instead of memories being scattered across separate phone galleries and chat threads, they are collected around the event that created them.

The central journey is: **host creates an event → members join → host configures contribution rules → members upload photos → the shared album collects them → members revisit/download permitted memories**. A member may host one event and be a guest in another. The event, rather than a public social feed, is the organizing unit.

Finding a member's own event photos is a core product goal, not a distant add-on: if a participant opts in, they can submit a selfie, EchoMoments scans event photos, and the participant gets a private personal album of likely matches with individual, selected, or bulk download. Matching is a suggestion and must remain consent-based and revocable.

## Product decisions and user requirements from the discussion

1. **Viewers/members are not limited by the upload cap.** A photo capacity should not block someone from joining or viewing the event.
2. **Hosts control photo allocation.** Event settings include an overall photo cap, a host allocation, and a shared guest pool. The host may optionally set a default per-member contribution limit and override it for an individual member; per-member limits are a host choice. Upload permission can be switched off for a member.
3. **Capacity must be reserved for queued work.** Saved, queued, and processing uploads count when deciding whether another upload fits. Settings must not reduce limits below already committed usage through the host UI.
4. **Uploads need a queue.** Every photo is its own durable job with visible progress, automatic retry for recoverable failure, and requeue of terminal failure without asking the user to select that file again. Host uploads normally get priority; aged guest work must still get a bounded turn so it cannot starve forever.
5. **Joining and uploading access:** current MVP supports authenticated accounts and public event codes/links. Password-protected/private invitations and scoped, no-account upload-only links are not implemented. A separate upload-only link/token is a possible later option; its permissions, expiry, revocation and whether guests can view still need a product decision.
6. **Privacy matters.** Photos and personal matches are private to authorized members; face enrollment needs explicit consent, and consent can be revoked.
7. The requested profile UI change was to remove the separate “Choose File” control and use the camera/photo option over the profile photo. That change is already in the earlier pushed baseline.
8. The user asked for an admin-panel review. The local admin surface and its access tests exist; hosted credentials and live production access have not been checked.
9. The user wants a free deployment to try the real workflow eventually, but has clearly said **not to deploy now**.

## What is implemented in the current project

### Events, membership and album

- Django application with account-based event membership. Hosts create events; logged-in members join public events with the event code/link.
- Event-level settings include dates/details, theme/cover, upload/download controls and photo-capacity controls.
- Viewing membership is independent of the photo cap. The host's member-management page is paginated at 50 members per page.
- Shared event photos are membership-gated and paginated. The shared album remains viewable to members after uploads are ended; upload closure does not automatically erase the event.
- Download access checks event membership and the host's download setting.

### Capacity, file upload and queue

- Each selected photo becomes a durable database-backed `UploadJob` and is staged in private storage. Jobs record status, attempts, availability, idempotency key and associated saved `Photo`.
- Local Windows worker command: `\.venv\Scripts\python.exe manage.py process_upload_queue`. Use the same `.venv` interpreter for the web process and face-index worker; `py manage.py ...` can choose a different global Django install. The host-first scheduler gives an aged guest a turn on the configured interval; guest work proceeds when there is no host backlog. Queue claims are designed for concurrent PostgreSQL workers.
- Browser behavior in `static/js/upload_queue.js`: a multi-file selection is sent as separate requests with up to three files in flight, per-file idempotency keys, progress, and up to three retries for transient network/server errors. Each job is polled as soon as the server accepts it. The database queue and host-priority scheduling remain server-side, so work from different users can still compete by priority. `runserver` does not start workers; run both queue commands in separate terminals or use `python manage.py serve_demo`.
- The upload path remains app-server-mediated. With S3-compatible private storage, the worker attempts a same-bucket server-side copy from staging to the final photo prefix; local storage and different-bucket configurations use the normal storage save path. Direct browser-to-R2 uploads, which would reduce app-server bandwidth further, are not implemented and require signed URLs plus bucket CORS configuration.
- Browser-level transient upload failures and worker-level transient save failures retry automatically. Terminal failed files remain staged for 30 days and can be requeued from the upload list.
- Event total cap, host allocation, guest pool, optional member default limit, and member override are available. Queued/processing jobs reserve capacity.
- Image upload limit is 10 MB and 30 megapixels. The server checks an allowlist against the actual bytes, decodes every image frame, and rejects malformed/truncated files and data appended after the image container. A filename or browser MIME type cannot make a program file pass. Stored extensions, inline/download MIME types, response filenames, and ZIP entry names are derived safely from verified bytes.
- Shared album pagination defaults to 20 photos per page, with 30 and 50 available in host and member views. The personal match album uses the same choices.

### Face-based personal album

- Enrollment is per event and opt-in. A participant can select a selfie file, use a mobile camera picker, or explicitly enable live camera capture; camera access is requested only after that click and requires HTTPS or localhost. Enrollment requires exactly one detectable face and confirmed consent. The selfie is handled in memory and discarded; an encrypted face feature template is retained for that event.
- YuNet detects faces and SFace builds features. `process_face_index_queue` processes photos and creates per-user private suggestions only for members with active consent.
- The `My Photos` page currently shows suggestions for one event. Users can hide a wrong match, download one photo, choose visible matches on the current page for a ZIP, or download all visible matches as a ZIP.
- Revoking consent removes the saved template and that user's suggestions. Face matching is not identity proof; recognition quality still needs validation on representative event photos.
- Model download is pinned to OpenCV Zoo revisions and SHA-256 checked by `scripts/download_face_models.py`; model licenses are downloaded with the files.

### Privacy, admin and storage

- Event photos, covers, profile pictures and staged upload files use private local storage in development and S3-compatible private storage when enabled. Django streams/serves private files only after authorization checks.
- Cleanup of replaced/deleted private objects is deferred until a database transaction commits.
- `FACE_ENCRYPTION_KEY` is required as a stable dedicated Fernet key in production. The value must be backed up securely; changing it makes previously stored face templates unreadable.
- Django Admin has Event, EventMember, Photo, UploadJob, FaceIndexJob and user/profile management. Raw encrypted templates and private storage file fields are hidden or read-only as appropriate.

### Local stack and deployment blueprint

- Django 5.2 application; current local test environment used Python 3.14.7. `render.yaml` pins Python 3.12.10 for its target.
- Development uses SQLite and local ignored private directories. The app requires the documented environment variables; Django does not load `.env` automatically.
- `render.yaml` describes a low-traffic demo: one Render Waitress web process with upload and face-index workers running in background threads, plus external Postgres and private S3-compatible object storage.
- Blueprint build installs `requirements-deploy.txt`, downloads pinned face models, and collects static files. Startup runs migrations and `python manage.py serve_demo`; that command starts both queue workers as daemon threads before Waitress. The background workers share the web process and stop when it sleeps/restarts, so this setup is for trying the MVP, not durable high-throughput processing.
- Recommended deployment choice: Cloudflare R2 for private photos and Neon for Postgres. R2 follows the existing S3-compatible storage code; Neon autosuspends idle compute and resumes automatically. Deployment is planned after local completion and commit; no cloud services have been provisioned. `README.md` compares current free-tier limits with Supabase and Cloudinary. Render Free still sleeps after 15 idle minutes and needs about a minute to wake.
- This single web/worker arrangement is for a low-traffic demo, not production-scale queue throughput. Dedicated workers and more robust storage/monitoring are a later scaling step.

## Local verification already completed

Most recent recorded verification in `AUDIT.md`:

- Django `check`, migration drift check (`makemigrations --check --dry-run`), migration check, Python syntax compilation, and `git diff --check` passed.
- Static files were collected and the pinned OpenCV models loaded locally.
- `pip check` found no broken declared dependencies.
- Django test suite passed **30 tests** using an isolated SQLite test database. Coverage includes event membership/album access, cap reservation, image size/dimension and content-integrity validation, rejection of document/program/audio/video uploads at app and Admin entry points, response MIME/safe ZIP names, 20/30/50 album page sizes, queue processing and retries, host-priority scheduling, member pagination, post-event album access, opt-in face matching and revocation, selfie camera-choice rendering, synthetic one-face enrollment through encrypted template and actual face-index match, unavailable OpenCV handling, and staff admin permissions/private-field restrictions.
- Latest local checks after this work: `manage.py check` passed, `makemigrations --check --dry-run` found no changes, and `git diff --check` exited successfully.
- Chrome responsive mode at 400 px was checked on the guest event page, My Photos, and account dashboard. Those pages fit the phone-width viewport. The signed-in local account has no hosted events, so host-specific UI was not visually reviewed.
- OpenCV 4.14 loaded the pinned YuNet and SFace models. One local 70-photo album was checked with a clear single-face reference: the original 0.363 cutoff produced 25 suggestions, including visually wrong low-score people; the 0.5 cutoff retained 11 visually consistent photos (including the reference) and excluded those false suggestions. A rollback-only endpoint/worker probe also returned 11 suggestions. No consent, template, or test matches remain in the local database. This is one album, not a broad quality benchmark.
- `manage.py check_face_matching` confirms the active environment can import OpenCV and load both models. Render startup invokes the same check after migrations. The form and source options were checked in Chrome, but the camera stream was not started because browser permission must be granted by the user.
- Local smoke validation detected one synthetic face with YuNet, generated a 128-value SFace embedding, enrolled it through the consent endpoint, and matched an identical synthetic event photo through the actual face-index worker inside Django's isolated test database. The encrypted template round-tripped to the same embedding; no synthetic image or enrollment was retained in the user's database.
- Three pre-existing local uploads were queued because only `runserver` had been started. Starting both local workers completed all three uploads and face-index jobs; with no opted-in members, no face scans were performed.
- Browser upload submission now runs at most three files concurrently. Same-bucket S3-compatible staging-to-album saves use server-side copy; end-to-end speed with hosted R2 remains unverified, and signed direct-to-R2 browser uploads are not part of this implementation.
- Event photos, covers, profile pictures, selfies, and Django Admin event/profile uploads share the JPEG/PNG/GIF/WebP byte validator. Legacy prototype inputs were narrowed to the same browser allowlist.
- `check --deploy` returned the optional warning `security.W021` because HSTS preload is disabled.
- **Not verified:** hosted Postgres, real S3-compatible storage credentials/bucket, deployed Render service, full browser end-to-end flow, concurrent uploads against hosted services, and match quality across varied people, lighting, poses, and events.

## Current local edits after the last commit

`git status --short` includes changes in the handoff, README, audit, upload validation, account/admin forms, event/admin forms and views, OpenCV/queue handling, responsive templates and styles, and upload-queue JavaScript. New untracked files include `events/image_validation.py` and `static/css/event-workflow.css`. Nothing has been committed; preserve all existing working-tree edits.

## Next work, in order

1. Continue local browser verification with an isolated temporary host event: host settings and capacity controls, upload queue/retry behavior, shared-album pagination, download permissions, host-dashboard layout, and the selfie camera on a device/browser where the user can grant camera permission. The three pre-existing local uploads have already completed.
2. Use the recommended R2/Neon pairing as the deployment plan. Configure services and secrets at the agreed deployment stage; until then, keep local storage for development.
3. Exercise simultaneous uploads and cap edits against hosted Postgres and private object storage after provisioning. Recognition quality and scan latency still need evaluation on a sample from a member who explicitly opts in.
4. Finish product decisions for private/password invitations and no-account upload-only links, if they are required for the demo. Keep member/view access separate from photo upload quotas.
5. **Deployment follows local completion and commit, as the user requested.** At that stage, provision/configure Render, Neon Postgres, private R2 storage, and stable secrets; connect the Blueprint; migrate and exercise a real hosted end-to-end event. Do not transfer local SQLite/private-media data without a separate migration plan. Do not start provisioning before the local completion and commit stages are finished.

## Useful local commands

```powershell
# Local setup
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/download_face_models.py

# Configure local environment in the current PowerShell session
$env:SECRET_KEY = "a-long-random-secret-for-local-development"
$env:DEBUG = "True"
$env:ALLOWED_HOSTS = "localhost,127.0.0.1"
python manage.py migrate
python manage.py createsuperuser
\.venv\Scripts\python.exe manage.py serve_demo --host 127.0.0.1 --port 8000

# Separate worker terminals
\.venv\Scripts\python.exe manage.py process_upload_queue
\.venv\Scripts\python.exe manage.py process_face_index_queue

# Checks used for the project
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test events
```

See `README.md` for setup/deployment details and `AUDIT.md` for the latest verification/gap list. Never copy production secrets into shell history, Git, or this handoff.
