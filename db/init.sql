-- ============================================================
-- Multi-Tenant SaaS Attendance System Schema v3.0
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── Plans ──────────────────────────────────────────────────
CREATE TABLE plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL UNIQUE,          -- "Free", "Pro", "Enterprise"
    slug VARCHAR(30) NOT NULL UNIQUE,          -- "free", "pro", "enterprise"
    description TEXT,
    price_monthly DECIMAL(10,2) DEFAULT 0,
    price_yearly DECIMAL(10,2) DEFAULT 0,
    max_employees INT DEFAULT 10,
    max_geofences INT DEFAULT 2,
    face_verification BOOLEAN DEFAULT true,
    webhooks BOOLEAN DEFAULT false,
    ai_chat BOOLEAN DEFAULT false,
    export_reports BOOLEAN DEFAULT true,
    priority_support BOOLEAN DEFAULT false,
    custom_branding BOOLEAN DEFAULT false,
    api_access BOOLEAN DEFAULT false,
    trial_days INT DEFAULT 14,                 -- días de prueba
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Seed default plans
INSERT INTO plans (name, slug, description, price_monthly, price_yearly, max_employees, max_geofences, face_verification, webhooks, ai_chat, trial_days) VALUES
('Gratis', 'free', 'Hasta 10 empleados, funciones básicas', 0, 0, 10, 2, true, false, false, 0),
('Pro', 'pro', 'Hasta 50 empleados, todas las funciones', 299.00, 2990.00, 50, 10, true, true, true, 14),
('Enterprise', 'enterprise', 'Sin límites, soporte prioritario, API', 999.00, 9990.00, 999999, 999999, true, true, true, 30);

-- ─── Companies (tenants) ────────────────────────────────────
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID REFERENCES plans(id) DEFAULT (SELECT id FROM plans WHERE slug = 'free'),
    name VARCHAR(150) NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL,
    admin_email VARCHAR(100) UNIQUE NOT NULL,
    admin_password_hash VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'trial',         -- trial, active, grace, suspended, cancelled
    trial_ends_at TIMESTAMP,
    subscription_ends_at TIMESTAMP,
    last_payment_at TIMESTAMP,
    suspended_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    max_employees_override INT,                 -- override del plan
    active BOOLEAN DEFAULT true,
    rfc VARCHAR(20),                            -- tax ID (optional)
    billing_name VARCHAR(150),
    billing_address TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_companies_slug ON companies(slug);
CREATE INDEX idx_companies_status ON companies(status);
CREATE INDEX idx_companies_plan ON companies(plan_id);
CREATE INDEX idx_companies_trial_end ON companies(trial_ends_at);

-- ─── Company configuration (one per company) ────────────────
CREATE TABLE company_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE UNIQUE,
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
);

CREATE INDEX idx_company_config_company ON company_config(company_id);

-- ─── Employees ──────────────────────────────────────────────
CREATE TABLE employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'employee',
    active BOOLEAN DEFAULT true,
    face_reference_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(company_id, email)
);

CREATE INDEX idx_employees_company ON employees(company_id);
CREATE INDEX idx_employees_active ON employees(company_id, active);

-- ─── Schedules ──────────────────────────────────────────────
CREATE TABLE schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    employee_id UUID REFERENCES employees(id) ON DELETE CASCADE,
    day_of_week INT[] NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    tolerance_minutes INT DEFAULT 5
);

CREATE INDEX idx_schedules_company ON schedules(company_id);

-- ─── Geofences ──────────────────────────────────────────────
CREATE TABLE geofences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    latitude DECIMAL(10,8) NOT NULL,
    longitude DECIMAL(11,8) NOT NULL,
    radius_meters INT DEFAULT 100
);

CREATE INDEX idx_geofences_company ON geofences(company_id);

-- ─── Employee <-> Geofence ──────────────────────────────────
CREATE TABLE employee_geofences (
    employee_id UUID REFERENCES employees(id) ON DELETE CASCADE,
    geofence_id UUID REFERENCES geofences(id) ON DELETE CASCADE,
    PRIMARY KEY (employee_id, geofence_id)
);

-- ─── Attendance logs ────────────────────────────────────────
CREATE TABLE attendance_logs (
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
);

CREATE INDEX idx_attendance_company ON attendance_logs(company_id);
CREATE INDEX idx_attendance_employee_id ON attendance_logs(employee_id);
CREATE INDEX idx_attendance_timestamp ON attendance_logs(timestamp);
CREATE INDEX idx_attendance_type ON attendance_logs(type);

