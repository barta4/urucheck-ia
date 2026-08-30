# 📝 TODO — Estado Actual y Tareas del Sistema

> **Última actualización:** Agosto 2026

---

## ✅ Resuelto Recientemente (v2.2.0)

1. **Panel SaaS Master y Gestión Financiera en USD:**
   * **Eliminación y Baja de Empresas** (`backend/routers/companies.py` & `SaasCompanies.jsx`): Endpoint `DELETE /api/companies/{id}` con soft-delete en cascada y modal de confirmación con doble validación de seguridad.
   * **Gestión de Cobros y Facturación SaaS** (`backend/routers/metrics.py` & `SaasBilling.jsx`): Resumen financiero en USD (MRR, Total Recaudado), estado por empresa (Al día, En Trial, Vencido), registro de pagos manuales con extensión de suscripciones (+30/+60/+90/+365 días), generador de links de checkout de MercadoPago e historial global con exportación CSV.
   * **Integración MercadoPago / MercadoLibre** (`backend/mp_oauth.py` & `SaasMercadoPago.jsx`): Configuración de credenciales de producción/OAuth en base de datos sin reiniciar backend y test en tiempo real con la API de MercadoPago (`/users/me`).
   * **Estandarización Internacional a USD**: Todas las tarifas, cobros, facturas y checkout configurados en Dólares (USD).
2. **Control Estricto de Horarios, Multi-Turnos y Descansos:**
   * **Multi-Turnos por Empleado**: Horarios por franja (`slot_name`) con geocercas diferenciadas por horario del día.
   * **Modos de Descanso**: Configuración de descanso fijo (`fixed`) con hora de inicio/fin o flexible (`flexible`) con duración máxima permitida.
   * **Alertas de Salida Temprana**: Detección y advertencia al empleado en la App móvil y registro de minutos anticipados en backend ante salidas no autorizadas.
3. **Publicación y Despliegue v2.2:**
   * Imágenes publicadas en Docker Hub: `alfredobartaburu/urucheck-backend:v2.2` y `alfredobartaburu/urucheck-frontend:v2.2`.
   * Código fuente completo sincronizado en GitHub: `https://github.com/barta4/urucheck-ia`.

---

## 📋 Tareas Pendientes y Roadmap de Mejoras

Para la descripción detallada de cada funcionalidad, consulta el archivo [ROADMAP_MEJORAS.md](file:///c:/Users/usuario/Desktop/Assitencia/ROADMAP_MEJORAS.md).

### 1. Frontend Web Admin (UI/UX)
- [x] Reemplazar `alert()` y `confirm()` nativos por Toasts reactivos.
- [x] Editor visual interactivo de geocercas sobre el mapa de Leaflet.
- [x] Importador / Exportador masivo de empleados en CSV.
- [ ] Implementar WebSocket / SSE para actualización del Dashboard en tiempo real.

### 2. App Móvil (Expo / React Native)
- [ ] Detección de vida facial (Anti-spoofing / Liveness challenge).
- [ ] Autenticación biométrica nativa del dispositivo (`expo-local-authentication` para Huella / Face ID).
- [ ] Sincronización en segundo plano (`expo-task-manager` / `BackgroundFetch`).

### 3. Backend & Lógica
- [x] Generación de planillas y reportes mensuales en **PDF oficial con código QR**.
- [ ] Migraciones versionadas de base de datos con **Alembic**.
- [ ] Integración con WhatsApp Cloud API para alertas instantáneas.

### 4. Despliegue en Dokploy (Traefik)
- [x] Configurar labels de Traefik en `docker-compose.yml` para enrutamiento directo de `backend:8000` y `frontend:80`.
- [ ] Script de copias de seguridad automáticas diarias de PostgreSQL con rotación a 30 días.

### 5. SaaS & Monetización
- [x] Barra de cuenta regresiva de días de prueba (Trial) y modal de Upgrade a planes Pro/Enterprise.
- [ ] Soporte Multi-Idioma (i18n: Español, Inglés, Portugués).
