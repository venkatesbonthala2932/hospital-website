import os
from dotenv import load_dotenv

# Explicitly load .env from the same directory as this file,
# regardless of where the user runs `python3 app.py` from.
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=_ENV_PATH, override=True)

_PLACEHOLDERS = {"your-project-ref.supabase.co", "your-anon-key-here",
                 "your-service-role-key-here", "change-this-to-any-random-string"}


class Config:
    # Supabase — used as database only, not for auth
    SUPABASE_URL         = os.environ.get("SUPABASE_URL", "").strip()
    SUPABASE_ANON_KEY    = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

    # Firebase — used for all authentication (email + Google)
    FIREBASE_SERVICE_ACCOUNT_JSON = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()

    # Flask
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret").strip()
    ENV        = os.environ.get("FLASK_ENV", "production").strip()
    DEBUG      = ENV == "development"
    PORT       = int(os.environ.get("FLASK_PORT", 8080))

    # Email (SMTP) — optional; emails are silently skipped if not configured
    SMTP_HOST  = os.environ.get("SMTP_HOST",  "").strip()
    SMTP_PORT  = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USER  = os.environ.get("SMTP_USER",  "").strip()
    SMTP_PASS  = os.environ.get("SMTP_PASS",  "").strip()
    FROM_EMAIL = os.environ.get("FROM_EMAIL", "Aadityaa Hospital <noreply@aadityaa.com>").strip()

    @classmethod
    def email_enabled(cls) -> bool:
        return bool(cls.SMTP_HOST and cls.SMTP_USER and cls.SMTP_PASS)

    # CORS — allowed frontend origins
    _raw = os.environ.get("CORS_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500")
    CORS_ORIGINS = [o.strip() for o in _raw.split(",") if o.strip()]

    # The first origin is used as the redirect target after Google OAuth
    @classmethod
    def frontend_url(cls):
        return cls.CORS_ORIGINS[0] if cls.CORS_ORIGINS else "http://localhost:5500"

    @classmethod
    def validate(cls):
        errors = []
        for name, val in [("SUPABASE_URL", cls.SUPABASE_URL),
                          ("SUPABASE_ANON_KEY", cls.SUPABASE_ANON_KEY),
                          ("SUPABASE_SERVICE_KEY", cls.SUPABASE_SERVICE_KEY)]:
            if not val or any(p in val for p in _PLACEHOLDERS):
                errors.append(f"  {name} is missing or still a placeholder")

        if not cls.FIREBASE_SERVICE_ACCOUNT_JSON or \
           cls.FIREBASE_SERVICE_ACCOUNT_JSON == "paste-your-firebase-service-account-json-here":
            errors.append("  FIREBASE_SERVICE_ACCOUNT_JSON is missing — "
                          "see Firebase Console → Project Settings → Service Accounts")

        if errors:
            raise RuntimeError("\n[CONFIG ERROR] Fix backend/.env:\n" + "\n".join(errors) + "\n")
