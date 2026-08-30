import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import google.generativeai as genai
from datetime import date, datetime
from auth import get_current_admin
from database import database
from config import settings
from zoneinfo import ZoneInfo
from collections import defaultdict

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatRequest(BaseModel):
    message: str

def init_gemini():
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise HTTPException(status_code=500, detail="Gemini API Key no configurada en el servidor.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.0-flash")

async def get_system_context(company_id: str) -> str:
    """Fetches real-time attendance data for a specific company"""
    tz = ZoneInfo(settings.TIMEZONE)
    now_tz = datetime.now(tz)
    today = now_tz.date()
    weekday = today.weekday() + 1
    now = now_tz.time()

    scheduled = await database.fetch_all(
        """
        SELECT e.id, e.name, s.start_time
        FROM employees e
        JOIN schedules s ON e.id = s.employee_id
        WHERE e.active = true AND e.company_id = :cid AND :day = ANY(s.day_of_week)
        """,
        {"cid": company_id, "day": weekday}
    )

    logs = await database.fetch_all(
        """
        SELECT al.employee_id, al.type, al.status, al.timestamp
        FROM attendance_logs al
        WHERE al.company_id = :cid AND DATE(al.timestamp) = :today
        ORDER BY al.timestamp ASC
        """,
        {"cid": company_id, "today": today}
    )

    history_by_emp = defaultdict(list)
    for log in logs:
        history_by_emp[str(log["employee_id"])].append(dict(log))

    context_lines = [
        f"Eres un asistente virtual experto para el panel de administración de una empresa.",
        f"ESTADO LOCAL: Hoy es {today.isoformat()} y en este exacto momento son las {now.strftime('%H:%M:%S')} (Zona horaria: {settings.TIMEZONE}).",
        "Tu trabajo principal es ayudar al jefe/administrador respondiendo preguntas concisas sobre la asistencia del personal del día de hoy.",
        "Responde de forma profesional, clara y directa.",
        "\n--- HISTORIAL DE MOVIMIENTOS HOY ---"
    ]

    if not scheduled:
        context_lines.append("Nadie tiene horario asignado para trabajar hoy según la base de datos.")
    else:
        from rules_engine import ensure_time
        for emp in scheduled:
            eid = str(emp["id"])
            name = emp["name"]
            scheduled_time = ensure_time(emp["start_time"]) or emp["start_time"]
            history = history_by_emp.get(eid)

            if not history:
                if isinstance(scheduled_time, str):
                    # fallback comparison or parsing in case ensure_time failed to parse
                    s_time = ensure_time(scheduled_time)
                else:
                    s_time = scheduled_time

                if s_time and now > s_time:
                    context_lines.append(f"- {name}: Tenía que entrar a las {scheduled_time}. Faltó (Ausente).")
                else:
                    context_lines.append(f"- {name}: Entra a las {scheduled_time} (Pendiente de llegar).")
                continue

            context_lines.append(f"- {name} (Entrada oficial: {scheduled_time}):")
            for record in history:
                time_str = record["timestamp"].strftime("%H:%M:%S")
                r_type = record["type"]
                r_status = record["status"]

                if r_type == 'check_in':
                    status_text = "A TIEMPO" if r_status == "on_time" else "CON RETRASO"
                    context_lines.append(f"   > {time_str}: Ingresó a trabajar ({status_text})")
                elif r_type == 'break_start':
                    context_lines.append(f"   > {time_str}: Salió al descanso / a comer")
                elif r_type == 'break_end':
                    context_lines.append(f"   > {time_str}: Regresó del descanso")
                elif r_type == 'check_out':
                    context_lines.append(f"   > {time_str}: Se fue (Terminó su jornada)")

    context_lines.append("----------------------------\n")
    return "\n".join(context_lines)

@router.post("/")
async def chat_with_ai(req: ChatRequest, admin=Depends(get_current_admin)):
    # Check feature access
    from resource_limiter import check_feature_access
    await check_feature_access(admin["company_id"], "ai_chat")

    try:
        model = init_gemini()
        company_id = admin["company_id"]
        context = await get_system_context(company_id)

        full_prompt = f"{context}\nPregunta del administrador: {req.message}\nRespuesta:"

        response = model.generate_content(full_prompt)
        return {"reply": response.text}

    except Exception as e:
        print(f"Error en Gemini Chat: {e}")
        raise HTTPException(status_code=500, detail="Error de comunicación con IA")
