# EchoMoments

EchoMoments is an event-centered memory album: hosts create an event, members join it, share photos, and revisit the shared album after the event. View access is independent of upload caps. The project now includes durable per-photo upload records, configurable capacity limits, private photo delivery, and opt-in face-matched personal albums.

## Local development (Windows)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/download_face_models.py
Copy-Item .env.example .env
```

Django does not load `.env` automatically. Set environment variables in the terminal before starting the server:

```powershell
$env:SECRET_KEY = "a-long-random-secret-for-local-development"
$env:DEBUG = "True"
$env:ALLOWED_HOSTS = "localhost,127.0.0.1"
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Run these workers in separate terminals while developing:

```powershell
python manage.py process_upload_queue
python manage.py process_face_index_queue
```

The upload worker saves staged files into the private event album, gives host uploads higher priority, retries transient failures, and prevents guest uploads from waiting indefinitely. A file that still fails stays in private staging for 30 days and can be requeued from the upload list without selecting it again. Face indexing is separate and only matches members who opted in. The database-backed jobs can be processed by a separate worker in a multi-service deployment.

## Upload limits and queue

Hosts can set an event-wide photo cap, a host allocation, a shared guest pool, a default per-member limit, and individual member overrides. Viewers are not capped. Queued and processing uploads reserve capacity, and host changes cannot reduce a cap below existing saved or queued photos. Each selected file is submitted as its own idempotent queue job. The browser retries transient upload failures and displays per-file progress.

## Personal photo albums

A member can opt in for an event by uploading a clear selfie with exactly one visible face and checking the consent box. EchoMoments processes the selfie in memory, discards it, and stores only an encrypted face template for that event. The face-index worker scans event photos and creates private suggestions. The current My Photos page is scoped to one event. Members can hide a wrong suggestion, download one photo, choose multiple visible suggestions on the current page for a ZIP, or download all visible suggestions as a ZIP. They can turn matching off at any time; revoking consent removes the template and their suggestions.

Face matching uses OpenCV YuNet for detection and SFace for feature extraction. Install the pinned model files and their license notices with:

```powershell
python scripts/download_face_models.py
```

The model files are downloaded from pinned OpenCV Zoo revisions and checked against SHA-256 hashes. YuNet model files are MIT-licensed and SFace model files are Apache-2.0-licensed; the script also downloads their license texts. Face matching produces suggestions, not identity proof, so users must review the album. Recognition quality should be evaluated with varied real event photos before broader use.

Set `FACE_ENCRYPTION_KEY` to a stable Fernet key for deployments. Generate one with:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

If it is omitted, the key is derived from Django's `SECRET_KEY`; changing that secret will make existing face templates unreadable. Never commit either key.

## Privacy and storage

Event photos, profile pictures, event cover images, and pending uploads are stored outside `MEDIA_ROOT`. Django serves them through authenticated endpoints. A migration copies existing cover/profile images from public media paths to private storage and removes the old public copies. Private files are deleted after a database transaction commits when their record is deleted or its file is replaced. Keep the storage bucket private. Face templates are encrypted with `FACE_ENCRYPTION_KEY`; accepted selfies stay in memory for the request and are not retained.

Local development uses private folders `private_uploads/` and `private_media/` plus SQLite. They are ignored by Git. Back up the database and private files before local data migrations.

## Free demo deployment

The repository includes a Render Blueprint in `render.yaml`. It runs one small Waitress web process with the upload and face-index workers in background threads. This layout is for a low-traffic demo; the separate worker commands remain available when moving to dedicated worker services.

A free Render web service has an ephemeral filesystem and spins down after inactivity, so this configuration stores database records and photos in external services. The current no-cost setup is:

1. Create a Supabase Free project. Use its Postgres connection string as `DATABASE_URL`.
2. Create a **private** Supabase Storage bucket and enable its S3-compatible API.
3. Connect the GitHub repository to Render and deploy the included Blueprint.
4. Set the S3 endpoint, region, bucket name, server-side access key, and secret key in Render. For Supabase, use the endpoint and region shown in its S3 settings and set `AWS_S3_ADDRESSING_STYLE=path`.
5. Set a stable `FACE_ENCRYPTION_KEY` in Render. The Blueprint generates a Django `SECRET_KEY` for the service.
6. Keep `DEBUG=False`. The Blueprint installs dependencies, downloads the pinned face models, collects static files, applies migrations, and starts the integrated demo server.

Production startup fails fast if persistent S3 storage, its endpoint/region, or a valid dedicated Fernet key is missing.

Free-tier limits affect how long data remains available and how much can be uploaded. Render's free web filesystem is ephemeral and its service sleeps after 15 minutes without traffic. Supabase Free currently includes a 500 MB database and 1 GB file storage, and free projects can pause after a week of inactivity. This is suitable for trying the workflow, not as a durable production service. Review the providers' current limits before deploying:

- [Render free services](https://render.com/docs/free)
- [Supabase pricing and free limits](https://supabase.com/pricing)
- [Supabase S3 authentication](https://supabase.com/docs/guides/storage/s3/authentication)

Do not use a public storage bucket or expose the S3 credentials to the browser. The app streams private objects only after checking event membership.

## Current product gaps

Private/hidden invitation workflows, email notifications, payments, comments, tags, and role delegation beyond the host are not implemented. The current member-access flow uses accounts and event codes; future no-account upload links should remain separate from viewer access and use revocable, scoped tokens.
