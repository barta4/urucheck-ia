import logging
import asyncio
import httpx
import os
import urllib.parse
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from database import database
from config import settings
from routers.notifications import send_push_notification

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()
TZ = ZoneInfo(settings.TIMEZONE)



async def get_company_config(company_id: str) -> dict:
    """Fetch company configuration row. Returns empty dict on error."""
    try:
        row = await database.fetch_one(
            """SELECT webhook_url, smtp_host, smtp_port, smtp_username, smtp_password,
                      smtp_from_email, smtp_to_email, email_notify_monthly_report,
                      webhook_notify_checkin, webhook_notify_checkout, webhook_notify_break,
                      webhook_notify_late, webhook_notify_absence
               FROM company_config WHERE company_id = :cid""",
            {"cid": company_id},
        )
        return dict(row) if row else {}
    except Exception as exc:
        logger.error("[agent_controller] Fallo al recuperar config empresa %s: %s", company_id[:8], exc)
        return {}


async def _get_employee_push_token(employee_id: str, company_id: str) -> tuple[str | None, str | None]:
    """Return (expo_push_token, name) for an employee. Returns (None, None) if not found."""
    emp = await database.fetch_one(
        "SELECT expo_push_token, name FROM employees WHERE id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id},
    )
    if emp:
        return emp["expo_push_token"], emp["name"]
    return None, None



async def send_webhook(event_type: str, payload: dict, company_id: str, notify_flag: str = None) -> None:
    """Send a webhook event to the company's configured webhook URL."""
    try:
        config = await get_company_config(company_id)
        webhook_url = config.get("webhook_url")

        if not webhook_url:
            return

        if notify_flag and not config.get(notify_flag, False):
            return

        # Log only the domain, not the full URL (may contain tokens in query params)
        domain = urllib.parse.urlparse(webhook_url).netloc
        async with httpx.AsyncClient() as client:
            await client.post(
                webhook_url,
                json={
                    "event": event_type,
                    "data": payload,
                    "timestamp": datetime.now(TZ).isoformat(),
                },
                timeout=10.0,
            )
            logger.info("Webhook [%s] enviado a %s", event_type, domain)
    except Exception as exc:
        logger.error("Error enviando webhook [%s]: %s", event_type, exc)



async def _notify_event(
    event_type: str,
    employee_id: str,
    company_id: str,
    extra: dict = None,
    notify_flag: str = None,
) -> None:
    try:
        emp = await database.fetch_one(
            "SELECT name FROM employees WHERE id = :eid AND company_id = :cid",
            {"eid": employee_id, "cid": company_id},
        )
        name = emp["name"] if emp else "Desconocido"
        payload = {"employee_id": str(employee_id), "employee_name": name, "company_id": str(company_id), **(extra or {})}
        await send_webhook(event_type, payload, company_id, notify_flag=notify_flag)
    except Exception as e:
        logger.error("Error en _notify_event(%s): %s", event_type, e)


async def notify_checkin(
    employee_id: str,
    company_id: str,
    status: str,
    timestamp: str,
    geofence_name: str = "Ubicación General",
) -> None:
    """Send webhook and push notification on employee check-in."""
    extra = {"status": status, "timestamp": timestamp, "type": "check_in", "geofence_name": geofence_name}
    await _notify_event("employee_checkin", employee_id, company_id, extra, notify_flag="webhook_notify_checkin")
    # Push notification to the employee
    push_token, name = await _get_employee_push_token(employee_id, company_id)
    if push_token:
        emoji = "✅" if status == "on_time" else "⚠️"
        label = "puntual" if status == "on_time" else "tarde"
        await send_push_notification(
            to=push_token,
            title=f"{emoji} Entrada registrada",
            body=f"Hola {name}, tu entrada de las {timestamp} en {geofence_name} fue registrada como {label}."
        )


async def notify_checkout(employee_id: str, company_id: str, timestamp: str, geofence_name: str = "Ubicación General"):
    """Send webhook on check-out."""
    await _notify_event(
        "employee_checkout", employee_id, company_id,
        {"timestamp": timestamp, "type": "check_out", "geofence_name": geofence_name},
        notify_flag="webhook_notify_checkout"
    )



