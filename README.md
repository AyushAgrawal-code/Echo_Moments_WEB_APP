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

Settings load values from `.env` at startup. Copy `.env.example` to `.env` and edit the values there, or set environment variables in the terminal before starting the server:

```powershell
$env:SECRET_KEY = "a-long-random-secret-for-local-development"
$env:DEBUG = "True"
$env:ALLOWED_HOSTS = "localhost,127.0.0.1"
\.venv\Scripts\python.exe manage.py migrate
\.venv\Scripts\python.exe manage.py createsuperuser
\.venv\Scripts\python.exe manage.py serve_demo --host 127.0.0.1 --port 8000
```

Use the `.venv` interpreter explicitly; `py manage.py ...` can select a different global Django install. `serve_demo` runs the web app and both queue workers together, so use it for the local demo. `runserver` serves pages but does not start workers; if you choose it, run both worker commands below in separate terminals or uploads and face scans remain queued.

Run these workers in separate terminals while developing:

```powershell
\.venv\Scripts\python.exe manage.py process_upload_queue
\.venv\Scripts\python.exe manage.py process_face_index_queue
```

The browser submits up to three selected files at a time and begins checking each job as soon as the server accepts it. The upload worker saves staged files into the private event album and normally selects host uploads first. If host work stays queued, one guest upload that has waited past `--guest-wait-seconds` can take a slot per interval; when no host work is waiting, guests proceed without that delay. Transient failures retry automatically. A file that still fails stays in private staging for 30 days and can be requeued from the upload list without selecting it again. Face indexing is separate and only matches members who opted in. The database-backed jobs can be processed by multiple worker processes in a multi-service deployment.

The browser still sends image bytes to the Django app. When staging and final private objects share an S3-compatible bucket, the worker copies them inside that bucket to avoid a download/re-upload through the app server. Direct browser-to-R2 upload could reduce server bandwidth further, but needs signed upload endpoints and CORS configuration and is not implemented yet.

## Upload limits and queue

Hosts can set an event-wide photo cap, a host allocation, a shared guest pool, a default per-member limit, and individual member overrides. Viewers are not capped. Queued and processing uploads reserve capacity, and host changes cannot reduce a cap below existing saved or queued photos. Each selected file is submitted as its own idempotent queue job. Image uploads are limited to 10 MB and 30 megapixels; the accepted formats are JPEG, PNG, GIF, and WebP. The server checks actual bytes, fully decodes every frame, and rejects malformed files or data appended after the image container. This validation covers event photos, event covers, profile pictures, face-enrollment selfies, and Django Admin upload forms. Browser file filters use the same allowlist, while server validation remains authoritative. Stored extensions and response MIME types come from verified image bytes. The browser retries transient upload failures and displays per-file progress.

Shared event albums show 20 photos per page by default. Hosts and members can choose 30 or 50 per page; the selection is preserved while moving between pages. The personal photo album uses the same page-size options.

## Personal photo albums

A member can opt in for an event by uploading a clear selfie, using a phone's front-camera file picker, or enabling live camera capture, then checking the consent box. Live camera access is requested only after the member chooses that option; browsers require HTTPS or localhost. The selfie must contain exactly one visible face. EchoMoments processes it in memory, discards it, and stores only an encrypted face template for that event. The face-index worker scans event photos and creates private suggestions. The current My Photos page is scoped to one event. Members can hide a wrong suggestion, download one photo, choose multiple visible suggestions on the current page for a ZIP, or download all visible suggestions as a ZIP. They can turn matching off at any time; revoking consent removes the template and their suggestions.

Face matching uses OpenCV YuNet for detection and SFace for feature extraction. Install the pinned model files and their license notices with:

```powershell
python scripts/download_face_models.py
```

Check that the active Python environment can import OpenCV and load both models before enrolling:

```powershell
python -m pip install -r requirements.txt
python manage.py check_face_matching
```

The Render startup command runs the same check after migrations so a deployment with missing OpenCV/model files fails visibly instead of presenting an enrollment form that cannot work.

The model files are downloaded from pinned OpenCV Zoo revisions and checked against SHA-256 hashes. YuNet model files are MIT-licensed and SFace model files are Apache-2.0-licensed; the script also downloads their license texts. Face matching produces suggestions, not identity proof, so users must review the album. Recognition quality should be evaluated with varied real event photos before broader use.

## Authentication and account recovery

Signup applies Django's configured password validators on the server. Password reset uses Django's one-time reset links. Gmail SMTP is preconfigured in `.env.example` and the local `.env` with TLS on port 587. To enable sending, turn on 2-Step Verification for the sending Google account, create an App Password for EchoMoments, and enter the same Gmail address in `EMAIL_HOST_USER` and `DEFAULT_FROM_EMAIL`; put the App Password in `EMAIL_HOST_PASSWORD`. Restart Django after saving. Keep the App Password private and use a dedicated app password rather than your Google account password.

