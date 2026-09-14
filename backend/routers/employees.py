import logging
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from typing import List, Optional
from datetime import time as time_type
from schemas import EmployeeCreate, EmployeeUpdate, EmployeeOut, ScheduleCreate, EmployeeBulkCreate
from auth import get_current_admin, get_password_hash
from database import database
from config import settings
from schedule_validator import find_schedule_conflict
import uuid
import os
import json
import secrets

logger = logging.getLogger(__name__)

# Whitelist of columns allowed in dynamic UPDATE SET clauses.
# Prevents column injection if schemas are extended unexpectedly.
_ALLOWED_EMPLOYEE_UPDATE_FIELDS = {
    "name", "email", "password_hash", "active",
    "document_id", "address", "phone",
}

router = APIRouter(prefix="/api/employees", tags=["employees"])

@router.get("/", response_model=List[dict])
async def list_employees(
    active_only: Optional[bool] = None,
    current_user=Depends(get_current_admin)
):
    company_id = current_user["company_id"]
    conditions = ["company_id = :cid"]
    params = {"cid": company_id}
    if active_only is not None:
        conditions.append("active = :act")
        params["act"] = active_only
    where = " AND ".join(conditions)
    rows = await database.fetch_all(
        f"SELECT id, name, email, role, active, created_at, document_id, address, phone FROM employees WHERE {where} ORDER BY name",
        params
    )
    return [dict(r) for r in rows]

@router.post("/bulk")
async def bulk_create_employees(data: EmployeeBulkCreate, current_user=Depends(get_current_admin)):
    company_id = current_user["company_id"]
    from resource_limiter import check_company_active
    await check_company_active(company_id)

    if not data.employees:
        raise HTTPException(status_code=400, detail="La lista de empleados no puede estar vacía")

    # Check plan limit against addition
    company = await database.fetch_one(
        """
        SELECT c.max_employees_override, p.max_employees
        FROM companies c
        LEFT JOIN plans p ON c.plan_id = p.id
        WHERE c.id = :cid
        """,
        {"cid": company_id}
    )
    limit = company["max_employees_override"] or company["max_employees"] or 10
    count_row = await database.fetch_one(
        "SELECT COUNT(*) as cnt FROM employees WHERE company_id = :cid AND active = true",
        {"cid": company_id}
    )
    current_cnt = count_row["cnt"] if count_row else 0
    if current_cnt + len(data.employees) > limit:
        raise HTTPException(
            status_code=400,
            detail=f"La importación excede el límite de su plan ({current_cnt + len(data.employees)}/{limit} empleados). Actualice su plan."
        )

    # Fetch existing emails in company to prevent duplicates
    existing_rows = await database.fetch_all(
        "SELECT LOWER(email) as email FROM employees WHERE company_id = :cid",
        {"cid": company_id}
    )
    existing_emails = {r["email"] for r in existing_rows}

    created = 0
    errors = []
    seen_batch_emails = set()

    # Wrap all inserts in a single transaction for atomicity
    async with database.transaction():
        for idx, item in enumerate(data.employees):
            clean_email = item.email.strip().lower()
            if clean_email in existing_emails or clean_email in seen_batch_emails:
                errors.append(f"Fila {idx + 1}: Email '{item.email}' ya registrado.")
                continue
            
            seen_batch_emails.add(clean_email)
            # Generate random secure temporary password if none provided (H13)
            auto_pwd = item.password or f"UruCheck{secrets.token_hex(4)}!"
            hashed = get_password_hash(auto_pwd)
            await database.execute(
                """
                INSERT INTO employees (company_id, name, email, password_hash, role, document_id, address, phone)
                VALUES (:cid, :name, :email, :password_hash, :role, :document_id, :address, :phone)
                """,
                {
                    "cid": company_id,
                    "name": item.name.strip(),
                    "email": clean_email,
                    "password_hash": hashed,
                    "role": item.role or "employee",
                    "document_id": item.document_id,
                    "address": item.address,
                    "phone": item.phone,
                }
            )
            created += 1

    return {
        "created_count": created,
        "errors": errors,
        "message": f"Se crearon {created} empleado(s) exitosamente." + (f" Hubo {len(errors)} advertencia(s)." if errors else "")
    }

