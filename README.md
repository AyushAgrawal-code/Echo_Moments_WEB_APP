# EchoMoments

Django event photo sharing MVP. Local development stores uploaded media in `media/` and uses the existing SQLite database. Keep a backup of `db.sqlite3` before applying future schema migrations.

## Windows setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set environment variables in PowerShell before starting Django (Django does not read `.env` files automatically):

```powershell
$env:SECRET_KEY = "a-long-random-secret-for-local-development"
$env:DEBUG = "True"
$env:ALLOWED_HOSTS = "localhost,127.0.0.1"
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Run checks and automated tests with `python manage.py check`, `python manage.py makemigrations --check --dry-run`, `python manage.py migrate --check`, and `python manage.py test`.

## Current scope

Event hosts and active members have separate event pages. Public events can be joined with the event code. Private and hidden events are invitation-only; an invitation workflow is not implemented, so code joining is rejected for those events. Photo uploads require an active membership, an active event, enabled uploads, and a supported image up to 10 MB. Members can download only when downloads are enabled. Hosts manage memberships and event status.

Notifications and activity are based on stored activity records, with no read/unread state yet. Facial recognition, payment processing, cloud storage adapters, invitations, comments, tags, and bulk ZIP download are future work and are not simulated. Local media storage is for development and is not a production media-serving configuration.
