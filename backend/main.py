from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from jose import jwt
import logging
import os
import traceback
from datetime import datetime, timezone

from database import database
from config import settings
from auth import get_password_hash
from routers import (
    auth, attendance, employees, dashboard, company, chat,
    privacy, data_rights, companies, plans, subscriptions,
    payments, audit, metrics, password_reset, notifications, leaves, locations,
)

# ─── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.connect()

    # ─── 0. Ensure pgcrypto extension exists ───
    try:
        await database.execute("CREATE EXTENSION IF NOT EXISTS \"pgcrypto\"")
    except Exception:
        pass

    # ─── 1. Create new tables if upgrading from older version ───
    create_tables = [
        # Original tables (in case DB was created with older init.sql)
        """CREATE TABLE IF NOT EXISTS company_config (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID,
            company_name VARCHAR(150) NOT NULL DEFAULT 'Mi Empresa',
            logo_path VARCHAR(255),
            primary_color VARCHAR(7) DEFAULT '#2563eb',
            accent_color VARCHAR(7) DEFAULT '#1d4ed8',
            webhook_url VARCHAR(255),
            bonus_success_message VARCHAR(255) DEFAULT '¡Bonus asegurado!',
            bonus_pending_message VARCHAR(255) DEFAULT 'Faltan {days} días para asegurar tu bono.',
            face_verification_enabled BOOLEAN DEFAULT false,
            face_verification_provider VARCHAR(30) DEFAULT 'face_recognition',
            webhook_notify_checkin BOOLEAN DEFAULT false,
            webhook_notify_checkout BOOLEAN DEFAULT false,
            webhook_notify_break BOOLEAN DEFAULT false,
            webhook_notify_late BOOLEAN DEFAULT false,
            webhook_notify_absence BOOLEAN DEFAULT false,
            updated_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS companies (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            plan_id UUID, name VARCHAR(150) NOT NULL DEFAULT 'Mi Empresa',
            slug VARCHAR(50) UNIQUE, admin_email VARCHAR(100) UNIQUE,
            admin_password_hash VARCHAR(255), status VARCHAR(20) DEFAULT 'trial',
            trial_ends_at TIMESTAMP, subscription_ends_at TIMESTAMP,
            last_payment_at TIMESTAMP, suspended_at TIMESTAMP, cancelled_at TIMESTAMP,
            max_employees_override INT, active BOOLEAN DEFAULT true,
            rfc VARCHAR(20), billing_name VARCHAR(150), billing_address TEXT,
            created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS plans (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(50) NOT NULL UNIQUE, slug VARCHAR(30) NOT NULL UNIQUE,
            description TEXT, price_monthly DECIMAL(10,2) DEFAULT 0,
            price_yearly DECIMAL(10,2) DEFAULT 0,
            max_employees INT DEFAULT 10, max_geofences INT DEFAULT 2,
            face_verification BOOLEAN DEFAULT true, webhooks BOOLEAN DEFAULT false,
            ai_chat BOOLEAN DEFAULT false, export_reports BOOLEAN DEFAULT true,
            priority_support BOOLEAN DEFAULT false, custom_branding BOOLEAN DEFAULT false,
            api_access BOOLEAN DEFAULT false, trial_days INT DEFAULT 14,
            active BOOLEAN DEFAULT true, created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS subscriptions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID, plan_id UUID, status VARCHAR(20) DEFAULT 'trial',
            mercado_pago_id VARCHAR(100), current_period_start TIMESTAMP,
            current_period_end TIMESTAMP, cancel_at_period_end BOOLEAN DEFAULT false,
            trial_start TIMESTAMP, trial_end TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS invoices (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID, subscription_id UUID,
            invoice_number VARCHAR(30) UNIQUE, amount DECIMAL(10,2) NOT NULL,
            currency VARCHAR(3) DEFAULT 'UYU', status VARCHAR(20) DEFAULT 'pending',
            due_date TIMESTAMP, paid_at TIMESTAMP,
            mercado_pago_payment_id VARCHAR(100), pdf_path VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS payments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID, invoice_id UUID,
            amount DECIMAL(10,2) NOT NULL, currency VARCHAR(3) DEFAULT 'UYU',
            method VARCHAR(30), mercado_pago_id VARCHAR(100),
            mercado_pago_status VARCHAR(30), raw_response JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS mp_oauth_tokens (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            access_token TEXT NOT NULL, refresh_token TEXT NOT NULL,
            expires_at DOUBLE PRECISION, created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS password_reset_requests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            employee_id UUID, company_id UUID, token VARCHAR(100) NOT NULL,
            status VARCHAR(20) DEFAULT 'pending', created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS audit_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID, user_id UUID, action VARCHAR(50) NOT NULL,
            resource VARCHAR(50), resource_id UUID, details JSONB,
            ip_address VARCHAR(45), user_agent TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS employees (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) DEFAULT 'employee',
            active BOOLEAN DEFAULT true,
            face_reference_path VARCHAR(255),
            expo_push_token VARCHAR(255),
            device_id VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(company_id, email)
        )""",
        """CREATE TABLE IF NOT EXISTS schedules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
            employee_id UUID REFERENCES employees(id) ON DELETE CASCADE,
            day_of_week INT[] NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            tolerance_minutes INT DEFAULT 5
        )""",
        """CREATE TABLE IF NOT EXISTS geofences (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            latitude DECIMAL(10,8) NOT NULL,
            longitude DECIMAL(11,8) NOT NULL,
            radius_meters INT DEFAULT 100
        )""",
        """CREATE TABLE IF NOT EXISTS employee_geofences (
            employee_id UUID REFERENCES employees(id) ON DELETE CASCADE,
            geofence_id UUID REFERENCES geofences(id) ON DELETE CASCADE,
            PRIMARY KEY (employee_id, geofence_id)
        )""",
        """CREATE TABLE IF NOT EXISTS attendance_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
            employee_id UUID REFERENCES employees(id) ON DELETE CASCADE,
            type VARCHAR(20) NOT NULL CHECK (type IN ('check_in','break_start','break_end','check_out')),
            timestamp TIMESTAMP NOT NULL,
            latitude DECIMAL(10,8),
            longitude DECIMAL(11,8),
            gps_accuracy FLOAT,
            photo_path VARCHAR(255),
            status VARCHAR(20) CHECK (status IN ('on_time','late','warning')),
            streak_day INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS streaks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
            employee_id UUID REFERENCES employees(id) ON DELETE CASCADE UNIQUE,
            current_streak INT DEFAULT 0,
            last_on_time_date DATE,
            updated_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS bonus_records (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
            employee_id UUID REFERENCES employees(id) ON DELETE CASCADE,
            month DATE NOT NULL,
            streak_achieved INT DEFAULT 0,
            bonus_earned BOOLEAN DEFAULT false,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(employee_id, month)
        )""",
        """CREATE TABLE IF NOT EXISTS leave_requests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
            employee_id UUID REFERENCES employees(id) ON DELETE CASCADE,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            reason VARCHAR(50) NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            certificate_path VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS saas_settings (
            id VARCHAR(100) PRIMARY KEY,
            value TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP DEFAULT NOW()
        )""",
        # Seed data (idempotent) — passwords are generated dynamically, NOT hardcoded
        "INSERT INTO plans (name, slug, description, price_monthly, price_yearly, max_employees, max_geofences, face_verification, webhooks, ai_chat, trial_days) SELECT 'Gratis', 'free', 'Hasta 10 empleados', 0, 0, 10, 2, true, false, false, 0 WHERE NOT EXISTS (SELECT 1 FROM plans WHERE slug = 'free')",
        "INSERT INTO plans (name, slug, description, price_monthly, price_yearly, max_employees, max_geofences, face_verification, webhooks, ai_chat, trial_days) SELECT 'Pro', 'pro', 'Hasta 50 empleados, todas las funciones', 299, 2990, 50, 10, true, true, true, 14 WHERE NOT EXISTS (SELECT 1 FROM plans WHERE slug = 'pro')",
        "INSERT INTO plans (name, slug, description, price_monthly, price_yearly, max_employees, max_geofences, face_verification, webhooks, ai_chat, trial_days) SELECT 'Enterprise', 'enterprise', 'Sin límites, soporte prioritario', 999, 9990, 999999, 999999, true, true, true, 30 WHERE NOT EXISTS (SELECT 1 FROM plans WHERE slug = 'enterprise')",
        "INSERT INTO saas_settings (id, value) VALUES ('apk_url', '') ON CONFLICT (id) DO NOTHING",
        "INSERT INTO saas_settings (id, value) VALUES ('ios_url', '') ON CONFLICT (id) DO NOTHING",
    ]
    for sql in create_tables:
        try:
            await database.execute(sql)
        except Exception as e:
            err_str = str(e).lower()
            if "already exists" not in err_str and "duplicate" not in err_str:
                logger.error("[Lifespan] Fallo al crear tabla o sembrar datos: %s. SQL: %.100s", e, sql)

    # ─── Seed admin company (parameterized — no f-string interpolation) ───
    if settings.SEED_ADMIN_PASSWORD:
        seed_email = settings.SUPER_ADMIN_EMAIL
        seed_hash = get_password_hash(settings.SEED_ADMIN_PASSWORD)
        seed_queries = [
            (
                "INSERT INTO companies (plan_id, name, slug, admin_email, admin_password_hash, status, trial_ends_at) "
                "SELECT (SELECT id FROM plans WHERE slug = 'free'), 'Mi Empresa', 'mi-empresa', :email, :hash, "
                "'active', NOW() + INTERVAL '14 days' "
                "WHERE NOT EXISTS (SELECT 1 FROM companies WHERE slug = 'mi-empresa')",
                {"email": seed_email, "hash": seed_hash},
            ),
            (
                "INSERT INTO company_config (company_id, company_name) "
                "SELECT id, 'Mi Empresa' FROM companies WHERE slug = 'mi-empresa' "
                "AND NOT EXISTS (SELECT 1 FROM company_config WHERE company_id = "
                "(SELECT id FROM companies WHERE slug = 'mi-empresa'))",
                None,
            ),
            (
                "INSERT INTO employees (company_id, name, email, password_hash, role) "
                "SELECT id, 'Administrador', :email, :hash, 'admin' "
                "FROM companies WHERE slug = 'mi-empresa' "
                "AND NOT EXISTS (SELECT 1 FROM employees WHERE email = :email)",
                {"email": seed_email, "hash": seed_hash},
            ),
            (
                "INSERT INTO subscriptions (company_id, plan_id, status, trial_start, trial_end) "
                "SELECT c.id, c.plan_id, 'trial', NOW(), c.trial_ends_at "
                "FROM companies c WHERE c.slug = 'mi-empresa' "
                "AND NOT EXISTS (SELECT 1 FROM subscriptions WHERE company_id = c.id)",
                None,
            ),
        ]
        for sql, params in seed_queries:
            try:
                if params:
                    await database.execute(sql, params)
                else:
                    await database.execute(sql)
            except Exception as e:
                err_str = str(e).lower()
                if "already exists" not in err_str and "duplicate" not in err_str:
                    logger.error("[Lifespan] Fallo al sembrar datos de admin: %s", e)

    # NOTE: Admin password is seeded only once during initial company creation.
    # Do NOT reset it here on every startup — that would overwrite ad    # ─── 2. Add missing columns (for upgrades) ───
    migrations = [
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS webhook_url VARCHAR(255);",
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS bonus_success_message VARCHAR(255) DEFAULT '¡Bonus asegurado!';",
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS bonus_pending_message VARCHAR(255) DEFAULT 'Faltan {days} días para asegurar tu bono.';",
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS webhook_notify_checkin BOOLEAN DEFAULT false;",
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS webhook_notify_checkout BOOLEAN DEFAULT false;",
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS webhook_notify_break BOOLEAN DEFAULT false;",
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS webhook_notify_late BOOLEAN DEFAULT false;",
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS webhook_notify_absence BOOLEAN DEFAULT false;",
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS face_verification_enabled BOOLEAN DEFAULT false;",
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS face_verification_provider VARCHAR(30) DEFAULT 'face_recognition';",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS face_reference_path VARCHAR(255);",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS expo_push_token VARCHAR(255);",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS device_id VARCHAR(255);",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id) ON DELETE CASCADE;",
        "ALTER TABLE attendance_logs ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id) ON DELETE CASCADE;",
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id) ON DELETE CASCADE;",
        "ALTER TABLE geofences ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id) ON DELETE CASCADE;",
        "ALTER TABLE streaks ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id) ON DELETE CASCADE;",
        "ALTER TABLE bonus_records ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id) ON DELETE CASCADE;",
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id) ON DELETE CASCADE;",
        "ALTER TABLE mp_oauth_tokens ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id) ON DELETE CASCADE;",
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS geofence_id UUID REFERENCES geofences(id) ON DELETE SET NULL;",
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS break_mode VARCHAR(20) DEFAULT 'flexible';",
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS break_start_time TIME;",
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS break_end_time TIME;",
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS slot_name VARCHAR(100);",
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS break_duration_minutes INT DEFAULT 45;",
        "ALTER TABLE attendance_logs ADD COLUMN IF NOT EXISTS schedule_id UUID REFERENCES schedules(id) ON DELETE SET NULL;",
        "ALTER TABLE attendance_logs ADD COLUMN IF NOT EXISTS early_minutes INT DEFAULT 0;",
        # Token expiry for password reset
        "ALTER TABLE password_reset_requests ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP;",
        # Employee extra fields
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS document_id VARCHAR(50);",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS address VARCHAR(255);",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS phone VARCHAR(50);",
        # SMTP Server Configuration for Company
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS smtp_host VARCHAR(150);",
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS smtp_port INT DEFAULT 587;",
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS smtp_username VARCHAR(100);",
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS smtp_password VARCHAR(255);",
        "ALTER TABLE company_config ALTER COLUMN smtp_password TYPE VARCHAR(255);",
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS smtp_from_email VARCHAR(100);",
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS smtp_to_email VARCHAR(100);",
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS email_notify_monthly_report BOOLEAN DEFAULT false;",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS is_super_admin BOOLEAN DEFAULT false;",
        # Company soft-delete and payment enhancements
        "ALTER TABLE companies ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS notes TEXT;",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS currency VARCHAR(3) DEFAULT 'USD';",
        "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS currency VARCHAR(3) DEFAULT 'USD';",
        "INSERT INTO saas_settings (id, value) VALUES ('mp_client_id', '') ON CONFLICT (id) DO NOTHING;",
        "INSERT INTO saas_settings (id, value) VALUES ('mp_client_secret', '') ON CONFLICT (id) DO NOTHING;",
        "INSERT INTO saas_settings (id, value) VALUES ('mp_access_token', '') ON CONFLICT (id) DO NOTHING;",
        "INSERT INTO saas_settings (id, value) VALUES ('mp_public_key', '') ON CONFLICT (id) DO NOTHING;",
        "INSERT INTO saas_settings (id, value) VALUES ('mp_webhook_secret', '') ON CONFLICT (id) DO NOTHING;",
        # Live tracking & on-demand location columns
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS live_tracking_enabled BOOLEAN DEFAULT false;",
        "ALTER TABLE company_config ADD COLUMN IF NOT EXISTS live_tracking_interval_minutes INT DEFAULT 15;",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS last_latitude DECIMAL(10,8);",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS last_longitude DECIMAL(11,8);",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS last_location_accuracy FLOAT;",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS last_location_at TIMESTAMP;",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS last_location_source VARCHAR(30);",
        "CREATE TABLE IF NOT EXISTS employee_location_reports (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), company_id UUID REFERENCES companies(id) ON DELETE CASCADE, employee_id UUID REFERENCES employees(id) ON DELETE CASCADE, latitude DECIMAL(10,8) NOT NULL, longitude DECIMAL(11,8) NOT NULL, accuracy FLOAT, battery_level FLOAT, source VARCHAR(30) DEFAULT 'on_demand', created_at TIMESTAMP DEFAULT NOW());",
        "CREATE INDEX IF NOT EXISTS idx_emp_loc_rep_comp ON employee_location_reports(company_id, created_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_emp_loc_rep_emp ON employee_location_reports(employee_id, created_at DESC);",
        "CREATE TABLE IF NOT EXISTS revoked_tokens (jti VARCHAR(64) PRIMARY KEY, expires_at TIMESTAMP WITH TIME ZONE);",
        "CREATE INDEX IF NOT EXISTS idx_revoked_tokens_exp ON revoked_tokens(expires_at);",
        # NOTE: super_admin flag is set via parameterized query below (not in this list).
        # ─── Performance indexes (idempotent) ───
        "CREATE INDEX IF NOT EXISTS idx_al_cid_eid ON attendance_logs(company_id, employee_id);",
        "CREATE INDEX IF NOT EXISTS idx_al_timestamp ON attendance_logs(timestamp DESC);",
        "CREATE INDEX IF NOT EXISTS idx_al_type ON attendance_logs(type);",
        "CREATE INDEX IF NOT EXISTS idx_schedules_cid_eid ON schedules(company_id, employee_id);",
        "CREATE INDEX IF NOT EXISTS idx_streaks_cid_eid ON streaks(company_id, employee_id);",
        "CREATE INDEX IF NOT EXISTS idx_audit_cid ON audit_logs(company_id, created_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_employees_cid ON employees(company_id);",
        "CREATE INDEX IF NOT EXISTS idx_payments_cid ON payments(company_id, created_at DESC);",
        # ─── Multi-tenant company_config guarantees ───
        "DELETE FROM company_config WHERE company_id IS NULL;",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_company_config_cid_unique ON company_config(company_id);",
        "INSERT INTO company_config (company_id, company_name) SELECT id, name FROM companies c WHERE NOT EXISTS (SELECT 1 FROM company_config cc WHERE cc.company_id = c.id);",
    ]

    for migration in migrations:
        try:
            await database.execute(migration)
        except Exception as e:
            err_str = str(e).lower()
            if "already exists" not in err_str and "duplicate" not in err_str:
                logger.error("[Lifespan] Fallo al aplicar migración: %s. SQL: %.100s", e, migration)

    # Set super_admin flag (parameterized — safe against injection)
    try:
        await database.execute(
            "UPDATE employees SET is_super_admin = true WHERE email = :email",
            {"email": settings.SUPER_ADMIN_EMAIL},
        )
    except Exception as e:
        logger.error("[Lifespan] Fallo al marcar super_admin: %s", e)

    from agent_controller import start_scheduler
    start_scheduler()

    yield
    await database.disconnect()