@router.post("/")
async def create_employee(data: EmployeeCreate, current_user=Depends(get_current_admin)):
    company_id = current_user["company_id"]

    # Check company active status and enforce plan employee limit
    from resource_limiter import check_company_active, check_employee_limit
    await check_company_active(company_id)
    await check_employee_limit(company_id)

    clean_email = data.email.strip() if data.email else ""
    existing = await database.fetch_one(
        "SELECT id FROM employees WHERE company_id = :cid AND LOWER(email) = LOWER(:email)",
        {"cid": company_id, "email": clean_email}
    )
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un empleado registrado con este correo electrónico.")

    hashed = get_password_hash(data.password)
    employee_id = await database.execute(
        """
        INSERT INTO employees (company_id, name, email, password_hash, role, document_id, address, phone)
        VALUES (:cid, :name, :email, :password_hash, :role, :document_id, :address, :phone)
        RETURNING id
        """,
        {
            "cid": company_id,
            "name": data.name,
            "email": clean_email,
            "password_hash": hashed,
            "role": data.role,
            "document_id": data.document_id,
            "address": data.address,
            "phone": data.phone
        }
    )
    return {"id": str(employee_id), "message": "Empleado creado correctamente"}

@router.patch("/{employee_id}")
async def update_employee(employee_id: str, data: EmployeeUpdate, current_user=Depends(get_current_admin)):
    company_id = current_user["company_id"]

    # Verify ownership
    emp = await database.fetch_one(
        "SELECT id FROM employees WHERE id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id}
    )
    if not emp:
        raise HTTPException(status_code=404, detail="El empleado no existe o no pertenece a su empresa.")

    updates = {}
    if data.name: updates["name"] = data.name
    if data.email:
        clean_email = data.email.strip()
        existing = await database.fetch_one(
            "SELECT id FROM employees WHERE company_id = :cid AND LOWER(email) = LOWER(:email) AND id != :eid",
            {"cid": company_id, "email": clean_email, "eid": employee_id}
        )
        if existing:
            raise HTTPException(status_code=400, detail="El correo electrónico ya está registrado por otro empleado.")
        updates["email"] = clean_email
    if data.password: updates["password_hash"] = get_password_hash(data.password)
    if data.active is not None: updates["active"] = data.active
    if data.document_id is not None: updates["document_id"] = data.document_id
    if data.address is not None: updates["address"] = data.address
    if data.phone is not None: updates["phone"] = data.phone

    if not updates:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    # Security: only allow whitelisted column names in the SET clause
    safe_updates = {k: v for k, v in updates.items() if k in _ALLOWED_EMPLOYEE_UPDATE_FIELDS}
    if not safe_updates:
        raise HTTPException(status_code=400, detail="No hay campos válidos para actualizar")

    set_clause = ", ".join([f"{k} = :{k}" for k in safe_updates.keys()])
    safe_updates["id"] = employee_id
    safe_updates["cid"] = company_id
    await database.execute(
        f"UPDATE employees SET {set_clause} WHERE id = :id AND company_id = :cid", safe_updates
    )
    return {"message": "Actualizado correctamente"}

@router.get("/{employee_id}")
async def get_employee(employee_id: str, current_user=Depends(get_current_admin)):
    company_id = current_user["company_id"]
    emp = await database.fetch_one(
        "SELECT id, name, email, role, active, created_at, document_id, address, phone FROM employees WHERE id = :id AND company_id = :cid",
        {"id": employee_id, "cid": company_id}
    )
    if not emp:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    return dict(emp)