async def notify_break(
    employee_id: str,
    company_id: str,
    break_type: str,
    timestamp: str,
    geofence_name: str = "Ubicación General",
    status: str = "on_time",
    minutes_late: int = 0,
) -> None:
    """Send webhook and push notification on break start/end."""
    extra = {
        "timestamp": timestamp,
        "type": break_type,
        "geofence_name": geofence_name,
        "status": status,
        "minutes_late": minutes_late,
    }
    await _notify_event(
        f"employee_{break_type}", employee_id, company_id,
        extra,
        notify_flag="webhook_notify_break",
    )
    # If returned late from a fixed break, notify the employee
    if break_type == "break_end" and status == "late":
        push_token, name = await _get_employee_push_token(employee_id, company_id)
        if push_token:
            await send_push_notification(
                to=push_token,
                title="⚠️ Regreso de descanso tardío",
                body=f"Hola {name}, regresaste {minutes_late} minuto(s) tarde de tu descanso fijado en {geofence_name}.",
            )



async def notify_late(
    employee_id: str,
    company_id: str,
    minutes_late: int,
    geofence_name: str = "Ubicación General",
) -> None:
    """Send webhook and push notification for late arrival."""
    await _notify_event(
        "employee_late", employee_id, company_id,
        {"minutes_late": minutes_late, "geofence_name": geofence_name},
        notify_flag="webhook_notify_late",
    )
    push_token, name = await _get_employee_push_token(employee_id, company_id)
    if push_token:
        await send_push_notification(
            to=push_token,
            title="⚠️ Llegada tarde registrada",
            body=f"Hola {name}, llegaste {minutes_late} minuto(s) tarde a {geofence_name}. Tu racha de puntualidad se ha reiniciado.",
        )

# ─── Daily absence check (multi-tenant) ──────────────────────────────────────

async def check_daily_absences():
    today = date.today()
    weekday = today.weekday() + 1
    now = datetime.now(TZ).time()
    logger.info("[Agente] Verificando ausencias del %s...", today)

    companies = await database.fetch_all("SELECT id FROM companies WHERE active = true")

    for company in companies:
        cid = str(company["id"])
        scheduled = await database.fetch_all(
            """
            SELECT e.id, e.name, s.start_time
            FROM employees e
            JOIN schedules s ON e.id = s.employee_id
            WHERE e.active = true AND e.company_id = :cid AND :day = ANY(s.day_of_week)
            """,
            {"cid": cid, "day": weekday}
        )

        from rules_engine import ensure_time
        for emp in scheduled:
            s_time = ensure_time(emp["start_time"])
            if s_time and now < s_time:
                continue

            check_in = await database.fetch_one(
                "SELECT id FROM attendance_logs WHERE employee_id = :eid AND company_id = :cid AND type = 'check_in' AND DATE(timestamp) = :today",
                {"eid": str(emp["id"]), "cid": cid, "today": today}
            )
            if not check_in:
                # Check for approved leave
                leave = await database.fetch_one(
                    """SELECT id FROM leave_requests 
                       WHERE employee_id = :eid AND company_id = :cid 
                         AND status = 'approved' 
                         AND :today >= start_date AND :today <= end_date""",
                    {"eid": str(emp["id"]), "cid": cid, "today": today}
                )
                
                if not leave:
                    await _notify_event(
                        "employee_absent", str(emp["id"]), cid,
                        {"message": f"No registró entrada hoy ({s_time or emp['start_time']} era su horario)"},
                        notify_flag="webhook_notify_absence"
                    )
                    logger.info("[Agente] Ausencia detectada: %s (empresa %s...)", emp['name'], cid[:8])


# ─── Monthly report (multi-tenant) ───────────────────────────────────────────

