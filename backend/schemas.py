import re
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime, date, time
from uuid import UUID
from decimal import Decimal


def validate_password_complexity(password: str) -> str:
    """
    Validates that a password satisfies minimum security complexity:
    - At least 8 characters
    - At least 1 numeric digit
    - At least 1 uppercase letter
    """
    if not password or len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    if not re.search(r"\d", password):
        raise ValueError("La contraseña debe incluir al menos un número.")
    if not re.search(r"[A-Z]", password):
        raise ValueError("La contraseña debe incluir al menos una letra mayúscula.")
    return password


# ─── Auth ─────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_id: Optional[str] = None
    company_slug: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    name: str
    role: str
    company_id: str
    company_name: str
    company_slug: str
    company_status: str
    is_super_admin: bool = False

# ─── Company Registration ─────────────────────────────────────
class CompanyCreate(BaseModel):
    name: str
    slug: str
    admin_email: EmailStr
    admin_password: str
    plan_slug: str = "free"
    billing_name: Optional[str] = None
    rfc: Optional[str] = None

    @field_validator("admin_password")
    @classmethod
    def validate_admin_pwd(cls, v: str) -> str:
        return validate_password_complexity(v)

class CompanyOut(BaseModel):
    id: UUID
    name: str
    slug: str
    admin_email: str
    plan_id: Optional[UUID] = None
    status: str
    trial_ends_at: Optional[datetime] = None
    active: bool
    created_at: datetime

class CompanyStatusUpdate(BaseModel):
    status: str

# ─── Plans ────────────────────────────────────────────────────
class PlanCreate(BaseModel):
    name: str
    slug: str
    description: str = ""
    price_monthly: Decimal = 0
    price_yearly: Decimal = 0
    max_employees: int = 10
    max_geofences: int = 2
    face_verification: bool = True
    webhooks: bool = False
    ai_chat: bool = False
    export_reports: bool = True
    priority_support: bool = False
    custom_branding: bool = False
    api_access: bool = False
    trial_days: int = 14

class PlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_monthly: Optional[Decimal] = None
    price_yearly: Optional[Decimal] = None
    max_employees: Optional[int] = None
    max_geofences: Optional[int] = None
    face_verification: Optional[bool] = None
    webhooks: Optional[bool] = None
    ai_chat: Optional[bool] = None
    trial_days: Optional[int] = None
    active: Optional[bool] = None

class PlanOut(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str
    price_monthly: Decimal
    price_yearly: Decimal
    max_employees: int
    max_geofences: int
    face_verification: bool
    webhooks: bool
    ai_chat: bool
    export_reports: bool
    priority_support: bool
    custom_branding: bool
    api_access: bool
    trial_days: int
    active: bool
    created_at: datetime

# ─── Subscription ─────────────────────────────────────────────
class SubscriptionOut(BaseModel):
    id: UUID
    company_id: UUID
    plan_id: Optional[UUID] = None
    plan_name: Optional[str] = None
    status: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    cancel_at_period_end: bool
    created_at: datetime

class ChangePlanRequest(BaseModel):
    plan_id: UUID

# ─── Invoice ──────────────────────────────────────────────────
class InvoiceOut(BaseModel):
    id: UUID
    company_id: UUID
    invoice_number: str
    amount: Decimal
    currency: str
    status: str
    due_date: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime

# ─── Payment ──────────────────────────────────────────────────
class PaymentOut(BaseModel):
    id: UUID
    company_id: UUID
    invoice_id: Optional[UUID] = None
    amount: Decimal
    method: Optional[str] = None
    mercado_pago_status: Optional[str] = None
    created_at: datetime

# ─── Employee ─────────────────────────────────────────────────
class EmployeeCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "employee"
    document_id: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_employee_pwd(cls, v: str) -> str:
        return validate_password_complexity(v)

class EmployeeBulkItem(BaseModel):
    name: str
    email: EmailStr
    password: Optional[str] = None
    role: str = "employee"
    document_id: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_bulk_pwd(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return validate_password_complexity(v)
        return None

class EmployeeBulkCreate(BaseModel):
    employees: List[EmployeeBulkItem]

class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    active: Optional[bool] = None
    document_id: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_update_pwd(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return validate_password_complexity(v)
        return None

class EmployeeOut(BaseModel):
    id: UUID
    name: str
    email: str
    role: str
    active: bool
    created_at: datetime
    document_id: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None

# ─── Schedule ─────────────────────────────────────────────────
class ScheduleCreate(BaseModel):
    employee_id: UUID
    day_of_week: List[int]
    start_time: time
    end_time: time
    slot_name: Optional[str] = None
    tolerance_minutes: int = 5
    geofence_id: Optional[UUID] = None
    break_mode: str = "flexible"  # "none" | "flexible" | "fixed"
    break_duration_minutes: Optional[int] = 45
    break_start_time: Optional[time] = None
    break_end_time: Optional[time] = None

class ScheduleOut(BaseModel):
    id: UUID
    employee_id: UUID
    day_of_week: List[int]
    start_time: time
    end_time: time
    slot_name: Optional[str] = None
    tolerance_minutes: int
    geofence_id: Optional[UUID] = None
    break_mode: Optional[str] = "flexible"
    break_duration_minutes: Optional[int] = 45
    break_start_time: Optional[time] = None
    break_end_time: Optional[time] = None

# ─── Geofence ─────────────────────────────────────────────────
class GeofenceCreate(BaseModel):
    name: str
    latitude: float
    longitude: float
    radius_meters: int = 100

class GeofenceOut(BaseModel):
    id: UUID
    name: str
    latitude: float
    longitude: float
    radius_meters: int

# ─── Attendance / Webhook ─────────────────────────────────────
class AttendanceMark(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gps_accuracy: Optional[float] = None
    device_timestamp: Optional[str] = None

class AttendanceResponse(BaseModel):
    status: str
    alert_type: str
    title: str
    message: str
    streak: Optional[int] = None
    days_to_bonus: Optional[int] = None
    streak_message: Optional[str] = None
    next_action: Optional[str] = None
    log_id: Optional[str] = None
    face_verified: Optional[bool] = None
    face_confidence: Optional[float] = None
    early_departure: Optional[bool] = False
    early_minutes: Optional[int] = 0
    slot_name: Optional[str] = None
    geofence_name: Optional[str] = None
    expected_end_time: Optional[str] = None

# ─── Reports ──────────────────────────────────────────────────
class BonusReport(BaseModel):
    employee_id: UUID
    employee_name: str
    email: str
    month: date
    streak_achieved: int
    bonus_earned: bool

# ─── Audit Log ────────────────────────────────────────────────
class AuditLogOut(BaseModel):
    id: UUID
    company_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    action: str
    resource: Optional[str] = None
    resource_id: Optional[UUID] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime

# ─── SaaS Metrics ─────────────────────────────────────────────
class SaasMetrics(BaseModel):
    total_companies: int
    active_companies: int
    trial_companies: int
    suspended_companies: int
    cancelled_companies: int
    mrr: Decimal
    arr: Decimal
    churn_rate: float
    total_revenue: Decimal
    total_employees_all: int
    plans_distribution: dict
    recent_signups: int
    expiring_trials: int
