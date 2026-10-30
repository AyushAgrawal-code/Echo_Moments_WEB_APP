# Use the official Python image so pip and venv are available during build.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# OpenCV headless needs the standard C++ runtime; keep the image lean.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libstdc++6 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-deploy.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements-deploy.txt

COPY . .

# Fetch the pinned, SHA-256-verified YuNet/SFace models at image build time.
RUN python scripts/download_face_models.py \
    && python manage.py collectstatic --noinput

EXPOSE 8000

# Run migrations and deployment checks before starting the Waitress server.
# The repository does not define a configure_site management command.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py check --deploy && python manage.py check_face_matching && python manage.py serve_demo --host 0.0.0.0 --port ${PORT:-8000}"]
