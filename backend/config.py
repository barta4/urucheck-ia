import logging
import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict

_logger = logging.getLogger(__name__)

# Known insecure defaults that MUST NOT be used in production.
_INSECURE_SECRET_KEYS = frozenset({
    "",
    "b3dHRW5MrXuZaa4MvD9FPqxrIP2zZU4c",  # old hardcoded default
    "changeme",
    "secret",
})


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://attendance_user:password@localhost:5432/attendance_db"
    # ⚠️  MUST be set via SECRET_KEY env var — no safe default.
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    # Reduced from 7 days to 24 hours — shorter window if token is compromised
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    PHOTOS_PATH: str = "/app/photos"
    FRONTEND_URL: str = "http://localhost"
    GEMINI_API_KEY: str = ""
    BONUS_STREAK_DAYS: int = 20  # days needed for bonus
    TIMEZONE: str = "America/Montevideo"
    DEBUG: bool = False  # Set True only in local development

    # --- Seed / Super-admin ---
    # Used only on first boot if the seed company does not exist yet.
    SEED_ADMIN_PASSWORD: str | None = None
    SUPER_ADMIN_EMAIL: str = "admin@miempresa.com"

    # --- GPS / Attendance ---
    # Reject check-ins with GPS accuracy worse than this value (meters)
    MAX_GPS_ACCURACY_METERS: float = 150.0
    # Push reminder N minutes before break end (window: N to N+5 min)
    BREAK_REMINDER_WINDOW_START: int = 55

    # --- Face verification ---
    FACE_VERIFICATION_ENABLED: bool = False
    FACE_VERIFICATION_PROVIDER: str = "face_recognition"  # face_recognition | gemini_vision
    FACE_VERIFICATION_THRESHOLD: float = 0.6

    # --- MercadoPago ---
    MERCADOPAGO_ACCESS_TOKEN: str = ""
    MERCADOPAGO_WEBHOOK_SECRET: str = ""

    # --- Encryption at Rest (Fernet key) ---
    ENCRYPTION_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()

# ─── Post-init: validate SECRET_KEY ──────────────────────────────────────────
if settings.SECRET_KEY in _INSECURE_SECRET_KEYS:
    _generated = secrets.token_urlsafe(32)
    _logger.warning(
        "⚠️  SECRET_KEY no configurada o usa un valor inseguro conocido. "
        "Se generó una clave temporal aleatoria. Los tokens JWT NO sobrevivirán "
        "reinicios del servidor. Defina SECRET_KEY en sus variables de entorno."
    )
    settings.SECRET_KEY = _generated