-- ─── Streaks ────────────────────────────────────────────────
CREATE TABLE streaks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    employee_id UUID REFERENCES employees(id) ON DELETE CASCADE UNIQUE,
    current_streak INT DEFAULT 0,
    last_on_time_date DATE,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_streaks_company ON streaks(company_id);

-- ─── Bonus records ──────────────────────────────────────────
CREATE TABLE bonus_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    employee_id UUID REFERENCES employees(id) ON DELETE CASCADE,
    month DATE NOT NULL,
    streak_achieved INT DEFAULT 0,
    bonus_earned BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(employee_id, month)
);

CREATE INDEX idx_bonus_company ON bonus_records(company_id);

-- ─── Subscriptions ──────────────────────────────────────────
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE UNIQUE,
    plan_id UUID REFERENCES plans(id),
    status VARCHAR(20) DEFAULT 'trial',         -- trial, active, past_due, cancelled, expired
    mercado_pago_id VARCHAR(100),               -- MP preapproval/subscription ID
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    cancel_at_period_end BOOLEAN DEFAULT false,
    trial_start TIMESTAMP,
    trial_end TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_subscriptions_company ON subscriptions(company_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_subscriptions_period_end ON subscriptions(current_period_end);

-- ─── Invoices ───────────────────────────────────────────────
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(id),
    invoice_number VARCHAR(30) UNIQUE NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'UYU',
    status VARCHAR(20) DEFAULT 'pending',       -- pending, paid, failed, cancelled, refunded
    due_date TIMESTAMP,
    paid_at TIMESTAMP,
    mercado_pago_payment_id VARCHAR(100),
    pdf_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_invoices_company ON invoices(company_id);
CREATE INDEX idx_invoices_status ON invoices(status);

-- ─── Payments ───────────────────────────────────────────────
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    invoice_id UUID REFERENCES invoices(id),
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'UYU',
    method VARCHAR(30),                         -- card, pix, transfer, cash
    mercado_pago_id VARCHAR(100),
    mercado_pago_status VARCHAR(30),            -- approved, pending, rejected, refunded
    raw_response JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_payments_company ON payments(company_id);
CREATE INDEX idx_payments_status ON payments(mercado_pago_status);

-- ─── Password Reset Requests ────────────────────────────────
CREATE TABLE password_reset_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID REFERENCES employees(id) ON DELETE CASCADE,
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    token VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, fulfilled, expired
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_password_reset_employee ON password_reset_requests(employee_id);
CREATE INDEX idx_password_reset_token ON password_reset_requests(token);

-- ─── MercadoPago OAuth Tokens ───────────────────────────────
CREATE TABLE mp_oauth_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ─── Audit Logs ─────────────────────────────────────────────
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    user_id UUID,                               -- can be NULL for system actions
    action VARCHAR(50) NOT NULL,                -- "employee_created", "plan_changed", etc.
    resource VARCHAR(50),                       -- "employee", "company", "plan", "subscription"
    resource_id UUID,
    details JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_company ON audit_logs(company_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_created_at ON audit_logs(created_at);

-- ─── Seed: Default company + admin + subscription ───────────
-- Password: admin123
INSERT INTO companies (plan_id, name, slug, admin_email, admin_password_hash, status, trial_ends_at)
VALUES (
    (SELECT id FROM plans WHERE slug = 'free'),
    'Mi Empresa',
    'mi-empresa',
    'admin@miempresa.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/lfBFRQHWMFCXp7hJi',
    'active',
    NOW() + INTERVAL '14 days'
);

-- Create config for default company
INSERT INTO company_config (company_id, company_name)
SELECT id, 'Mi Empresa' FROM companies WHERE slug = 'mi-empresa';

-- Create admin employee linked to company
INSERT INTO employees (company_id, name, email, password_hash, role)
SELECT id, 'Administrador', 'admin@miempresa.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/lfBFRQHWMFCXp7hJi',
    'admin'
FROM companies WHERE slug = 'mi-empresa';

-- Create subscription for default company
INSERT INTO subscriptions (company_id, plan_id, status, trial_start, trial_end)
SELECT
    c.id,
    c.plan_id,
    'trial',
    NOW(),
    c.trial_ends_at
FROM companies c WHERE c.slug = 'mi-empresa';
