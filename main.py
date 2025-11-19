"""Entry point shim so Cloud Run buildpacks discover the FastAPI app."""

from app.main import app as fastapi_app

# Buildpacks look for `app` at module scope (used by default gunicorn command)
app = fastapi_app