app = FastAPI(
    title="UruCheck IA (SaaS Multi-Empresa)",
    version="3.0.0",
    lifespan=lifespan
)

# ─── Rate Limiter ─────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

cors_origins = set()
for raw_origin in settings.FRONTEND_URL.split(","):
    cleaned = raw_origin.strip().rstrip("/")
    if cleaned:
        cors_origins.add(cleaned)
cors_origins.update(["http://localhost:3000", "http://localhost:5173", "http://localhost", "http://127.0.0.1:5173", "http://127.0.0.1:3000"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    expose_headers=["Content-Disposition"],
)

FIELD_TRANSLATIONS_ES = {
    "start_time": "Hora de entrada",
    "end_time": "Hora de salida",
    "day_of_week": "Días de la semana",
    "slot_name": "Nombre / Etiqueta del turno",
    "tolerance_minutes": "Tolerancia (minutos)",
    "geofence_id": "Ubicación / Geocerca",
    "break_mode": "Modalidad de descanso",
    "break_duration_minutes": "Duración del descanso",
    "break_start_time": "Hora de inicio del descanso",
    "break_end_time": "Hora de fin del descanso",
    "name": "Nombre completo",
    "email": "Correo electrónico",
    "password": "Contraseña",
    "role": "Rol",
    "document_id": "Documento / C.I.",
    "phone": "Teléfono",
    "address": "Dirección",
    "latitude": "Latitud GPS",
    "longitude": "Longitud GPS",
    "radius_meters": "Radio de geocerca (metros)",
    "gps_accuracy": "Precisión GPS",
    "device_timestamp": "Hora del dispositivo",
    "employee_id": "Empleado",
    "company_id": "Empresa",
    "company_slug": "Identificador de empresa",
}

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    sanitized_errors = []
    for err in exc.errors():
        err_copy = dict(err)
        if "ctx" in err_copy and isinstance(err_copy["ctx"], dict):
            ctx_copy = dict(err_copy["ctx"])
            for k, v in ctx_copy.items():
                if isinstance(v, Exception):
                    ctx_copy[k] = str(v)
            err_copy["ctx"] = ctx_copy
        sanitized_errors.append(err_copy)

        loc = err.get("loc", [])
        field_raw = str(loc[-1]) if loc else "campo"
        field_label = FIELD_TRANSLATIONS_ES.get(field_raw, field_raw)
        err_type = str(err.get("type", ""))
        msg = str(err.get("msg", ""))

        clean_msg = msg
        for prefix in ["Value error, ", "Assertion failed, "]:
            if clean_msg.startswith(prefix):
                clean_msg = clean_msg[len(prefix):]

        if "missing" in err_type:
            errors.append(f"El campo '{field_label}' es obligatorio y no fue completado.")
        elif "time" in err_type or "time" in msg.lower():
            errors.append(f"El campo '{field_label}' debe tener un formato de hora válido (ej. HH:MM).")
        elif "date" in err_type or "date" in msg.lower():
            errors.append(f"El campo '{field_label}' debe tener un formato de fecha válido (AAAA-MM-DD).")
        elif "integer" in err_type or "int" in err_type:
            errors.append(f"El campo '{field_label}' debe ser un número entero válido.")
        elif "float" in err_type or "number" in err_type:
            errors.append(f"El campo '{field_label}' debe ser un número válido.")
        elif "greater_than" in err_type:
            errors.append(f"El valor de '{field_label}' es inferior al mínimo permitido.")
        elif "less_than" in err_type:
            errors.append(f"El valor de '{field_label}' supera el límite máximo permitido.")
        elif "uuid" in err_type or "uuid" in msg.lower():
            errors.append(f"El campo '{field_label}' tiene un formato de identificador no válido.")
        else:
            if field_label.lower() in clean_msg.lower():
                errors.append(clean_msg if clean_msg.endswith(".") else f"{clean_msg}.")
            else:
                errors.append(f"Valor incorrecto en '{field_label}': {clean_msg}.")

    readable_detail = " | ".join(errors) if errors else "Datos del formulario incompletos o con formato inválido."
    return JSONResponse(status_code=422, content={"detail": readable_detail, "errors": jsonable_encoder(sanitized_errors)})

@app.exception_handler(Exception)
async def custom_exception_handler(request: Request, exc: Exception):
    # In debug mode include traceback; in production hide it to avoid leaking internals
    if settings.DEBUG:
        content = {"detail": str(exc), "traceback": traceback.format_exc()}
    else:
        content = {"detail": "Error interno del servidor. Por favor contacte a soporte."}
    return JSONResponse(status_code=500, content=content)

# ─── Routers ────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(attendance.router)
app.include_router(employees.router)
app.include_router(dashboard.router)
app.include_router(company.router)
app.include_router(chat.router)
app.include_router(privacy.router)
app.include_router(data_rights.router)
app.include_router(companies.router)
app.include_router(plans.router)
app.include_router(subscriptions.router)
app.include_router(payments.router)
app.include_router(audit.router)
app.include_router(metrics.router)
app.include_router(password_reset.router)
app.include_router(notifications.router)
app.include_router(leaves.router)
app.include_router(locations.router)

# Serve photos — protected against path traversal
@app.get("/api/photos/{filename}")
async def get_photo(filename: str, request: Request, token: str = None) -> FileResponse:
    """Authenticated photo serving with strict path traversal protection."""
    extracted_token = None
    if token:
        extracted_token = token
    else:
        authorization = request.headers.get("authorization")
        if authorization and authorization.startswith("Bearer "):
            extracted_token = authorization.replace("Bearer ", "")

    if not extracted_token:
        raise HTTPException(status_code=401, detail="No autorizado")

    try:
        payload = jwt.decode(extracted_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        company_id = payload.get("company_id")
        is_super_admin = payload.get("is_super_admin", False)
        if not user_id:
            raise HTTPException(status_code=401, detail="Token inválido")
            
        # Security: Tenant isolation check
        if not is_super_admin and company_id:
            valid_prefixes = (
                f"{company_id}_",
                f"logo_{company_id}_",
                f"face_{company_id}_",
                f"cert_{company_id}_"
            )
            # Support subdirectory paths (e.g. "logos/logo_xxx")
            basename = os.path.basename(filename)
            if not basename.startswith(valid_prefixes):
                raise HTTPException(status_code=403, detail="Acceso denegado a recursos de otra empresa")
                
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    # Security: reject filenames with path separators or dot-traversal sequences
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido")
    path = os.path.realpath(os.path.join(settings.PHOTOS_PATH, filename))
    base = os.path.realpath(settings.PHOTOS_PATH)
    if not path.startswith(base + os.sep) and path != base:
        raise HTTPException(status_code=400, detail="Acceso denegado")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    return FileResponse(path)


@app.get("/api/health")
async def health() -> dict:
    """Public health-check endpoint with database probe."""
    db_status = "ok"
    try:
        await database.fetch_one("SELECT 1")
    except Exception as e:
        db_status = f"error: {str(e)}"

    overall = "ok" if db_status == "ok" else "degraded"
    return {
        "status": overall,
        "database": db_status,
        "service": "attendance-api",
        "version": "3.0.1",
        "build_version": "v2.16",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
