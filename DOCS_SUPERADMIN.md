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

2. **Gestión de Empresas Clientes (`/saas-companies`)**:
   * Listado de todas las empresas registradas en la plataforma.
   * Capacidad de suspender, reactivar o cambiar de plan a cualquier empresa cliente.
   * Asignación de overrides personalizados de límite de empleados (`max_employees_override`).

3. **Gestión de Planes y Precios (`/saas-plans`)**:
   * Crear, editar precios (mensual/anual), límites de empleados y geocercas, y activar/desactivar funciones (reconocimiento facial, webhooks, chat IA, etc.).

4. **Acceso de Auditoría y Fotos**:
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
