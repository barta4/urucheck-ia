# 🗺️ Roadmap de Mejoras y Evolución Técnica

> Este documento detalla las mejoras arquitectónicas, de experiencia de usuario (UI/UX), seguridad y modelo SaaS planificadas para el sistema, adaptadas para despliegue en **Dokploy (con Traefik)**.

---

## 📋 Índice
1. [Frontend Web & Experiencia de Usuario (UI/UX)](#1-frontend-web--experiencia-de-usuario-uiux)
2. [App Móvil (React Native & Expo)](#2-app-móvil-react-native--expo)
3. [Backend & Arquitectura de Datos](#3-backend--arquitectura-de-datos)
4. [Infraestructura y Despliegue en Dokploy (Traefik)](#4-infraestructura-y-despliegue-en-dokploy-traefik)
5. [Modelo SaaS & Crecimiento](#5-modelo-saas--crecimiento)
6. [Seguridad y Hardening Multi-Tenant (Security Audit)](#6-seguridad-y-hardening-multi-tenant-security-audit)

---

## 1. Frontend Web & Experiencia de Usuario (UI/UX)

### 1.1. Sistema de Notificaciones Toast y Modales Reactivos
* **Situación actual:** Varias pantallas usan `alert()` y `confirm()` nativos del navegador, lo que congela la ejecución y no permite personalización visual.
* **Mejora planificada:**
  * Integrar `sonner` o `react-hot-toast` para notificaciones no intrusivas con soporte de temas y colores del tenant.
  * Crear modales de confirmación con diseño accesible para eliminación de empleados, geocercas y licencias.

### 1.2. Dashboard en Tiempo Real con WebSockets o Server-Sent Events (SSE)
* **Situación actual:** El dashboard consulta periódicamente cada 30 segundos (`setInterval(fetchData, 30000)`).
* **Mejora planificada:**
  * Crear un canal SSE o WebSocket en FastAPI (`/api/ws/dashboard` o `/api/dashboard/events`).
  * Emitir eventos cada vez que un empleado registra entrada, descanso o salida.
  * El mapa y las métricas del panel web se actualizarán instantáneamente en milisegundos sin recargar.

### 1.3. Editor Visual e Interactivo de Geocercas en Mapa
* **Situación actual:** La creación de geocercas requiere ingresar latitud, longitud y radio en campos de texto numéricos.
* **Mejora planificada:**
  * Integrar controles de dibujo en Leaflet (`leaflet-draw` o marcadores interactivos).
  * Permitir hacer clic en el mapa, arrastrar el marcador central y redimensionar el círculo con un control deslizante visual.
  * Búsqueda de direcciones mediante autocompletado de OpenStreetMap / Nominatim.

### 1.4. Importación y Exportación Masiva en Excel/CSV
* **Situación actual:** El alta de empleados y horarios se realiza uno a uno.
* **Mejora planificada:**
  * Plantilla descargable en Excel (`.xlsx`) y CSV.
  * Validador previo de columnas (nombre, email, horario, tolerancia, rol) con reporte de errores fila por fila antes de guardar.
  * Procesamiento en lote para crear decenas de empleados en un solo clic.

---

## 2. App Móvil (React Native & Expo)

### 2.1. Detección de Vida Facial (Anti-Spoofing / Liveness Detection)
* **Situación actual:** La verificación facial coteja la selfie tomada con la foto de referencia registrada.
* **Mejora planificada:**
  * Implementar un reto aleatorio de detección de vida antes de la captura (ej. solicitar pestañear, sonreír o girar ligeramente la cabeza).
  * Detección de reflejos y textura para mitigar el uso de fotografías impresas o pantallas secundarias.

### 2.2. Autenticación Biométrica Nativa del Dispositivo
* **Situación actual:** El empleado inicia sesión con email y contraseña, persistiendo el token en `SecureStore`.
* **Mejora planificada:**
  * Integrar `expo-local-authentication`.
  * Permitir desbloquear la app mediante Face ID, Touch ID o huella dactilar nativa del sistema operativo, agilizando el marcado diario.

### 2.3. Sincronización en Segundo Plano para Modo Offline
* **Situación actual:** Las marcas encoladas sin internet se sincronizan cuando el usuario abre la app y se detecta conexión.
* **Mejora planificada:**
  * Configurar `expo-background-fetch` y `expo-task-manager`.
  * Despachar automáticamente las marcas pendientes en segundo plano apenas el sistema operativo detecte restablecimiento de red WiFi/datos móviles, sin requerir intervención manual del usuario.

---

## 3. Backend & Arquitectura de Datos

### 3.1. Migraciones de Base de Datos Versionadas con Alembic
* **Situación actual:** El esquema y las columnas se gestionan mediante scripts SQL en el `lifespan` de FastAPI.
* **Mejora planificada:**
  * Inicializar **Alembic** (`alembic init alembic`) conectado a los modelos SQLAlchemy.
  * Crear historial de revisiones (`alembic revision --autogenerate`) para despliegues reproducibles y rollbacks seguros.

### 3.2. Generación de Planillas y Reportes Mensuales en PDF Oficial
* **Situación actual:** Los reportes de asistencia se exportan en formato CSV.
* **Mejora planificada:**
  * Integrar generación de documentos PDF (`reportlab` o `weasyprint`).
  * Formato oficial con logo de la empresa, tabla de horas trabajadas, llegadas tarde, ausencias justificadas y código QR de validación digital para entrega a recursos humanos o contabilidad.

### 3.3. Integración con WhatsApp para Alertas Inmediatas
* **Situación actual:** Las notificaciones a la empresa se envían por Webhook HTTP y correo SMTP.
* **Mejora planificada:**
  * Conectar con WhatsApp Cloud API o Twilio para despachar mensajes instantáneos a supervisores cuando un empleado no registre asistencia transcurrida la tolerancia.

---

## 4. Infraestructura y Despliegue en Dokploy (Traefik)

> **Nota de Arquitectura:** En Dokploy, **Traefik** actúa como el Ingress/Reverse Proxy principal del servidor. Traefik se encarga automáticamente de la obtención y renovación de certificados SSL (Let's Encrypt), terminación TLS y enrutamiento por subdominio o path.

### 4.1. Simplificación de la Pila en Dokploy
Al desplegar en Dokploy, la arquitectura puede simplificarse eliminando Nginx como proxy reverso global:

```
                      ┌──────────────────────────────────────────────┐
                      │              Traefik (Dokploy)               │ ← SSL Automático / HTTPS
                      └──────────────┬────────────────┬──────────────┘
                                     │                │
                        /api/*       │                │ /*
                 ┌───────────────────▼──┐          ┌──▼────────────────────┐
                 │   attendance_api     │          │   attendance_admin    │
                 │   FastAPI (:8000)    │          │   (Nginx SPA estático)│
                 └──────────┬───────────┘          └───────────────────────┘
                            │
                 ┌──────────▼───────────┐
                 │    attendance_db     │
                 │     (Postgres)       │
                 └──────────────────────┘
```

* **Traefik:** Rutea el dominio principal y subdominios, aplica compresión Gzip/Brotli, gestiona certificados SSL y redirige HTTP a HTTPS automáticamente.
* **Frontend Admin:** Se sirve como aplicación estática SPA (usando una imagen ligera de Nginx o un servidor web estático interno).
* **Backend:** Expone el puerto `8000` directamente a la red interna de Traefik.

### 4.2. Configuración de Etiquetas Traefik en `docker-compose.yml` para Dokploy
Ejemplo de configuración con labels para integración con Traefik:

```yaml
services:
  backend:
    build: ./backend
    restart: always
    environment:
      - DATABASE_URL=postgresql://attendance_user:${DB_PASSWORD}@db:5432/attendance_db
      - FRONTEND_URL=https://asistencia.tudominio.com
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.backend.rule=Host(`asistencia.tudominio.com`) && PathPrefix(`/api`)"
      - "traefik.http.routers.backend.entrypoints=websecure"
      - "traefik.http.routers.backend.tls.certresolver=letsencrypt"
      - "traefik.http.services.backend.loadbalancer.server.port=8000"

  frontend:
    build: ./frontend-admin
    restart: always
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=Host(`asistencia.tudominio.com`)"
      - "traefik.http.routers.frontend.entrypoints=websecure"
      - "traefik.http.routers.frontend.tls.certresolver=letsencrypt"
      - "traefik.http.services.frontend.loadbalancer.server.port=80"
```

### 4.3. Copias de Seguridad Automáticas de PostgreSQL
* Configurar un contenedor auxiliar o cron job en el servidor que ejecute diariamente:
  ```bash
  docker exec attendance_db pg_dump -U attendance_user attendance_db | gzip > /backups/backup_$(date +%Y%m%d_%H%M%S).sql.gz
  find /backups -type f -name "*.sql.gz" -mtime +30 -delete
  ```
* Sincronización opcional hacia almacenamiento en la nube (AWS S3, Google Cloud Storage o Cloudflare R2).

---

## 5. Modelo SaaS & Crecimiento

### 5.1. Contador de Período de Prueba (Trial) y Modal de Upgrade
* **Situación actual:** La fecha de finalización de prueba está guardada en la base de datos (`companies.trial_ends_at`).
* **Mejora planificada:**
  * Mostrar una barra superior en el panel admin cuando falten menos de 7 días para finalizar el período de prueba.
  * Modal interactivo que permita al administrador seleccionar un plan (Pro / Enterprise) y pagar con Mercado Pago en checkout integrado.

### 5.2. Soporte Multi-Idioma (i18n)
* **Mejora planificada:**
  * Configurar `i18next` en el frontend y `react-i18next` en la app móvil.
  * Diccionarios de traducción en Español (predeterminado), Inglés y Portugués para facilitar la expansión a toda Latinoamérica.

---

## 6. Seguridad y Hardening Multi-Tenant (Security Audit)

> **Resultado del Security Audit (8 pilares)**: Implementación de defensas en profundidad, blindaje de pagos y aislamiento multi-tenant.

### 6.1. Validación Criptográfica de Webhooks de Mercado Pago (HMAC-SHA256)
* **Estado:** ✅ **Implementado**
* **Detalle:** Validación estricta de las cabeceras `x-signature` y `x-request-id` con el secreto `mp_webhook_secret` y ventana de tolerancia temporal (`ts` <= 600s) para mitigar ataques de repetición (replay attacks) y falsificación de pagos.

### 6.2. Cifrado Simétrico en Reposo para Credenciales (Fernet)
* **Estado:** ✅ **Implementado**
* **Detalle:** Las contraseñas de servidores SMTP y secretos de terceros en `company_config` se cifran usando Fernet derivado de `ENCRYPTION_KEY` / `SECRET_KEY`, evitando que accesos o volcados de base de datos expongan credenciales en texto plano. En las respuestas de la API, las contraseñas se enmascaran (`********`).

### 6.3. Identificador Único de Tokens JWT (`jti`) y Revocación de Sesiones
* **Estado:** ✅ **Implementado**
* **Detalle:** Emisión de `jti` en cada token de acceso y persistencia en tabla `revoked_tokens` al invocar `POST /api/auth/logout`, permitiendo la invalidación explícita de credenciales comprometidas.

### 6.4. Contenedor Backend Non-Root (`appuser`)
* **Estado:** ✅ **Implementado**
* **Detalle:** Dockerfile configurado con usuario y grupo del sistema sin privilegios (`appuser:appuser`, UID 1001), eliminando riesgos de escalación de privilegios al host si ocurre una vulnerabilidad de aplicación.

### 6.5. Límites DoS en Subida de Archivos y Fotos
* **Estado:** ✅ **Implementado**
* **Detalle:** Validación de tamaño máximo de 10 MB antes de persistir fotos de asistencia, certificados médicos y fotos de enrolamiento facial, respondiendo con `HTTP 413 Payload Too Large` ante archivos excesivos.

### 6.6. Políticas de Complejidad de Contraseñas y Erradicación de Defaults
* **Estado:** ✅ **Implementado**
* **Detalle:** Reglas obligatorias de al menos 8 caracteres, números y mayúsculas en registro de empresa y empleados. Erradicación de contraseñas por defecto (`123456`) en la creación masiva, reemplazadas por claves aleatorias seguras autogeneradas.

### 6.7. Health Probes y Observabilidad
* **Estado:** ✅ **Implementado**
* **Detalle:** Endpoint `/api/health` instrumentado con verificación activa de conectividad a PostgreSQL para que Traefik y Dokploy reconozcan el estado real del clúster antes de enrutar tráfico.

