# Sistema de Control de Asistencia Gamificado (SaaS Multi-Empresa)

> **v2.0.0** — Sistema multi-tenant. Cada empresa tiene sus propios datos aislados.

## Estructura del proyecto

```
attendance-system/
├── backend/          # FastAPI - API REST
├── frontend-admin/   # React + Tailwind - Panel Admin
├── mobile-app/       # Expo React Native - App Empleados
├── nginx/            # Reverse proxy
├── db/               # SQL inicial
└── docker-compose.yml
```

---

## 🏢 Multi-Empresa (SaaS)

El sistema soporta **múltiples empresas** con datos completamente aislados:

### Cómo funciona:

| Concepto | Detalle |
|---|---|
| **Registro** | `POST /api/companies/register` — Self-service, crea empresa + admin + config |
| **Aislamiento** | Cada tabla tiene `company_id` — queries filtran automáticamente |
| **JWT** | Token incluye `company_id` y `company_slug` — resuelto en cada request |
| **Landing** | `/register` en el panel admin para crear nueva empresa |
| **Plan gratuito** | Hasta 10 empleados por empresa |

### Registrar nueva empresa:

```bash
curl -X POST http://localhost/api/companies/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp",
    "slug": "acme-corp",
    "admin_email": "admin@acme.com",
    "admin_password": "secure123",
    "plan": "free",
    "max_employees": 10
  }'
```

### Login:

El login detecta automáticamente la empresa del usuario por email:

```bash
curl -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@acme.com", "password": "secure123"}'
```

Respuesta incluye `company_id`, `company_name`, `company_slug`.

---

## Deploy en VPS

### 1. Clonar y configurar variables
```bash
cp .env.example .env
nano .env  # Editar DB_PASSWORD, SECRET_KEY, FRONTEND_URL, VITE_API_URL
```

### 2. Levantar los servicios
```bash
docker-compose up -d --build
```

### 3. Verificar
```bash
docker-compose ps
curl http://localhost/api/health
```

### Credenciales por defecto (empresa demo)
- **Email:** admin@miempresa.com
- **Password:** admin123
- ⚠️ Cambiar inmediatamente via panel de empleados

---

## 🔐 Verificación Facial Biométrica

El sistema soporta verificación facial al momento de marcar asistencia, con dos proveedores:

| Proveedor | Velocidad | Costo | Requisitos |
|-----------|-----------|-------|------------|
| **face_recognition** (local) | ~100ms | Gratis | Cámara 720p+, buena iluminación |
| **Gemini Vision** (cloud) | ~2-3s | API call | `GEMINI_API_KEY` configurada |

### Activar verificación facial:

1. **Variables de entorno** (en `.env`):
   ```
   FACE_VERIFICATION_ENABLED=true
   FACE_VERIFICATION_PROVIDER=face_recognition  # o gemini_vision
   FACE_VERIFICATION_THRESHOLD=0.6
   ```

2. **Panel Admin → Configuración de Empresa**: Activa el toggle "Verificación facial biométrica" y selecciona el proveedor.

3. **Registrar rostro de cada empleado**: Panel Admin → Empleados → botón "👤 Registrar" → Sube una foto frontal clara.

4. **Reconstruir el backend** (si face_recognition no estaba instalado):
   ```bash
   docker-compose up -d --build backend
   ```

> ⚠️ **Importante**: Sin una foto de referencia registrada, el empleado no podrá marcar asistencia si la verificación facial está activa.

---

## App Móvil (Expo)

### Desarrollo local
```bash
cd mobile-app
npm install
# Editar app.config.js → extra.API_URL con IP del VPS
npx expo start
```

### Build para producción (APK Android)
```bash
npm install -g eas-cli
eas login
eas build --platform android --profile preview
```

---

## Endpoints principales

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | /api/auth/login | Login |
| POST | /api/attendance/mark | Marcar asistencia (multipart) |
| GET | /api/attendance/today | Estado del día (empleado) |
| GET | /api/dashboard/today | Dashboard tiempo real (admin) |
| GET | /api/dashboard/logs | Registros con filtros (admin) |
| GET | /api/dashboard/bonus-report?month=2024-01 | Reporte bonos |
| GET | /api/dashboard/bonus-report/export?month=2024-01 | Exportar CSV |
| GET/POST | /api/employees/ | CRUD empleados |
| POST | /api/employees/{id}/schedules | Asignar horario |
| POST | /api/dashboard/geofences | Crear geocerca |

---

## Configuración de bonos

En `backend/config.py`:
```python
BONUS_STREAK_DAYS: int = 20  # días requeridos para el bono
```

---

## 📚 Documentación adicional

- [MANUAL.md](MANUAL.md) — Manual técnico exhaustivo (arquitectura, APIs, variables y procedimientos).
- [ROADMAP_MEJORAS.md](ROADMAP_MEJORAS.md) — Roadmap de mejoras planificadas (WebSockets, Toasts, Liveness detection, PDFs, Dokploy con Traefik).
- [TODO.md](TODO.md) — Lista de tareas y estado actual del proyecto.

