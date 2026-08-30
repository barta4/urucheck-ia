# 🔑 Documentación del Usuario Superadmin (UruCheck IA)

Este documento detalla cómo funciona el usuario **Superadmin (Master)** de la plataforma, cómo se definen sus credenciales, cómo acceder al panel SaaS y cómo promover cualquier cuenta a Superadmin.

---

## 1. 👤 Credenciales por Defecto y Variables de Entorno

El usuario Superadmin se configura mediante variables de entorno en tu archivo `.env` o en el panel de **Dokploy**:

| Configuración | Variable de Entorno | Valor Predeterminado | Descripción |
|---|---|---|---|
| **Email Superadmin** | `SUPER_ADMIN_EMAIL` | `admin@miempresa.com` | Email del usuario con permisos globales |
| **Contraseña Inicial** | `SEED_ADMIN_PASSWORD` | *(Definida en tu .env)* | Contraseña con la que se crea la cuenta en el primer arranque |
| **Slug de Empresa** | *N/A* | `mi-empresa` | Empresa inicial creada en el sembrado de base de datos |

> **Nota de Seguridad**:
> En cada inicio del backend, el sistema ejecuta automáticamente:
> ```sql
> UPDATE employees SET is_super_admin = true WHERE email = :SUPER_ADMIN_EMAIL;
> ```
> Por lo tanto, **cualquier usuario cuyo email coincida con la variable `SUPER_ADMIN_EMAIL` obtiene automáticamente todos los privilegios de Superadmin**.

---

## 2. 🚀 Cómo Iniciar Sesión como Superadmin

1. Abre el panel web en tu navegador: `http://localhost:5173` (desarrollo) o tu dominio en producción (ej. `https://asistencia.urufile.com`).
2. En la pantalla de Login:
   * **Email**: `admin@miempresa.com` (o el valor que tengas configurado en `SUPER_ADMIN_EMAIL`).
   * **Contraseña**: La contraseña asignada en `SEED_ADMIN_PASSWORD` (o la que hayas establecido).
   * **Slug de empresa** *(opcional, si el email existe en varias empresas)*: `mi-empresa`.
3. Al iniciar sesión:
   * Verás el panel de administración normal de tu empresa.
   * En la barra lateral izquierda (abajo), aparecerá el botón destacado:
     👉 **`🔑 Panel SaaS Master`** (`/saas` o `/saas-dashboard`).

---

## 3. 🛡️ Capacidades y Privilegios Exclusivos del Superadmin

Cuando un usuario tiene `is_super_admin = true`, desbloquea:

1. **Dashboard SaaS Master (`/saas-dashboard`)**:
   * Métricas de negocio en tiempo real: **MRR** (Ingresos Mensuales Recurrentes), **ARR**, Churn Rate e ingresos totales.
   * Conteo de empresas activas, en período de prueba (trial), suspendidas y canceladas.
   * Contador de empresas cuyos trials vencen en los próximos 3 días.
   * Configuración de URLs de descarga globales para la App móvil (APK Android y App Store).

4. **Gestión de Cobros y Facturación SaaS (`/saas/billing`)**:
   * **KPIs Financieros Globales en USD**: Total recaudado histórico, MRR activo, empresas al día y monto pendiente por cobrar.
   * **Estado de Cobro por Empresa**: Monitoreo de empresas al día, en período de prueba (trial), vencidas o suspendidas con días de atraso.
   * **Registro de Pagos Manuales**: Permite acreditar pagos recibidos fuera de pasarela (transferencias bancarias, efectivo, cheques), emitiendo factura y extendiendo la suscripción (+15, +30, +60, +90, +365 días) de forma inmediata.
   * **Generador de Links de Pago MP**: Creación de enlaces de checkout directos en USD con copia al portapapeles para enviar por WhatsApp o Email.
   * **Historial Global y Exportación**: Registro paginado de todas las transacciones con exportación a archivo **Excel (CSV)**.

5. **Integración con MercadoPago / MercadoLibre (`/saas/mercadopago`)**:
   * Panel de control con indicador de estado en vivo (🟢 Conectado / 🔴 No configurado).
   * Verificación en tiempo real contra la API de MercadoPago (`https://api.mercadopago.com/users/me`) mostrando titular, email, sitio y moneda USD.
   * Configuración de credenciales de producción y OAuth (`client_id`, `client_secret`, `access_token`, `public_key`) almacenadas de forma segura y aplicadas en caliente sin reiniciar el backend.
   * URL de webhook preconfigurada para notificaciones automáticas IPN.

6. **Eliminación y Baja de Empresas (`/saas/companies`)**:
   * Capacidad de dar de baja empresas del sistema de forma segura (*Soft-Delete*).
   * Desactivación en cascada de empleados y administradores.
   * Cancelación automática de suscripciones vigentes.
   * Modal de confirmación con doble validación de seguridad (requiere tipear `ELIMINAR`).

7. **Acceso de Auditoría y Fotos**:
   * Capacidad de inspeccionar registros de auditoría y fotos de cualquier empresa sin bloqueos de aislamiento de prefijo.

---

## 4. 🔄 Cómo Cambiar o Promover Otro Usuario a Superadmin

### Opción A: Mediante Variable de Entorno (Recomendado)
En tu entorno de Dokploy o archivo `.env`, cambia:
```env
SUPER_ADMIN_EMAIL=tu_email_personal@dominio.com
```
Reinicia el contenedor backend. Al arrancar, el backend detectará el nuevo email y le otorgará el rol Superadmin automáticamente.

### Opción B: Directo en Base de Datos PostgreSQL
Si necesitas otorgarle superadmin a un usuario manualmente por consola SQL:
```sql
UPDATE employees SET is_super_admin = true WHERE email = 'tu_email@dominio.com';
```
*(El cambio toma efecto en el siguiente login del usuario).*
