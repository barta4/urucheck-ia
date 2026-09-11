# 📝 TODO — Estado Actual y Tareas del Sistema

> **Última actualización:** Septiembre 2026 — **Versión 2.11.0**

---

## ✅ Resuelto Recientemente (v2.11.0)

1. **Optimización y Endurecimiento de Google Gemini Vision (`backend/face_service.py`):**
   * Migración a llamadas asíncronas no bloqueantes con `model.generate_content_async` y timeout de 8 segundos (`asyncio.wait_for`), evitando congelamiento del event loop en FastAPI/Uvicorn.
   * Normalización universal con Pillow (`PIL.Image` y `ImageOps.exif_transpose`) soportando JPG, PNG, WebP y rotación automática de selfies de smartphones.
   * Modo estructurado JSON nativo (`response_mime_type: "application/json"`) y parser con regex defensivo.
   * Mensajes de error claros ante baja confianza (indicando porcentaje) y validación de rostros en fotos de legajo.
   * 8 nuevas pruebas unitarias automatizadas añadidas, alcanzando 60 tests con 100% de éxito.

2. **Corrección del Ciclo Dinámico de Marcación (`GET /api/attendance/today`):**
   * Eliminado el error `UnboundLocalError` en `backend/routers/attendance.py` ocasionado por una importación interna de `settings`.
   * Ahora la app móvil recibe el estado del día con código HTTP 200 y el botón cambia dinámicamente según la etapa de la jornada:
     * 🟢 **Registrar Entrada** ➔ ☕ **Iniciar Descanso** ➔ 💼 **Volver al Trabajo** ➔ 🔴 **Registrar Salida** ➔ ✅ **Jornada Completa**.

3. **Permisos de Volúmenes en Docker y Guardado de Fotos (`v2.9` / `v2.10`):**
   * Ajustado `backend/Dockerfile` otorgando permisos `chmod -R 777 /app/photos` y liberando la ejecución de usuario para convivir de forma nativa con los volúmenes de Docker en VPS (`photos_data:/app/photos`).
   * Capa defensiva en `attendance.py` y `leaves.py` con respaldo automático a `/tmp/photos` y `/tmp/photos/certificates` en caso de cualquier bloqueo de sistema de archivos.

4. **Auditoría Técnica y Refactorización Integral:**
   * **Servicio de Pagos Centralizado (`backend/payment_service.py`):** Unificación de checkout preferences de MercadoPago, verificación criptográfica HMAC SHA-256 de webhooks y procesamiento atómico de notificaciones. Eliminadas más de 190 líneas de código duplicado.
   * **Seguridad en Consultas SQL (`backend/db_utils.py`):** Helper `build_dynamic_update_query` con lista blanca de columnas para evitar inyecciones SQL en actualizaciones dinámicas.
   * **Frontend Admin Limpio (`frontend-admin`):** Módulo `fileDownloader.js` para descargas Blob con liberación de memoria y exportador CSV UTF-8 con BOM compatible con Microsoft Excel en todas las páginas.
   * **Constantes Compartidas de Asistencia:** Módulos centralizados `constants/attendance.js` en Frontend Admin y Mobile App.
   * **Corrección de Deprecaciones:** Migración de `datetime.utcnow()` a `datetime.now(timezone.utc)` y modelos a Pydantic v2 `ConfigDict`.
   * **Corrección de UI Móvil:** Resuelto error de estilos no definidos en `LeavesScreen.jsx`.

5. **Suite de Pruebas Automatizadas:**
   * 60 tests automatizados pasando al 100% en `pytest backend/tests/`.

6. **Despliegue Multi-Plataforma en Docker Hub:**
   * Imágenes publicadas para `linux/amd64`:
     * 🏷️ `docker.io/alfredobartaburu/urucheck-backend:v2.11` (y `latest`)
     * 🏷️ `docker.io/alfredobartaburu/urucheck-frontend:v2.8` (y `latest`)
   * `docker-compose.yml` sincronizado para despliegue directo en Dokploy con Traefik.

---

## 📋 Tareas Pendientes y Roadmap de Mejoras

Para la descripción detallada de cada funcionalidad, consulta el archivo [ROADMAP_MEJORAS.md](file:///c:/Users/usuario/Desktop/Assitencia/ROADMAP_MEJORAS.md).

### 1. Frontend Web Admin (UI/UX)
- [x] Reemplazar `alert()` y `confirm()` nativos por Toasts reactivos.
- [x] Editor visual interactivo de geocercas sobre el mapa de Leaflet.
- [x] Importador / Exportador masivo de empleados en CSV (UTF-8 con BOM).
- [ ] Implementar WebSocket / SSE para actualización del Dashboard en tiempo real.

### 2. App Móvil (Expo / React Native)
- [x] Ciclo dinámico inteligente de botones (Entrada ➔ Descanso ➔ Retorno ➔ Salida).
- [x] Manejo de colas offline con sincronización automática al recuperar red.
- [ ] Detección de vida facial (Anti-spoofing / Liveness challenge).
- [ ] Autenticación biométrica nativa del dispositivo (`expo-local-authentication` para Huella / Face ID).
- [ ] Sincronización en segundo plano (`expo-task-manager` / `BackgroundFetch`).

### 3. Backend & Lógica
- [x] Generación de planillas y reportes mensuales en **PDF oficial con código QR**.
- [x] Capa defensiva de almacenamiento de archivos y certificados médicos.
- [x] Suite de pruebas automatizadas con pytest (52 tests).
- [ ] Migraciones versionadas de base de datos con **Alembic**.
- [ ] Integración con WhatsApp Cloud API para alertas instantáneas.

### 4. Despliegue en Dokploy (Traefik)
- [x] Configurar labels de Traefik en `docker-compose.yml` para enrutamiento directo de `backend:8000` y `frontend:80`.
- [x] Imágenes Docker optimizadas para `linux/amd64` con versionado incremental para evitar colisiones de caché.
- [ ] Script de copias de seguridad automáticas diarias de PostgreSQL con rotación a 30 días.

### 5. SaaS & Monetización
- [x] Barra de cuenta regresiva de días de prueba (Trial) y modal de Upgrade a planes Pro/Enterprise.
- [x] Gestión de cobros en USD con pasarela MercadoPago y registro manual de pagos.
- [ ] Soporte Multi-Idioma (i18n: Español, Inglés, Portugués).
