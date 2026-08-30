# 📘 Manual del Sistema — Control de Asistencia SaaS

> **Versión:** 3.1.0  
> **Tipo:** SaaS Multi-Empresa con reconocimiento facial  
> **Stack:** FastAPI + React + React Native + PostgreSQL + Nginx

---

## 📋 Tabla de Contenidos

1. [Arquitectura del Sistema](#1-arquitectura-del-sistema)
2. [Instalación y Deploy](#2-instalación-y-deploy)
3. [Configuración (.env)](#3-configuración-env)
4. [Base de Datos](#4-base-de-datos)
5. [API Completa](#5-api-completa)
6. [App Móvil](#6-app-móvil)
7. [Panel de Administración](#7-panel-de-administración)
8. [Panel Super-Admin (SaaS)](#8-panel-super-admin-saas)
9. [Reconocimiento Facial](#9-reconocimiento-facial)
10. [Modo Offline](#10-modo-offline)
11. [Seguridad y Cumplimiento Legal](#11-seguridad-y-cumplimiento-legal)
12. [Ciclo de Vida de Empresas](#12-ciclo-de-vida-de-empresas)
13. [Planes y Límites](#13-planes-y-límites)
14. [Troubleshooting](#14-troubleshooting)
15. [Backup y Restauración](#15-backup-y-restauración)

---

## 1. Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────┐
│                    INTERNET                              │
└──────────────────────┬──────────────────────────────────┘
                       │
              ┌────────▼────────┐
              │     Nginx       │  Puertos: 8080 (HTTP), 8443 (HTTPS)
              │  Reverse Proxy  │  Rutea /api/* → backend, /* → frontend
              └────┬───────┬────┘
                   │       │
        ┌──────────▼─┐   ┌─▼────────────┐
        │  Backend   │   │  Frontend    │
        │  FastAPI   │   │  React+Vite  │
        │  :8000     │   │  :80 (int)   │
        └─────┬──────┘   └──────────────┘
              │
     ┌────────▼────────┐
     │   PostgreSQL    │
     │   :5432         │
     │  Attendance DB  │
     └─────────────────┘

  ┌─────────────────────┐
  │  App Móvil (Expo)   │  ← Se conecta al backend via HTTP
  │  React Native       │     (no pasa por Nginx)
  └─────────────────────┘
```

### Servicios Docker:

| Servicio | Imagen | Puerto | Función |
|---|---|---|---|
| `attendance_db` | postgres:16-alpine | 5432 (interno) | Base de datos |
| `attendance_api` | build: ./backend | 8000 (interno) | API REST (FastAPI) |
| `attendance_admin` | build: ./frontend-admin | 80 (interno) | Panel web admin |
| `attendance_nginx` | nginx:alpine | 8080, 8443 (host) | Reverse proxy |

### Volúmenes persistentes:

| Volumen | Contenido |
|---|---|
| `postgres_data` | Archivos de PostgreSQL (BD completa) |
| `photos_data` | Fotos de verificación, logos, referencias faciales |

---

## 2. Instalación y Deploy

### Requisitos:
- Docker + Docker Compose v2
- Linux con 2GB+ RAM, 10GB+ disco
- Puerto 8080 disponible (8443 opcional para HTTPS)

### Paso a paso:

```bash
# 1. Clonar o copiar el proyecto
cd ~/Escritorio/proyectos/AssitenciaIA

# 2. Configurar variables de entorno
cp .env.example .env
nano .env   # Editar las claves y URLs

# 3. Construir y levantar
docker compose up -d --build

# 4. Verificar
docker compose ps
curl http://localhost:8080/api/health
# → {"status":"ok","service":"attendance-api","version":"3.1.0"}

# 5. Acceder al panel admin
# http://localhost:8080/login
# Email: admin@miempresa.com
# Password: admin123
```

### Para producción (HTTPS):

```bash
# 1. Crear directorio de certificados
mkdir -p nginx/certs

# 2. Copiar certificados SSL
cp cert.pem nginx/certs/
cp key.pem nginx/certs/

# 3. Editar nginx/nginx.conf — descomentar bloque SSL
# 4. Rebuild
docker compose up -d --build nginx
```

### Actualización del sistema:

```bash
# 1. Bajar servicios
docker compose down

# 2. Pull de los nuevos archivos
# (copiar los archivos actualizados al directorio)

# 3. Rebuild y levantar
docker compose up -d --build

# 4. Verificar
docker compose ps
curl http://localhost:8080/api/health
```

---

## 3. Configuración (.env)

```bash
# ─── Base de datos ────────────────────────────
DB_PASSWORD=supersecretpassword123

# ─── Seguridad JWT ────────────────────────────
SECRET_KEY=cambiar-por-una-clave-secreta-muy-larga-y-aleatoria-minimo-32-char

# ─── URLs ─────────────────────────────────────
FRONTEND_URL=http://localhost
VITE_API_URL=http://localhost/api

# ─── Reconocimiento facial ────────────────────
GEMINI_API_KEY=                 # Opcional — solo si usas Gemini como fallback
FACE_VERIFICATION_ENABLED=false # true = activar verificación facial
FACE_VERIFICATION_PROVIDER=face_recognition  # face_recognition | gemini_vision
FACE_VERIFICATION_THRESHOLD=0.6 # Umbral de similitud facial (0.6 = default dlib)

# ─── Pagos (MercadoPago) ──────────────────────
MERCADOPAGO_ACCESS_TOKEN=       # Token estático (solo lectura o production)
MERCADOPAGO_CLIENT_ID=          # Para OAuth con refresh automático
MERCADOPAGO_CLIENT_SECRET=      # Para OAuth con refresh automático
MERCADOPAGO_REDIRECT_URI=       # URL de callback OAuth

# ─── Rate Limiting ────────────────────────────
SLOWAPI_RATE_LIMIT=5/minute     # Máximos intentos de login por minuto
```

### Variables en la App Móvil (`mobile-app/app.config.js`):

```js
extra: {
  API_URL: "http://TU-IP-DEL-SERVIDOR:8080/api"
}
```

> ⚠️ Cambiar `192.168.1.17` por la IP real del servidor.

---

## 4. Base de Datos

### Tablas principales:

```
companies          → Empresas (tenants del SaaS)
  ├─ plans         → Definición de planes (Free, Pro, Enterprise)
  ├─ subscriptions → Suscripción activa de cada empresa
  └─ company_config → Configuración visual y de features

employees          → Empleados de cada empresa
  ├─ schedules     → Horarios asignados
  ├─ streaks       → Racha de puntualidad
  └─ bonus_records → Bonos ganados por mes

attendance_logs    → Registros de asistencia (check-in, break, check-out)
geofences          → Geocercas por empresa
employee_geofences → Asignación empleado ↔ geocerca

invoices           → Facturas generadas
payments           → Pagos procesados
mp_oauth_tokens    → Tokens de MercadoPago con auto-refresh
password_reset_requests → Solicitudes de reset de contraseña
audit_logs         → Log de todas las acciones del sistema
```

### Diagrama de relaciones:

```
companies (1) ──── (N) employees
   │                     │
   │                     ├── (N) schedules
   │                     ├── (N) streaks
   │                     ├── (N) attendance_logs
   │                     └── (N) employee_geofences
   │                              │
   │                     geofences (N)
   │
   ├── (1) company_config
   ├── (1) subscription ─── (1) plan
   ├── (N) invoices ─── (N) payments
   └── (N) audit_logs
```

---

## 5. API Completa

### Base URL:
```
http://localhost:8080/api
```

### Autenticación:

Todos los endpoints protegidos requieren header:
```
Authorization: Bearer <token>
```

### 5.1 Autenticación

#### `POST /auth/login`
Iniciar sesión.

**Request:**
```json
{
  "email": "admin@miempresa.com",
  "password": "admin123"
}
```

**Response 200:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user_id": "a1b2c3d4-...",
  "name": "Administrador",
  "role": "admin",
  "company_id": "x9y8z7w6-...",
  "company_name": "Mi Empresa",
  "company_slug": "mi-empresa",
  "company_status": "active"
}
```

**Response 401:**
```json
{ "detail": "Email o contraseña incorrectos" }
```

#### `POST /auth/forgot-password`
Solicitar restablecimiento de contraseña (crea registro para el admin).

**Request:**
```json
{ "email": "empleado@miempresa.com" }
```

**Response 200:**
```json
{ "message": "Solicitud enviada a tu administrador..." }
```

#### `POST /auth/reset-password` *(admin)*
Restablecer contraseña de un empleado.

**Request:**
```json
{
  "employee_id": "uuid-del-empleado",
  "new_password": "nuevaPassword123"
}
```

---

### 5.2 Asistencia

#### `POST /attendance/mark` *(autenticado)*
Marcar asistencia (check-in, break, check-out).

**Request (multipart/form-data):**
| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| latitude | float | ✅ | Latitud GPS |
| longitude | float | ✅ | Longitud GPS |
| gps_accuracy | float | Opcional | Precisión en metros |
| device_timestamp | string | Opcional | Timestamp del dispositivo (ISO 8601) |
| photo | file | Opcional | Selfie para verificación facial |

**Response 200 (éxito):**
```json
{
  "status": "on_time",
  "alert_type": "green",
  "title": "✅ Identidad verificada",
  "message": "Rostro verificado (92% confianza). ¡Excelente puntualidad!",
  "streak": 5,
  "days_to_bonus": 15,
  "streak_message": "Llevas 5 día(s) seguido(s). Faltan 15 días para asegurar tu bono.",
  "next_action": "break_start",
  "log_id": "uuid",
  "face_verified": true,
  "face_confidence": 0.92
}
```

**Response 200 (advertencia):**
```json
{
  "status": "late",
  "alert_type": "red",
  "title": "Llegada tarde registrada",
  "message": "Llegaste 12 minuto(s) tarde...",
  "streak": 0,
  "days_to_bonus": 20,
  "streak_message": "La racha de puntualidad se ha reiniciado."
}
```

#### `GET /attendance/today` *(autenticado)*
Obtener registros del día actual.

**Response:**
```json
{
  "logs": [
    { "id": "uuid", "type": "check_in", "timestamp": "2025-04-05T08:55:00", "status": "on_time" }
  ],
  "next_action": "break_start",
  "streak": 5,
  "days_to_bonus": 15
}
```

---

### 5.3 Empleados *(admin)*

#### `GET /employees/`
Listar empleados de la empresa.

#### `POST /employees/`
Crear empleado.

**Request:**
```json
{
  "name": "Juan Pérez",
  "email": "juan@miempresa.com",
  "password": "password123",
  "role": "employee"
}
```

#### `PATCH /employees/{employee_id}`
Actualizar empleado.

#### `DELETE /employees/{employee_id}`
Desactivar empleado (soft delete).

#### `GET /employees/{employee_id}/schedules`
Ver horarios del empleado.

#### `POST /employees/{employee_id}/schedules`
Asignar horario.

**Request:**
```json
{
  "day_of_week": [1, 2, 3, 4, 5],
  "start_time": "09:00",
  "end_time": "18:00",
  "tolerance_minutes": 5
}
```

#### `POST /employees/{employee_id}/face-enroll` *(admin)*
Registrar foto de referencia facial.

**Request (multipart):** `photo=<imagen>`

#### `DELETE /employees/{employee_id}/face-enroll` *(admin)*
Eliminar foto de referencia.

#### `GET /employees/{employee_id}/face-status` *(admin)*
Verificar si tiene foto facial registrada.

---

### 5.4 Dashboard *(admin)*

#### `GET /dashboard/today`
Estado en tiempo real de todos los empleados.

**Response:**
```json
{
  "summary": { "total": 10, "on_time": 7, "late": 1, "absent": 2, "pending": 0 },
  "employees": [
    {
      "employee_id": "uuid",
      "name": "Juan Pérez",
      "scheduled_start": "09:00:00",
      "status": "on_time",
      "check_in_time": "2025-04-05 08:55:00",
      "current_action": "check_in",
      "streak": 5
    }
  ]
}
```

#### `GET /dashboard/logs`
Registros de asistencia con filtros.

**Query params:**
| Param | Tipo | Descripción |
|---|---|---|
| employee_id | string | Filtrar por empleado |
| date_from | date | Desde (YYYY-MM-DD) |
| date_to | date | Hasta (YYYY-MM-DD) |
| status | string | `on_time`, `late`, `warning` |
| limit | int | Máximo registros (default: 100) |
| offset | int | Paginación (default: 0) |

#### `GET /dashboard/logs/export`
Exportar registros como Excel (.xlsx).

Mismos query params que `/dashboard/logs`.

#### `GET /dashboard/bonus-report?month=2025-04`
Reporte mensual de bonos.

#### `GET /dashboard/bonus-report/export?month=2025-04`
Exportar reporte de bonos como CSV.

#### `GET /dashboard/geofences`
Listar geocercas.

#### `POST /dashboard/geofences`
Crear geocerca.

**Request:**
```json
{
  "name": "Oficina Central",
  "latitude": -34.9011,
  "longitude": -56.1645,
  "radius_meters": 100
}
```

#### `POST /dashboard/geofences/{geofence_id}/assign/{employee_id}`
Asignar geocerca a empleado.

#### `DELETE /dashboard/geofences/{geofence_id}`
Eliminar geocerca.

---

### 5.4.1 Empresa *(autenticado)*

#### `GET /company/config`
Obtener configuración de la empresa (colores, logo, webhooks, etc.).

#### `PATCH /company/config` *(admin)*
Actualizar configuración (multipart/form-data).

| Campo | Tipo | Descripción |
|---|---|---|
| company_name | string | Nombre de la empresa |
| primary_color | string | Color primario (#hex) |
| accent_color | string | Color secundario (#hex) |
| webhook_url | string | URL del webhook |
| bonus_success_message | string | Mensaje de bono asegurado |
| bonus_pending_message | string | Mensaje de progreso de bono |
| face_verification_enabled | string | `true` / `false` |
| face_verification_provider | string | `face_recognition` / `gemini_vision` |
| webhook_notify_checkin | string | `true` / `false` |
| webhook_notify_checkout | string | `true` / `false` |
| webhook_notify_break | string | `true` / `false` |
| webhook_notify_late | string | `true` / `false` |
| webhook_notify_absence | string | `true` / `false` |
| logo | file | Logo de la empresa |

#### `GET /company/logo`
Obtener logo de la empresa.

#### `POST /company/webhook/test` *(admin)*
Probar webhook configurado.

---

### 5.5 Chat IA *(admin)*

#### `POST /chat/`
Enviar pregunta al asistente IA (Gemini).

**Request:**
```json
{ "message": "¿Quién llegó tarde hoy?" }
```

**Response:**
```json
{ "reply": "Hoy llegó tarde: Juan Pérez (12 minutos tarde a las 09:12)..." }
```

---

### 5.6 Privacidad y Derechos de Datos

#### `GET /privacy/privacy-policy`
Obtener política de privacidad completa (12 secciones, Ley 18.331).

#### `GET /privacy/legal-notice`
Aviso legal con metadata de cumplimiento URCDP.

#### `GET /data-rights/summary` *(autenticado)*
Resumen de datos personales almacenados.

**Response:**
```json
{
  "employee_id": "uuid",
  "registered_since": "2025-01-15T10:00:00",
  "data_held": {
    "face_reference_photo": true,
    "attendance_log_count": 45,
    "current_streak": 5,
    "geofence_assignments": 2
  },
  "retention_policy": {
    "verification_photos": "90 días",
    "face_reference_photo": "Relación laboral + 30 días",
    "attendance_logs": "2 años"
  }
}
```

#### `GET /data-rights/export` *(autenticado)*
Exportar todos los datos personales en JSON.

#### `GET /data-rights/export-csv` *(autenticado)*
Exportar registros de asistencia en CSV.

#### `POST /data-rights/delete-face-photo` *(autenticado)*
Eliminar foto de referencia facial.

#### `POST /data-rights/request-deletion` *(autenticado)*
Solicitar eliminación total de datos (ARCO+).

**Request:**
```json
{
  "delete_face_photo": true,
  "delete_attendance_logs": false,
  "reason": "Solicitud voluntaria del empleado"
}
```

---

### 5.7 SaaS — Empresas *(admin)*

#### `POST /companies/register`
Registrar nueva empresa (self-service).

**Request:**
```json
{
  "name": "Acme Corp",
  "slug": "acme-corp",
  "admin_email": "admin@acme.com",
  "admin_password": "secure123",
  "plan_slug": "free",
  "billing_name": "Acme Corp SRL",
  "rfc": "123456789"
}
```

**Response:**
```json
{
  "message": "Empresa 'Acme Corp' creada exitosamente. Tienes 14 días de prueba.",
  "company_id": "uuid",
  "company_slug": "acme-corp",
  "admin_token": "eyJhbGci...",
  "admin_id": "uuid",
  "admin_name": "Administrador"
}
```

#### `GET /companies/` *(admin)*
Listar todas las empresas.

#### `GET /companies/me` *(autenticado)*
Obtener datos de la empresa actual.

#### `PATCH /companies/{company_id}` *(admin)*
Cambiar estado de empresa (suspender, reactivar, cancelar).

**Request:** `{ "status": "suspended" }`

#### `POST /companies/{company_id}/assign-plan?plan_id=xxx` *(admin)*
Asignar plan a empresa.

---

### 5.8 SaaS — Planes *(admin)*

#### `GET /plans/`
Listar planes activos.

#### `GET /plans/all` *(admin)*
Listar todos los planes (incluidos inactivos).

#### `POST /plans/` *(admin)*
Crear nuevo plan.

**Request:**
```json
{
  "name": "Pro",
  "slug": "pro",
  "description": "Hasta 50 empleados con todas las funciones",
  "price_monthly": 299.00,
  "price_yearly": 2990.00,
  "max_employees": 50,
  "max_geofences": 10,
  "face_verification": true,
  "webhooks": true,
  "ai_chat": true,
  "export_reports": true,
  "priority_support": false,
  "custom_branding": false,
  "api_access": false,
  "trial_days": 14
}
```

#### `PATCH /plans/{plan_id}` *(admin)*
Actualizar plan.

#### `DELETE /plans/{plan_id}` *(admin)*
Eliminar plan (solo si ninguna empresa lo usa).

---

### 5.9 SaaS — Suscripciones *(autenticado)*

#### `GET /subscriptions/my`
Ver suscripción actual de la empresa.

**Response:**
```json
{
  "id": "uuid",
  "plan_name": "Pro",
  "plan_slug": "pro",
  "status": "trial",
  "current_period_end": "2025-05-05T00:00:00",
  "trial_start": "2025-04-05T00:00:00",
  "trial_end": "2025-04-19T00:00:00",
  "cancel_at_period_end": false,
  "trial_remaining_days": 14,
  "is_trial_active": true
}
```

#### `POST /subscriptions/change-plan` *(admin)*
Cambiar plan de la empresa.

**Request:**
```json
{ "plan_id": "uuid-del-nuevo-plan" }
```

#### `GET /subscriptions/check-feature/{feature}`
Verificar si una feature está incluida en el plan actual.

**Features válidas:** `face_verification`, `webhooks`, `ai_chat`, `export_reports`, `priority_support`, `custom_branding`, `api_access`

#### `GET /subscriptions/` *(admin)*
Listar todas las suscripciones.

---

### 5.10 SaaS — Pagos *(admin)*

#### `POST /payments/create-preference`
Crear preferencia de pago en MercadoPago.

**Query params:** `amount=299.00&description=Suscripción mensual Pro`

**Response:**
```json
{
  "preference_id": "123456-abc",
  "init_point": "https://www.mercadopago.com/checkout/...",
  "sandbox_init_point": "https://sandbox.mercadopago.com/checkout/..."
}
```

#### `POST /payments/webhook`
Webhook de MercadoPago (automático, no requiere auth).

#### `GET /payments/my` *(admin)*
Historial de pagos de la empresa.

---

### 5.11 SaaS — Métricas *(admin)*

#### `GET /saas-metrics/dashboard`
Dashboard completo con KPIs del SaaS.

**Response:**
```json
{
  "companies": { "total": 15, "active": 10, "trial": 3, "suspended": 1, "cancelled": 1 },
  "revenue": { "mrr": 2990.00, "arr": 35880.00, "total_revenue": 15000.00, "churn_rate": 6.67 },
  "usage": {
    "total_employees": 150,
    "plans_distribution": { "Gratis": 8, "Pro": 5, "Enterprise": 2 },
    "recent_signups": 2,
    "expiring_trials": 1,
    "top_companies": [
      { "name": "Acme Corp", "slug": "acme-corp", "log_count": 450 }
    ]
  },
  "recent_activity": [ ... ]
}
```

#### `GET /saas-metrics/companies`
Lista de empresas con métricas para tabla admin.

---

### 5.12 SaaS — Audit Log *(admin)*

#### `GET /audit/logs`
Consultar logs de auditoría con filtros.

**Query params:**
| Param | Tipo | Descripción |
|---|---|---|
| company_id | string | Filtrar por empresa (solo super-admin) |
| action | string | Filtrar por acción |
| resource | string | Filtrar por recurso |
| date_from | date | Desde |
| date_to | date | Hasta |
| limit | int | Máximo (default: 100) |
| offset | int | Paginación (default: 0) |

#### `GET /audit/actions`
Lista de acciones distintas (para filtros).

---

### 5.13 Endpoints Públicos

#### `GET /api/health`
Health check del sistema.

**Response:**
```json
{ "status": "ok", "service": "attendance-api", "version": "3.1.0" }
```

#### `GET /api/photos/{filename}`
Servir foto de verificación (sin auth).

---

## 6. App Móvil

### 6.1 Instalación

```bash
cd mobile-app
npm install

# Desarrollo:
npx expo start

# Build APK:
eas build --platform android --profile preview
```

### 6.2 Flujo de Pantallas

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Onboarding  │ →  │    Login     │ →  │   MarkScreen │
│              │    │              │    │              │
│ • Términos   │    │ • Email      │    │ • Cámara     │
│ • Privacidad │    │ • Password   │    │ • GPS        │
│ • Consent.   │    │ • Forgot PW  │    │ • Asistencia │
│   biométrico │    │              │    │ • Streak     │
└──────────────┘    └──────────────┘    └──────┬───────┘
                                              │
                        ┌─────────────────────┼──────────────────────┐
                        ▼                     ▼                      ▼
                 ┌───────────┐         ┌───────────┐         ┌───────────┐
                 │ MyData    │         │OfflineQueue│        │ Privacy   │
                 │           │         │           │         │ Policy    │
                 │ • Exportar│         │ • Ver     │         │           │
                 │ • Eliminar│         │ • Sync    │         │           │
                 │ • Retención│         │ • Delete  │         │           │
                 └───────────┘         └───────────┘         └───────────┘
```

### 6.3 Navegación

| Acción | Resultado |
|---|---|
| Botón "← Volver" | Navega a la pantalla anterior |
| Botón atrás Android | Navega atrás en el stack (React Navigation) |
| Pull-to-refresh | Refresca datos del día actual |

### 6.4 Modo Offline

- Sin conexión → foto + GPS se guardan en cola local
- Se muestra banner amarillo: "📶 Sin conexión"
- Badge con cantidad de pendientes
- Al reconectar → auto-sync automático
- Botón "🔄 Sync" para sincronización manual
- Pantalla "OfflineQueue" para ver/reintentar/eliminar pendientes

### 6.5 Configuración de API URL

Editar `mobile-app/app.config.js`:
```js
extra: {
  API_URL: "http://TU-SERVIDOR:8080/api"
}
```

---

## 7. Panel de Administración

### 7.1 Acceso

- URL: `http://localhost:8080/login`
- Credenciales default: `admin@miempresa.com` / `admin123`

### 7.2 Secciones

| Sección | Función |
|---|---|
| **Dashboard** | Estado en tiempo real, resumen del día |
| **Empleados** | CRUD de empleados + horarios + foto facial |
| **Registros** | Historial de asistencia con filtros + exportar Excel |
| **Bonos** | Reporte mensual de bonos + exportar CSV |
| **Geocercas** | Crear y asignar geocercas |
| **Configuración** | Nombre, logo, colores, webhooks, mensajes, verificación facial |
| **Chat IA** | Asistente virtual con datos de asistencia en tiempo real |

### 7.3 Registro de Nueva Empresa

- URL: `http://localhost:8080/register`
- Crea empresa + admin + configuración + suscripción trial
- Plan default: Free (10 empleados, 14 días de trial)

---

## 8. Panel Super-Admin (SaaS)

### 8.1 Acceso

- URL: `http://localhost:8080/saas/dashboard`
- Requiere usuario con rol `admin`

### 8.2 Secciones

| Sección | Función |
|---|---|
| **Dashboard** | MRR, ARR, churn, empresas activas, trials, top companies |
| **Empresas** | Lista completa, cambiar plan, suspender, reactivar, cancelar |
| **Planes** | CRUD de planes, toggle activo/inactivo, ver cuántas empresas usan cada uno |
| **Audit Log** | Historial global de acciones con filtros |

### 8.3 Gestión de Empresas

| Acción | Efecto |
|---|---|
| Suspender | Bloquea acceso, datos preservados 30 días |
| Reactivar | Restaura acceso inmediato |
| Cancelar | Marca para eliminación tras 30 días |
| Cambiar plan | Asigna nuevo plan con validación de límites |

---

## 9. Reconocimiento Facial

### 9.1 Proveedores

| Proveedor | Velocidad | Costo | Requisitos |
|---|---|---|---|
| **face_recognition** (local) | ~100ms | Gratis | Cámara 720p+, buena iluminación |
| **Gemini Vision** (cloud) | ~2-3s | API call | `GEMINI_API_KEY` configurada |

### 9.2 Activar

1. `.env`: `FACE_VERIFICATION_ENABLED=true`
2. Panel Admin → Configuración → toggle "Verificación facial biométrica"
3. Registrar rostro de cada empleado: Empleados → botón "👤 Registrar"

### 9.3 Flujo de Verificación

```
Empleado abre app → Centra rostro → Presiona botón
  → Selfie + GPS se envían al servidor
  → Backend compara selfie vs foto de referencia
  → Si coincide → registra asistencia
  → Si no coincide → rechaza con mensaje
```

### 9.4 Política de Retención

| Dato | Plazo |
|---|---|
| Fotos de verificación (selfies) | 90 días (auto-eliminación a las 3:00 AM) |
| Foto de referencia facial | Relación laboral + 30 días |
| Embeddings faciales | Mientras exista la foto de referencia |

---

## 10. Modo Offline

### 10.1 Cómo Funciona

```
Sin internet:
  1. App captura foto + GPS
  2. Se guarda en AsyncStorage (cola local)
  3. Muestra: "📶 Guardado sin conexión — X pendiente(s)"
  4. Cada 10s actualiza el contador

Con internet:
  1. NetInfo detecta conexión
  2. Auto-sync dispara syncQueue()
  3. Envía cada item al servidor (con foto)
  4. Backend verifica rostro + geocerca
  5. Muestra resultado: "✅ X enviado(s)"
```

### 10.2 Límites

| Límite | Valor |
|---|---|
| Edad máxima de items | 48 horas (se eliminan automáticamente) |
| Foto por item | Sí, se guarda en cache temporal |
| Sync automático | Al detectar reconexión |
| Sync manual | Botón "🔄 Sync" disponible |
| Vista de pendientes | Pantalla OfflineQueue accesible desde header |

---

## 11. Seguridad y Cumplimiento Legal

### 11.1 Ley Uruguaya 18.331 + 19.924

| Requisito | Estado |
|---|---|
| Datos biométricos = datos sensibles | ✅ Clasificados |
| Evaluación de Impacto (DPIA) | ✅ Documentada en legal-notice |
| Registro ante URCDP | ✅ Metadata disponible |
| Consentimiento informado | ✅ Checkboxes obligatorios en onboarding |
| Derechos ARCO+ | ✅ Pantalla "Mis Datos" en app |
| Retención definida | ✅ 90d fotos, 2 años logs |
| Notificación de brechas | ✅ Documentada en política |

### 11.2 Medidas de Seguridad

| Medida | Implementación |
|---|---|
| JWT con expiración | 7 días, auto-refresh |
| Rate limiting | 5 intentos/minuto en login (slowapi) |
| HTTPS | Configurable vía Nginx + certificados |
| Contraseñas | bcrypt con salt rounds |
| SQL injection | Parámetros parametrizados en todas las queries |
| CORS | Orígenes configurables via FRONTEND_URL |
| Webhook signature | Verificación de firma MP (pendiente implementación) |

### 11.3 Datos Almacenados

| Dato | Dónde | Encriptado |
|---|---|---|
| Contraseñas | DB (bcrypt hash) | ✅ |
| Fotos de verificación | Volumen Docker `/app/photos` | ❌ (solo acceso servidor) |
| Foto de referencia facial | Volumen Docker `/app/photos/face_references` | ❌ |
| JWT tokens | SecureStore (mobile), localStorage (web) | ✅ (device-level) |
| GPS coords | DB attendance_logs | ❌ |

---

## 12. Ciclo de Vida de Empresas

```
┌─────────┐     14 días     ┌─────────┐   Pago    ┌─────────┐
│   NUEVA │ ──────────────→ │  TRIAL  │ ────────→ │ ACTIVA  │
│         │                 │         │           │         │
└─────────┘                 └────┬────┘           └────┬────┘
                                 │                     │
                          No paga│                No paga
                                 ▼                     ▼
                          ┌──────────┐          ┌──────────┐
                          |  GRACIA  │ ── 3d ──→ │SUSPENDIDA│
                          │          │           │          │
                          └──────────┘           └────┬─────┘
                                                      │
                                                 30 días
                                                      ▼
                                                ┌──────────┐
                                                │CANCELADA │
                                                │          │
                                                └──────────┘
```

### Scheduler Automático (cada hora):

| Job | Horario | Función |
|---|---|---|
| Limpieza de fotos | 3:00 AM | Elimina fotos > 90 días |
| Ausencias | 10:00 AM | Detecta empleados sin check-in |
| Reporte mensual | Día 1, 00:05 | Genera y envía reporte vía webhook |
| Ciclo de vida | Cada hora | Expira trials → grace → suspend → cancel |

---

## 13. Planes y Límites

| Feature | Free | Pro ($299) | Enterprise ($999) |
|---|---|---|---|
| Empleados | 10 | 50 | Ilimitado |
| Geocercas | 2 | 10 | Ilimitado |
| Reconocimiento facial | ✅ | ✅ | ✅ |
| Webhooks | ❌ | ✅ | ✅ |
| Chat IA (Gemini) | ❌ | ✅ | ✅ |
| Exportar reportes | ✅ | ✅ | ✅ |
| Soporte prioritario | ❌ | ❌ | ✅ |
| Marca personalizada | ❌ | ❌ | ✅ |
| API personalizada | ❌ | ❌ | ✅ |
| Trial | 0 días | 14 días | 30 días |

### Validación de Límites

| Acción | Validación |
|---|---|
| Crear empleado | Verifica `max_employees` del plan (o override de empresa) |
| Crear geocerca | Verifica `max_geofences` del plan |
| Usar Chat IA | Verifica `ai_chat` del plan (402 si no incluido) |
| Usar Webhooks | Verifica `webhooks` del plan |
| Cambiar a plan menor | Valida que empleados actuales no excedan nuevo límite |

---

## 14. Troubleshooting

### La app no levanta

```bash
# Ver logs
docker compose logs -f backend
docker compose logs -f postgres
docker compose logs -f frontend

# Reiniciar un servicio
docker compose restart backend

# Ver puertos
docker compose ps
```

### Error de permisos Docker

```bash
# Agregar usuario al grupo docker
sudo usermod -aG docker $USER
newgrp docker
```

### Error "'ContainerConfig'"

```bash
# Usar docker compose v2 (sin guión)
docker compose up -d --build

# Si no está instalado:
sudo apt install docker-compose-plugin
```

### Base de datos no se inicializa

```bash
# El init.sql solo corre la PRIMERA vez que se crea el volumen
# Para resetear:
docker compose down -v
docker compose up -d --build
```

### Error de conexión a PostgreSQL

```bash
# Verificar que el contenedor de DB esté corriendo
docker compose ps postgres

# Ver logs de DB
docker compose logs postgres
```

### Fotos no se guardan

```bash
# Verificar volumen
docker volume ls | grep photos_data

# Ver contenido
docker run --rm -v attendance-system_photos_data:/data alpine ls /data
```

### Token JWT expirado

- Duración: 7 días
- Solución: Logout → Login nuevamente
- El token se renueva automáticamente al hacer login

### Webhook no funciona

```bash
# Probar webhook desde el panel admin
# Configuración → URL del Webhook → botón "🔔 Probar"

# Ver logs del backend
docker compose logs -f backend | grep Webhook
```

### Error de reconocimiento facial

```bash
# Verificar que face_recognition está instalado
docker compose exec backend pip list | grep face

# Si no está, rebuild:
docker compose up -d --build backend
```

---

## 15. Backup y Restauración

### Backup de Base de Datos

```bash
# Backup completo
docker exec attendance_db pg_dump -U attendance_user attendance_db > backup_$(date +%Y%m%d).sql

# Backup comprimido
docker exec attendance_db pg_dump -U attendance_user attendance_db | gzip > backup_$(date +%Y%m%d).sql.gz
```

### Restaurar Base de Datos

```bash
# 1. Bajar servicios
docker compose down

# 2. Restaurar
cat backup_20250405.sql | docker exec -i attendance_db psql -U attendance_user attendance_db

# 3. Levantar
docker compose up -d
```

### Backup de Fotos

```bash
# Copiar volumen de fotos
docker run --rm -v attendance-system_photos_data:/data -v $(pwd):/backup alpine tar czf /backup/photos_backup.tar.gz -C /data .
```

### Restaurar Fotos

```bash
docker run --rm -v attendance-system_photos_data:/data -v $(pwd):/backup alpine tar xzf /backup/photos_backup.tar.gz -C /data
```

### Backup Completo Automatizado

```bash
#!/bin/bash
# backup.sh
BACKUP_DIR="/ruta/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# DB
docker exec attendance_db pg_dump -U attendance_user attendance_db | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# Photos
docker run --rm -v attendance-system_photos_data:/data -v $BACKUP_DIR:/backup alpine tar czf "/backup/photos_$DATE.tar.gz" -C /data .

# Mantener solo últimos 7 backups
ls -t $BACKUP_DIR/db_*.sql.gz | tail -n +8 | xargs rm -f
ls -t $BACKUP_DIR/photos_*.tar.gz | tail -n +8 | xargs rm -f

echo "Backup completado: $DATE"
```

Agregar a crontab (`crontab -e`):
```
0 2 * * * /ruta/backup.sh
```

---

## Anexos

### A. Endpoints por Rol

| Rol | Endpoints Accesibles |
|---|---|
| **Empleado** | `/attendance/mark`, `/attendance/today`, `/company/config`, `/data-rights/*`, `/privacy/*` |
| **Admin empresa** | Todo lo de Empleado + `/employees/*`, `/dashboard/*`, `/company/config (PATCH)`, `/chat/`, `/subscriptions/my`, `/subscriptions/change-plan` |
| **Super-Admin** | Todo lo anterior + `/plans/*`, `/companies/*`, `/saas-metrics/*`, `/audit/*` |

### B. Códigos de Error

| HTTP | Significado | Cuándo aparece |
|---|---|---|
| 200 | Éxito | Operación completada |
| 400 | Bad Request | Datos inválidos, límite alcanzado |
| 401 | No autorizado | Token expirado, credenciales incorrectas |
| 402 | Payment Required | Feature no incluida en el plan |
| 403 | Forbidden | Rol insuficiente (requiere admin) |
| 404 | Not Found | Recurso no existe |
| 500 | Server Error | Error interno del servidor |

### C. Límites del Sistema

| Límite | Valor |
|---|---|
| Timeout de requests | 30 segundos |
| Máx empleados por empresa | Definido por plan (default 10) |
| Antigüedad de cola offline | 48 horas |
| Retención de fotos | 90 días |
| Retención de logs | 2 años |
| JWT expiración | 7 días |
| Rate limiting login | 5 intentos/minuto |
