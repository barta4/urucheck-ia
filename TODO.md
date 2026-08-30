# 📝 TODO — Estado Actual y Tareas del Sistema

> **Última actualización:** Agosto 2026

---

## ✅ Resuelto Recientemente

1. **Aislamiento Multi-Tenant de Colores, Logos y Marca:**
   * Resuelto en Backend (`routers/company.py`, `main.py`) con UPSERT garantizado, índices únicos y auto-recuperación de configuraciones huérfanas.
   * Resuelto en Frontend Admin (`CompanyContext.jsx`, `CompanySettings.jsx`) reactivo a `useAuth` y sincronizado sin necesidad de refresco manual.
   * Resuelto en App Móvil (`useCompany.js`, `AuthContext.jsx`) eliminando la caché estática global y habilitando soporte offline en `AsyncStorage`.
2. **Modernización UI/UX del Frontend Admin:**
   * Reemplazados todos los `alert()` y `confirm()` por sistema global de **Toasts Reactivos** (`ToastContext.jsx`) y componente modal accesible `<ConfirmModal />`.
   * **Editor Visual de Geocercas en Leaflet** (`Geofences.jsx`): Clic en mapa, marcador arrastrable, slider de radio en tiempo real y buscador de direcciones Nominatim.
   * **Carga Masiva de Empleados** (`Employees.jsx` & `POST /api/employees/bulk`): Carga por CSV con validación previa de columnas, reporte de errores y descarga de plantilla.
3. **Reportes Oficiales y Exportación:**
   * Generación de reportes de asistencia en **PDF Oficial con Código QR** (`backend/pdf_service.py` con ReportLab + `GET /api/dashboard/bonus-report/pdf` en `Bonuses.jsx`).
4. **SaaS & Retención:**
   * Barra de cuenta regresiva de período de prueba (**TrialBanner**) y modal de Upgrade de plan interactivo integrado en `Layout.jsx`.
5. **Suite de Pruebas Automatizadas y Seguridad:**
   * Suite en `backend/tests/` con 10/10 tests pasando (`test_pdf_service.py`, `test_rules_engine.py`, `test_security_auth.py`).

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