async def run_monthly_report_for_company(cid: str):
    today = date.today()
    first_day_of_this_month = today.replace(day=1)
    last_day_of_prev_month = first_day_of_this_month - timedelta(days=1)
    first_day_of_prev_month = last_day_of_prev_month.replace(day=1)

    month_name = first_day_of_prev_month.strftime("%B")
    months_es = {
        "January": "Enero", "February": "Febrero", "March": "Marzo", "April": "Abril",
        "May": "Mayo", "June": "Junio", "July": "Julio", "August": "Agosto",
        "September": "Septiembre", "October": "Octubre", "November": "Noviembre", "December": "Diciembre"
    }
    month_label_es = f"{months_es.get(month_name, month_name)} {first_day_of_prev_month.year}"
    logger.info("[Agente] Generando reporte mensual de %s para empresa %s...", month_label_es, cid[:8])

    employees = await database.fetch_all(
        "SELECT id, name, document_id, address, phone FROM employees WHERE active = true AND company_id = :cid ORDER BY name", 
        {"cid": cid}
    )
    report_data = []

    for emp in employees:
        eid = str(emp["id"])

        check_ins = await database.fetch_one(
            """SELECT COUNT(*) FROM attendance_logs
               WHERE employee_id = :eid AND company_id = :cid AND type = 'check_in'
               AND DATE(timestamp) BETWEEN :start AND :end""",
            {"eid": eid, "cid": cid, "start": first_day_of_prev_month, "end": last_day_of_prev_month}
        )
        lates = await database.fetch_one(
            """SELECT COUNT(*) FROM attendance_logs
               WHERE employee_id = :eid AND company_id = :cid AND type = 'check_in' AND status = 'late'
               AND DATE(timestamp) BETWEEN :start AND :end""",
            {"eid": eid, "cid": cid, "start": first_day_of_prev_month, "end": last_day_of_prev_month}
        )

        hours_rows = await database.fetch_all(
            """
            SELECT DATE(timestamp) as day,
                MIN(CASE WHEN type = 'check_in'  THEN timestamp END) as ci,
                MAX(CASE WHEN type = 'check_out' THEN timestamp END) as co
            FROM attendance_logs
            WHERE employee_id = :eid AND company_id = :cid
              AND DATE(timestamp) BETWEEN :start AND :end
              AND type IN ('check_in', 'check_out')
            GROUP BY DATE(timestamp)
            """,
            {"eid": eid, "cid": cid, "start": first_day_of_prev_month, "end": last_day_of_prev_month}
        )
        total_minutes = 0
        for row in hours_rows:
            if row["ci"] and row["co"]:
                diff = (row["co"] - row["ci"]).total_seconds() / 60
                total_minutes += max(0, diff)

        total_hours = round(total_minutes / 60, 2)
        attended = check_ins["count"] if check_ins else 0
        late_count = lates["count"] if lates else 0

        report_data.append({
            "employee_id": eid,
            "name": emp["name"],
            "document_id": emp["document_id"] or "No registrado",
            "address": emp["address"] or "No registrado",
            "phone": emp["phone"] or "No registrado",
            "mes": month_label_es,
            "dias_asistidos": attended,
            "tardanzas": late_count,
            "horas_totales": total_hours,
            "bono_elegible": late_count == 0 and attended > 0,
        })

    if report_data:
        payload = {
            "company_id": cid,
            "month": first_day_of_prev_month.strftime("%Y-%m"),
            "month_label": month_label_es,
            "total_employees": len(report_data),
            "report": report_data
        }
        await send_webhook("monthly_attendance_report", payload, cid)

        # Enviar correo SMTP si está configurado
        config = await get_company_config(cid)
        if config.get("smtp_host") and config.get("smtp_username") and config.get("smtp_password"):
            html_rows = ""
            for row in report_data:
                bono_status = "✅ Elegible" if row["bono_elegible"] else "❌ No Elegible"
                html_rows += f"""
                <tr style="border-bottom: 1px solid #e2e8f0; font-size: 13px;">
                    <td style="padding: 10px; font-weight: bold; color: #1a202c;">{row['name']}</td>
                    <td style="padding: 10px; color: #4a5568;">{row['document_id']}</td>
                    <td style="padding: 10px; color: #4a5568;">{row['phone']}</td>
                    <td style="padding: 10px; color: #4a5568;">{row['address']}</td>
                    <td style="padding: 10px; text-align: center; color: #1a202c;">{row['dias_asistidos']}</td>
                    <td style="padding: 10px; text-align: center; color: #e53e3e; font-weight: bold;">{row['tardanzas']}</td>
                    <td style="padding: 10px; text-align: center; color: #3182ce; font-weight: bold;">{row['horas_totales']} hs</td>
                    <td style="padding: 10px; text-align: center; font-weight: bold;">{bono_status}</td>
                </tr>
                """

            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f7fafc;">
                <div style="max-width: 900px; margin: 0 auto; background-color: #ffffff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e2e8f0;">
                    <div style="text-align: center; margin-bottom: 30px; border-bottom: 2px solid #3182ce; padding-bottom: 20px;">
                        <h1 style="color: #2b6cb0; margin: 0; font-size: 22px;">Reporte Mensual de Asistencia</h1>
                        <p style="color: #718096; margin: 5px 0 0 0; font-size: 15px;">Período: {month_label_es}</p>
                    </div>
                    
                    <p style="color: #4a5568; font-size: 15px; line-height: 1.5;">
                        Estimado Administrador,<br><br>
                        A continuación, adjuntamos el análisis mensual detallado de asistencia, puntualidad y datos de contacto de sus empleados correspondiente al mes de <strong>{month_label_es}</strong>.
                    </p>
                    
                    <table style="width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 13px;">
                        <thead>
                            <tr style="background-color: #ebf8ff; border-bottom: 2px solid #bee3f8;">
                                <th style="padding: 12px; text-align: left; color: #2b6cb0;">Empleado</th>
                                <th style="padding: 12px; text-align: left; color: #2b6cb0;">C.I.</th>
                                <th style="padding: 12px; text-align: left; color: #2b6cb0;">Teléfono</th>
                                <th style="padding: 12px; text-align: left; color: #2b6cb0;">Dirección</th>
                                <th style="padding: 12px; text-align: center; color: #2b6cb0;">Asistencias</th>
                                <th style="padding: 12px; text-align: center; color: #2b6cb0;">Tardanzas</th>
                                <th style="padding: 12px; text-align: center; color: #2b6cb0;">Horas</th>
                                <th style="padding: 12px; text-align: center; color: #2b6cb0;">Bono</th>
                            </tr>
                        </thead>
                        <tbody>
                            {html_rows}
                        </tbody>
                    </table>
                    
                    <div style="margin-top: 30px; padding: 15px; background-color: #f7fafc; border-radius: 8px; border-left: 4px solid #3182ce; font-size: 12px; color: #718096;">
                        Este es un reporte automático generado y enviado por la plataforma de <strong>UruCheck IA</strong> utilizando la configuración SMTP de su empresa.
                    </div>
                </div>
            </body>
            </html>
            """
            from email_service import send_smtp_email
            send_smtp_email(
                config=config,
                subject=f"UruCheck IA - Reporte Mensual de Asistencia ({month_label_es})",
                html_content=html_content,
                text_content=f"Reporte Mensual de Asistencia ({month_label_es}). Por favor, abra el correo en formato HTML para visualizar el reporte."
            )
        print(f"[Agente] Reporte mensual procesado para empresa {cid[:8]}... ({len(report_data)} empleados).")

async def generate_monthly_report():
    companies = await database.fetch_all("SELECT id FROM companies WHERE active = true")
    for company in companies:
        try:
            await run_monthly_report_for_company(str(company["id"]))
        except Exception as e:
            print(f"[Agente Error] Error generando reporte mensual para {company['id']}: {e}")


# ─── Data retention cleanup (multi-tenant) ────────────────────────────────────

async def cleanup_old_photos():
    from datetime import timedelta
    cutoff = (datetime.now(TZ) - timedelta(days=90)).replace(tzinfo=None)
    print(f"[Agente] Limpiando fotos anteriores a {cutoff.date()}...")

    old_photos = await database.fetch_all(
        """
        SELECT id, photo_path FROM attendance_logs
        WHERE photo_path IS NOT NULL AND photo_path != ''
        AND timestamp < :cutoff
        """,
        {"cutoff": cutoff}
    )

    deleted = 0
    for row in old_photos:
        path = row["photo_path"]
        if path and os.path.exists(path):
            try:
                os.remove(path)
                deleted += 1
            except Exception as e:
                print(f"[Agente] Error eliminando {path}: {e}")

    await database.execute(
        "UPDATE attendance_logs SET photo_path = NULL WHERE timestamp < :cutoff",
        {"cutoff": cutoff}
    )

    logger.info("[Agente] Limpieza completada. %d fotos eliminadas del disco.", deleted)


# ─── Push Notifications (multi-tenant) ───────────────────────────────────────


async def check_upcoming_shifts():
    today = date.today()
    weekday = today.weekday() + 1
    now = datetime.now(TZ)
    now_naive = now.replace(tzinfo=None)

    # Lógica 1: Próximos a entrar (10-15 min) — multi-tenant
    start_time_lower = (now + timedelta(minutes=10)).time()
    start_time_upper = (now + timedelta(minutes=15)).time()

    companies = await database.fetch_all("SELECT id FROM companies WHERE active = true")

    for company in companies:
        cid = str(company["id"])

        scheduled = await database.fetch_all(
            """
            SELECT e.id, e.name, e.expo_push_token, s.start_time
            FROM employees e
            JOIN schedules s ON e.id = s.employee_id
            WHERE e.active = true AND e.company_id = :cid
              AND :day = ANY(s.day_of_week) AND e.expo_push_token IS NOT NULL
              AND s.start_time >= :start_lower AND s.start_time <= :start_upper
            """,
            {"cid": cid, "day": weekday, "start_lower": start_time_lower, "start_upper": start_time_upper}
        )

        from rules_engine import ensure_time
        for emp in scheduled:
            check_in = await database.fetch_one(
                "SELECT id FROM attendance_logs WHERE employee_id = :eid AND company_id = :cid AND type = 'check_in' AND DATE(timestamp) = :today",
                {"eid": str(emp["id"]), "cid": cid, "today": today}
            )
            if not check_in:
                s_time = ensure_time(emp["start_time"])
                time_str = s_time.strftime('%H:%M') if s_time else str(emp["start_time"])
                await send_push_notification(
                    to=emp["expo_push_token"],
                    title="⏰ ¡Tu turno comienza pronto!",
                    body=f"Hola {emp['name']}, recuerda registrar tu entrada a las {time_str}."
                )

    # Lógica 2: Retorno de almuerzo (55 a 60 min desde break_start) — multi-tenant
    for company in companies:
        cid = str(company["id"])

        break_starts = await database.fetch_all(
            """
            SELECT l.employee_id, l.timestamp, e.name, e.expo_push_token
            FROM attendance_logs l
            JOIN employees e ON l.employee_id = e.id
            WHERE l.type = 'break_start' AND l.company_id = :cid
              AND DATE(l.timestamp) = :today AND e.expo_push_token IS NOT NULL
            """,
            {"cid": cid, "today": today}
        )

        for log in break_starts:
            break_end = await database.fetch_one(
                "SELECT id FROM attendance_logs WHERE employee_id = :eid AND company_id = :cid AND type = 'break_end' AND timestamp > :break_start",
                {"eid": log["employee_id"], "cid": cid, "break_start": log["timestamp"]}
            )
            if not break_end:
                elapsed = (now_naive - log["timestamp"]).total_seconds() / 60
                if 55 <= elapsed < (55 + 5):  # Window defined by BREAK_REMINDER_WINDOW_START setting
                    await send_push_notification(
                        to=log["expo_push_token"],
                        title="\U0001f96a \u00a1Se termina tu almuerzo!",
                        body=f"Hola {log['name']}, tu hora de almuerzo termina en unos minutos. \u00a1No olvides marcar tu regreso!"
                    )


# ─── Scheduler setup ─────────────────────────────────────────────────────────

def start_scheduler():
    scheduler.add_job(check_daily_absences, CronTrigger(hour=10, minute=0, timezone=TZ))
    scheduler.add_job(generate_monthly_report, CronTrigger(day=1, hour=0, minute=5, timezone=TZ))
    scheduler.add_job(cleanup_old_photos, CronTrigger(hour=3, minute=0, timezone=TZ))
    scheduler.add_job(check_upcoming_shifts, CronTrigger(minute='*/5', timezone=TZ))

    # Company lifecycle processing (every hour)
    from company_lifecycle import process_lifecycle_events
    scheduler.add_job(process_lifecycle_events, CronTrigger(minute=0, timezone=TZ))

    # MercadoPago token refresh (every 5 hours, before 6h expiry)
    try:
        from mp_oauth import scheduled_token_refresh
        scheduler.add_job(scheduled_token_refresh, CronTrigger(hour='*/5', timezone=TZ))
    except ImportError:
        pass

    scheduler.start()
    logger.info("Agente Controlador (Scheduler) multi-tenant iniciado.")