@router.delete("/{employee_id}")
async def delete_employee(employee_id: str, current_user=Depends(get_current_admin)):
    try:
        company_id = current_user["company_id"]

        # 1. Verify employee exists and belongs to this company
        emp_row = await database.fetch_one(
            "SELECT id, name, email, role, face_reference_path FROM employees WHERE id = :id AND company_id = :cid",
            {"id": employee_id, "cid": company_id}
        )
        if not emp_row:
            raise HTTPException(status_code=404, detail="Empleado no encontrado")
        emp = dict(emp_row)

        # 2. Prevent self-deletion of the current admin user
        if str(current_user["id"]) == str(employee_id):
            raise HTTPException(
                status_code=400,
                detail="No puedes eliminar tu propia cuenta de administrador en uso."
            )

        # 3. Prevent deleting the only active administrator of the company
        if emp.get("role") == "admin":
            admin_count = await database.fetch_one(
                "SELECT COUNT(*) as cnt FROM employees WHERE company_id = :cid AND role = 'admin' AND active = true",
                {"cid": company_id}
            )
            if admin_count and admin_count["cnt"] <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="No se puede eliminar el único administrador activo de la empresa. Asigna el rol administrador a otro usuario primero."
                )

        # 4. Clean up disk files: face enrollment photo
        face_path = emp.get("face_reference_path")
        if face_path:
            try:
                if os.path.exists(face_path):
                    os.remove(face_path)
            except Exception as e:
                logger.warning("No se pudo eliminar foto facial en disco de %s: %s", employee_id, e)

        # Clean up disk files: attendance check-in photos
        try:
            attendance_photos = await database.fetch_all(
                "SELECT photo_path FROM attendance_logs WHERE employee_id = :eid AND photo_path IS NOT NULL",
                {"eid": employee_id}
            )
            for row in attendance_photos:
                p = dict(row).get("photo_path")
                if p:
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning("Error buscando fotos de asistencia para eliminar: %s", e)

        # Clean up disk files: leave request certificate attachments
        try:
            leave_certs = await database.fetch_all(
                "SELECT certificate_path FROM leave_requests WHERE employee_id = :eid AND certificate_path IS NOT NULL",
                {"eid": employee_id}
            )
            for row in leave_certs:
                c = dict(row).get("certificate_path")
                if c:
                    try:
                        if os.path.exists(c):
                            os.remove(c)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning("Error buscando certificados de licencias para eliminar: %s", e)

        # 5. Defensively delete related rows in database
        # Order matters! Child tables with FK to schedules (like attendance_logs) must be deleted before schedules.
        # Filter by employee_id alone so legacy records with NULL company_id are also purged cleanly.
        child_cleanup_queries = [
            ("DELETE FROM attendance_logs WHERE employee_id = :eid", {"eid": employee_id}),
            ("DELETE FROM employee_location_reports WHERE employee_id = :eid", {"eid": employee_id}),
            ("DELETE FROM leave_requests WHERE employee_id = :eid", {"eid": employee_id}),
            ("DELETE FROM password_reset_requests WHERE employee_id = :eid", {"eid": employee_id}),
            ("DELETE FROM streaks WHERE employee_id = :eid", {"eid": employee_id}),
            ("DELETE FROM bonus_records WHERE employee_id = :eid", {"eid": employee_id}),
            ("DELETE FROM employee_geofences WHERE employee_id = :eid", {"eid": employee_id}),
            ("DELETE FROM schedules WHERE employee_id = :eid", {"eid": employee_id}),
        ]
        for q, params in child_cleanup_queries:
            try:
                await database.execute(q, params)
            except Exception as ex:
                logger.warning("Error defensivo eliminando registros relacionados (%s): %s", q, ex)

        # Finally delete the employee record
        await database.execute(
            "DELETE FROM employees WHERE id = :eid AND company_id = :cid",
            {"eid": employee_id, "cid": company_id}
        )

        # 6. Audit log
        try:
            await database.execute(
                """
                INSERT INTO audit_logs (company_id, user_id, action, resource, resource_id, details)
                VALUES (:cid, :uid, 'employee_deleted', 'employee', :eid, :details)
                """,
                {
                    "cid": company_id,
                    "uid": current_user["id"],
                    "eid": employee_id,
                    "details": json.dumps({"deleted_name": emp["name"], "deleted_email": emp["email"]})
                }
            )
        except Exception as e:
            logger.warning("Error al registrar auditoría de eliminación de empleado: %s", e)

        return {"message": f"Empleado {emp['name']} y todos sus datos asociados fueron eliminados permanentemente", "id": employee_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error crítico al eliminar empleado %s: %s", employee_id, e)
        raise HTTPException(
            status_code=500,
            detail=f"Error al eliminar empleado: {str(e)}"
        )

@router.get("/{employee_id}/schedules")
async def get_schedules(employee_id: str, current_user=Depends(get_current_admin)):
    company_id = current_user["company_id"]
    rows = await database.fetch_all(
        "SELECT * FROM schedules WHERE employee_id = :eid AND company_id = :cid ORDER BY start_time ASC",
        {"eid": employee_id, "cid": company_id}
    )
    return [dict(r) for r in rows]

@router.post("/{employee_id}/schedules")
async def create_schedule(employee_id: str, data: ScheduleCreate, current_user=Depends(get_current_admin)):
    company_id = current_user["company_id"]

    # Validate days of week
    if not data.day_of_week:
        raise HTTPException(
            status_code=400,
            detail="Debe seleccionar al menos un día de la semana para asignar el horario."
        )
    for day in data.day_of_week:
        if day < 1 or day > 7:
            raise HTTPException(
                status_code=400,
                detail=f"Día inválido ({day}). Los días deben ser del 1 (Lunes) al 7 (Domingo)."
            )

    # Validate break_mode
    if data.break_mode not in ("none", "flexible", "fixed"):
        raise HTTPException(
            status_code=400,
            detail="La modalidad de descanso debe ser 'none' (Sin descanso), 'flexible' (Flexible) o 'fixed' (Horario fijo)."
        )

    # Verify employee belongs to company
    emp = await database.fetch_one(
        "SELECT id, name FROM employees WHERE id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id}
    )
    if not emp:
        raise HTTPException(
            status_code=404,
            detail="El empleado seleccionado no existe o no pertenece a su empresa."
        )

    # Validate geofence belongs to company if provided
    if data.geofence_id:
        gf = await database.fetch_one(
            "SELECT id, name FROM geofences WHERE id = :gid AND company_id = :cid",
            {"gid": str(data.geofence_id), "cid": company_id}
        )
        if not gf:
            raise HTTPException(
                status_code=404,
                detail="La ubicación o geocerca seleccionada no existe o no pertenece a su empresa."
            )

    # Validate start_time and end_time
    if not data.start_time or not data.end_time:
        raise HTTPException(
            status_code=400,
            detail="Debe especificar tanto la hora de entrada como la hora de salida del turno."
        )
    if data.start_time == data.end_time:
        raise HTTPException(
            status_code=400,
            detail="La hora de entrada y la hora de salida no pueden ser iguales."
        )

    # Validate tolerance
    if data.tolerance_minutes is not None and (data.tolerance_minutes < 0 or data.tolerance_minutes > 120):
        raise HTTPException(
            status_code=400,
            detail="La tolerancia debe ser un valor entre 0 y 120 minutos."
        )

    # Validate break settings
    if data.break_mode == "fixed":
        if not data.break_start_time or not data.break_end_time:
            raise HTTPException(
                status_code=400,
                detail="Para el modo de descanso en horario fijo, debe especificar la hora de inicio y la de fin del descanso."
            )
        if data.break_start_time == data.break_end_time:
            raise HTTPException(
                status_code=400,
                detail="La hora de inicio y fin del descanso fijo no pueden ser iguales."
            )
    elif data.break_mode == "flexible":
        if data.break_duration_minutes is not None and (data.break_duration_minutes <= 0 or data.break_duration_minutes > 480):
            raise HTTPException(
                status_code=400,
                detail="La duración del descanso flexible debe ser mayor a 0 y menor a 480 minutos (8 horas)."
            )

    # Check for schedule overlap / collision with existing schedules of this employee
    existing_schedules = await database.fetch_all(
        "SELECT id, slot_name, day_of_week, start_time, end_time FROM schedules WHERE employee_id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id}
    )
    conflict = find_schedule_conflict(
        existing_schedules=[dict(s) for s in existing_schedules],
        new_days=data.day_of_week,
        new_start=data.start_time,
        new_end=data.end_time
    )
    if conflict:
        raise HTTPException(status_code=400, detail=conflict["message"])

    try:
        await database.execute(
            """
            INSERT INTO schedules (company_id, employee_id, day_of_week, start_time, end_time, slot_name,
                                   tolerance_minutes, geofence_id, break_mode, break_start_time, break_end_time, break_duration_minutes)
            VALUES (:cid, :eid, :days, :start, :end, :slot_name, :tol, :geofence_id, :break_mode, :break_start, :break_end, :break_dur)
            """,
            {
                "cid": company_id,
                "eid": employee_id,
                "days": data.day_of_week,
                "start": data.start_time,
                "end": data.end_time,
                "slot_name": data.slot_name.strip() if data.slot_name else None,
                "tol": data.tolerance_minutes if data.tolerance_minutes is not None else 5,
                "geofence_id": str(data.geofence_id) if data.geofence_id else None,
                "break_mode": data.break_mode,
                "break_start": data.break_start_time if data.break_mode == "fixed" else None,
                "break_end": data.break_end_time if data.break_mode == "fixed" else None,
                "break_dur": data.break_duration_minutes if data.break_mode == "flexible" else None,
            }
        )
    except Exception as e:
        logger.error(f"Error al guardar horario en base de datos: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo guardar el horario en la base de datos. Verifique que los campos sean válidos."
        )

    return {"message": "Horario asignado exitosamente"}

@router.delete("/{employee_id}/schedules/{schedule_id}")
async def delete_schedule(employee_id: str, schedule_id: str, current_user=Depends(get_current_admin)):
    company_id = current_user["company_id"]
    existing = await database.fetch_one(
        "SELECT id FROM schedules WHERE id = :sid AND employee_id = :eid AND company_id = :cid",
        {"sid": schedule_id, "eid": employee_id, "cid": company_id}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="El horario no existe o ya fue eliminado previamente.")

    await database.execute(
        "DELETE FROM schedules WHERE id = :sid AND employee_id = :eid AND company_id = :cid",
        {"sid": schedule_id, "eid": employee_id, "cid": company_id}
    )
    return {"message": "Horario eliminado correctamente"}

# ─── Face enrollment endpoints ───────────────────────────────────────────────

@router.post("/{employee_id}/face-enroll")
async def enroll_face(
    employee_id: str,
    photo: UploadFile = File(...),
    current_user=Depends(get_current_admin)
):
    company_id = current_user["company_id"]

    emp = await database.fetch_one(
        "SELECT id, name FROM employees WHERE id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id}
    )
    if not emp:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    if not photo.content_type or not photo.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen")

    old = await database.fetch_one(
        "SELECT face_reference_path FROM employees WHERE id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id}
    )
    if old and old["face_reference_path"] and os.path.exists(old["face_reference_path"]):
        try:
            os.remove(old["face_reference_path"])
        except Exception:
            pass

    ext = photo.filename.split(".")[-1].lower() if photo.filename else "jpg"
    if ext not in ("png", "jpg", "jpeg", "webp"):
        raise HTTPException(status_code=400, detail="Formato no permitido. Use PNG, JPG o WebP")

    content = await photo.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB limit (H8)
        raise HTTPException(status_code=413, detail="La imagen excede el tamaño máximo permitido (10 MB)")

    face_dir = os.path.join(settings.PHOTOS_PATH, "face_references")
    os.makedirs(face_dir, exist_ok=True)
    filename = f"face_{company_id}_{employee_id}_{uuid.uuid4().hex}.{ext}"
    face_path = os.path.join(face_dir, filename)

    with open(face_path, "wb") as f:
        f.write(content)

    # Fetch provider from company configuration
    config = await database.fetch_one(
        "SELECT face_verification_provider FROM company_config WHERE company_id = :cid",
        {"cid": company_id}
    )
    provider = config["face_verification_provider"] if config else "face_recognition"

    from face_service import has_face_reference
    has_face = await has_face_reference(face_path, provider=provider)
    if not has_face:
        os.remove(face_path)
        raise HTTPException(
            status_code=400,
            detail="No se pudo detectar un rostro en la imagen. Verifica que la foto sea clara y tenga buena iluminación."
        )

    await database.execute(
        "UPDATE employees SET face_reference_path = :path WHERE id = :eid AND company_id = :cid",
        {"path": face_path, "eid": employee_id, "cid": company_id}
    )

    return {
        "message": f"Rostro de {emp['name']} registrado correctamente",
        "enrolled": True,
    }


@router.delete("/{employee_id}/face-enroll")
async def remove_face_enrollment(employee_id: str, current_user=Depends(get_current_admin)):
    company_id = current_user["company_id"]

    emp = await database.fetch_one(
        "SELECT id, name, face_reference_path FROM employees WHERE id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id}
    )
    if not emp:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    if emp["face_reference_path"] and os.path.exists(emp["face_reference_path"]):
        try:
            os.remove(emp["face_reference_path"])
        except Exception:
            pass

    await database.execute(
        "UPDATE employees SET face_reference_path = NULL WHERE id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id}
    )

    return {"message": f"Referencia facial de {emp['name']} eliminada"}


@router.get("/{employee_id}/face-status")
async def get_face_status(employee_id: str, current_user=Depends(get_current_admin)):
    company_id = current_user["company_id"]

    emp = await database.fetch_one(
        "SELECT id, name, face_reference_path FROM employees WHERE id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id}
    )
    if not emp:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    has_face = emp["face_reference_path"] is not None and os.path.exists(emp["face_reference_path"])
    return {
        "employee_id": str(emp["id"]),
        "employee_name": emp["name"],
        "has_face_reference": has_face
    }


@router.post("/{employee_id}/reset-device")
async def reset_device(employee_id: str, current_user=Depends(get_current_admin)):
    company_id = current_user["company_id"]
    
    emp = await database.fetch_one(
        "SELECT id, name FROM employees WHERE id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id}
    )
    if not emp:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
        
    await database.execute(
        "UPDATE employees SET device_id = NULL WHERE id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id}
    )
    
    return {"message": f"Dispositivo desvinculado para {emp['name']}. Ahora podrá iniciar sesión desde un nuevo dispositivo."}