Google sign-in is optional and appears only when both `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` are set. Create a Google OAuth Web application client, add the deployed origin as an authorized JavaScript origin, and register `https://YOUR_DOMAIN/accounts/google/login/callback/` as an authorized redirect URI (for local development use `http://127.0.0.1:8000/accounts/google/login/callback/`). Keep the secret in the server's environment, never in browser code or source control. Install dependencies from `requirements.txt` and run `manage.py migrate` to create django-allauth's account, social-account, and Sites tables. The first deployment should also update the Django Site domain from `example.com` to the real app hostname in Django Admin.

The provider integration and button rendering can be tested locally without credentials, but completing Google's external consent and callback requires your OAuth client values and a matching callback URL.

Set `FACE_ENCRYPTION_KEY` to a stable Fernet key for deployments. Generate one with:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

If it is omitted, the key is derived from Django's `SECRET_KEY`; changing that secret will make existing face templates unreadable. Never commit either key.

## Privacy and storage

Event photos, profile pictures, event cover images, and pending uploads are stored outside `MEDIA_ROOT`. Django serves them through authenticated endpoints. A migration copies existing cover/profile images from public media paths to private storage and removes the old public copies. Private files are deleted after a database transaction commits when their record is deleted or its file is replaced. Keep the storage bucket private. Face templates are encrypted with `FACE_ENCRYPTION_KEY`; accepted selfies stay in memory for the request and are not retained.

Local development uses private folders `private_uploads/` and `private_media/` plus SQLite. They are ignored by Git. Back up the database and private files before local data migrations.

## Deployment blueprint and storage provider choice

The Render Blueprint runs one small Waitress web process with the upload and face-index workers in background threads. This layout is for a low-traffic demo; the separate worker commands remain available for dedicated worker services. The service filesystem is temporary, so a deployment needs persistent Postgres and private object storage.

The recommended setup for this demo is Cloudflare R2 for photos and Neon for Postgres. Both remain external recommendations only: no account, bucket, database, or credential has been created or configured.

| Photo storage | Advantages | Tradeoffs |
|---|---|---|
| Cloudflare R2 (recommended) | S3-compatible, fits the existing private storage backend, and includes 10 GB-month storage with free Internet egress on its Standard tier. | Database is separate; configure a private bucket and server-side keys. Usage beyond the free monthly allowance is billed. |
| Cloudinary | Strong image delivery, resizing, and optimization; familiar to the owner. Its Free plan includes 25 shared monthly credits. At 1 MB per original, 1,000 photos is about 1 GB before derivatives; stored size, delivered bandwidth, and transformations all consume credits. | Current code uses S3 storage and would need a Cloudinary adapter plus careful signed/private delivery. The 25 credits are a shared monthly pool, so photo views and variants reduce the storage headroom. |
| Supabase Storage | Keeps storage and Postgres together; its S3-compatible API fits the current backend. | Free storage is 1 GB; free projects can pause after 7 days of low activity and require manual restore. S3 keys stay server-side and can bypass Storage RLS. |
| AWS S3 | Mature S3 tooling, IAM controls, and broad operational support; fits the current backend. | More setup and usage-based billing to monitor. |

For the database, Neon Free currently includes 1 GB of Postgres storage and 100 compute-hours per project each month. Its compute suspends after five minutes idle and resumes automatically on the next query (typically about 500 ms), so it does not need periodic manual activity to keep the database usable. The Render Free web service still sleeps after 15 minutes without inbound traffic and takes about a minute to wake; that is the expected cold-start delay before a demo.

The Render Blueprint expects a private S3-compatible bucket, persistent Postgres `DATABASE_URL`, stable `FACE_ENCRYPTION_KEY`, and SMTP sender credentials. Set `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` (Gmail App Password), and `DEFAULT_FROM_EMAIL` in Render's environment; the values are never stored in the blueprint. Google sign-in is optional; add its client ID and secret there if enabled and register the Render hostname's OAuth callback URL. On each start, the blueprint migrates the database, configures the Sites domain from Render's hostname, runs Django's deployment check, validates the face models, and starts the web server and queue workers. R2 uses the existing storage path; Cloudinary requires an adapter. Keep all storage credentials in server environment settings and keep the bucket private; the app serves photos only after checking event access. Recheck current quotas and terms before creating services. The current free allowances suit a modest demo, not a 100,000-photo collection; actual capacity depends on average image size, derivatives, and monthly viewing. Before deployment, configure the recommended services, connect the repository, and run a live end-to-end check. Do not transfer local SQLite data or private files without a separate migration plan.

Current official plan information, reviewed 2026-10-28: [R2 pricing](https://developers.cloudflare.com/r2/pricing/), [Neon Free plan](https://neon.com/blog/neon-free-plan-1-gb-per-project), [Neon scale-to-zero](https://neon.com/blog/why-you-want-a-database-that-scales-to-zero), [Render Free limitations](https://render.com/docs/free), [Supabase project pausing](https://supabase.com/docs/guides/platform/free-project-pausing), and [Cloudinary billing](https://cloudinary.com/documentation/billing_and_plans).

## Current product gaps

Private/hidden invitation workflows, email notifications, payments, comments, tags, and role delegation beyond the host are not implemented. The current member-access flow uses accounts and event codes; future no-account upload links should remain separate from viewer access and use revocable, scoped tokens.
