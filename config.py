import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Secret key used by Flask to sign session cookies.
    # Locally, falls back to a dev value so you don't have to set anything.
    # On Render, set SECRET_KEY as an environment variable in the dashboard —
    # it'll automatically be picked up here instead.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-this")

    # --- Database ---
    # Locally: SQLite (a single file, zero setup).
    # On Render: Render automatically provides a DATABASE_URL environment
    # variable once you attach a PostgreSQL database to this service — if
    # that variable exists, we use it instead of SQLite.
    _database_url = os.environ.get("DATABASE_URL", "")
    if _database_url:
        # Render's DATABASE_URL starts with "postgres://", but SQLAlchemy
        # needs "postgresql://" (a naming change between library versions) —
        # this line just fixes that mismatch automatically.
        _database_url = _database_url.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = _database_url
    else:
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "skillconnect.db")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- File uploads (profile audio, voice notes) ---
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB max upload size

    # --- Gemini API (for AI voice-note feedback) ---
    # Locally: set this as an environment variable before running the app,
    # or paste your key directly below for convenience.
    # On Render: set GEMINI_API_KEY as an environment variable in the
    # dashboard — never commit a real key directly into this file if you're
    # pushing this project to a public GitHub repo.
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
