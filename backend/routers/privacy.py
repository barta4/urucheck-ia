"""
Privacy, legal compliance, and data rights endpoints.
Complies with Uruguayan Law 18.331 (Personal Data Protection) + Law 19.924.
"""
import os
import json
import csv
import io
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from auth import get_current_user
from database import database
from config import settings

router = APIRouter(prefix="/api/privacy", tags=["privacy"])


# ─── Legal content (served from backend so it's single source of truth) ───────

@router.get("/privacy-policy")
async def get_privacy_policy():
    """Full privacy policy text — complies with Law 18.331 Art. 6 (right to information)"""
    return {
        "version": "2.0",
        "last_updated": "2025-04-05",
        "jurisdiction": "Uruguay — Ley 18.331 / Ley 19.924",
        "data_controller": "Tu empresa (empleador)",
        "sections": [
            {
                "title": "1. Responsable del tratamiento",
                "content": (
                    "El responsable del tratamiento de tus datos personales es tu empleador, "
                    "quien ha registrado la base de datos ante la Unidad Reguladora y de Control "
                    "de Datos Personales (URCDP) de Uruguay, conforme a la Ley 18.331 y el Decreto "
                    "Reglamentario 364/010. Si tienes dudas, contacta al administrador de tu empresa."
                )
            },
            {
                "title": "2. Datos que recopilamos",
                "content": (
                    "Para el registro de asistencia, el sistema recopila:\n"
                    "• Datos biométricos faciales: una fotografía (selfie) al momento de marcar "
                    "asistencia, utilizada para verificar tu identidad mediante reconocimiento facial.\n"
                    "• Datos de geolocalización: coordenadas GPS (latitud, longitud y precisión) "
                    "al momento del registro.\n"
                    "• Datos de asistencia: fecha, hora, tipo de registro (entrada, salida, descanso), "
                    "y estado (puntual, tarde).\n"
                    "• Datos de racha (streak): conteo de días consecutivos de puntualidad para "
                    "el cálculo de bonos."
                )
            },
            {
                "title": "3. Base legal del tratamiento",
                "content": (
                    "El tratamiento de tus datos personales, incluidos los datos biométricos "
                    "(categoría de datos sensibles según Art. 4 de la Ley 18.331), se fundamenta en:\n"
                    "• La ejecución del contrato de trabajo y las obligaciones laborales.\n"
                    "• El interés legítimo del empleador en verificar la asistencia del personal.\n"
                    "• Tu consentimiento libre, informado e inequívoco para el tratamiento de datos biométricos.\n"
                    "La Ley 18.331 Art. 18 BIS requiere una Evaluación de Impacto previa al tratamiento "
                    "de datos biométricos, la cual ha sido realizada por tu empleador."
                )
            },
            {
                "title": "4. Finalidad del tratamiento",
                "content": (
                    "Tus datos se utilizan exclusivamente para:\n"
                    "• Verificar tu identidad al momento de marcar asistencia.\n"
                    "• Controlar y registrar tu jornada laboral (entradas, salidas, descansos).\n"
                    "• Calcular tu racha de puntualidad y bonificaciones asociadas.\n"
                    "• Generar reportes de asistencia para el área de Recursos Humanos.\n"
                    "• Enviar notificaciones automatizadas vía webhook (si están configuradas)."
                )
            },
            {
                "title": "5. Lo que NO hacemos",
                "content": (
                    "✗ No rastreamos tu ubicación en segundo plano.\n"
                    "✗ No accedemos a tu cámara fuera del momento de marcación.\n"
                    "✗ No compartimos tus datos con terceros no autorizados.\n"
                    "✗ No vendemos ni cedemos tu información personal.\n"
                    "✗ No utilizamos tus datos biométricos para fines distintos al control de asistencia.\n"
                    "✗ No almacenamos embeddings faciales en formato identificable fuera del servidor seguro."
                )
            },
            {
                "title": "6. Permisos requeridos",
                "content": (
                    "La aplicación solicita acceso a:\n"
                    "• Cámara: para capturar tu fotografía durante la marcación. Se usa solo "
                    "cuando activamente presionas el botón de registro.\n"
                    "• Ubicación (GPS): para verificar que te encuentras en el lugar de trabajo "
                    "asignado (geocerca). Se consulta solo al momento de marcar.\n\n"
                    "Puedes revocar estos permisos en la configuración de tu teléfono en cualquier "
                    "momento. Sin embargo, esto impedirá el funcionamiento de la marcación de asistencia."
                )
            },
            {
                "title": "7. Almacenamiento y seguridad",
                "content": (
                    "• Todos los datos se transmiten mediante HTTPS (conexión cifrada).\n"
                    "• Las fotografías se almacenan en servidores seguros de tu empresa.\n"
                    "• La foto de referencia facial se guarda como un embedding matemático (vector "
                    "de 128 dimensiones), no como imagen identificable.\n"
                    "• Los registros de asistencia se conservan según la política de retención de "
                    "tu empresa (por defecto: 2 años).\n"
                    "• Las fotografías de verificación se eliminan automáticamente después de 90 días."
                )
            },
            {
                "title": "8. Plazo de conservación de datos",
                "content": (
                    "• Fotografías de verificación (selfies): 90 días desde la captura.\n"
                    "• Foto de referencia facial: mientras dure la relación laboral + 30 días tras "
                    "la finalización.\n"
                    "• Registros de asistencia (logs): 2 años (cumplimiento de obligaciones laborales).\n"
                    "• Datos de racha y bonos: duración del mes en curso + 1 año para auditoría.\n"
                    "Tras estos plazos, los datos se eliminan o anonimizan de forma irreversible."
                )
            },
            {
                "title": "9. Tus derechos (ARCO+)",
                "content": (
                    "Conforme a la Ley 18.331, tienes derecho a:\n"
                    "• Acceso: solicitar una copia de todos tus datos personales almacenados.\n"
                    "• Rectificación: corregir datos inexactos o incompletos.\n"
                    "• Cancelación (supresión): solicitar la eliminación de tus datos biométricos "
                    "y registros de asistencia (sujeto a obligaciones legales de conservación).\n"
                    "• Oposición: oponerte al tratamiento de tus datos para fines específicos.\n"
                    "• Revocación del consentimiento: retirar tu consentimiento para el uso de "
                    "datos biométricos (esto puede implicar el uso de un método alternativo de "
                    "registro de asistencia).\n\n"
                    "Para ejercer estos derechos, usa la sección 'Mis Datos' en la app o contacta "
                    "al administrador de tu empresa."
                )
            },
            {
                "title": "10. Transferencia internacional de datos",
                "content": (
                    "En caso de que se utilice Google Gemini Vision como proveedor alternativo "
                    "de verificación facial, las imágenes podrían procesarse en servidores de Google "
                    "ubicados fuera de Uruguay. Este proveedor cumple con estándares internacionales "
                    "de protección de datos. Puedes optar por el proveedor local (face_recognition) "
                    "si así lo prefieres, consultando a tu administrador."
                )
            },
            {
                "title": "11. Notificación de brechas de seguridad",
                "content": (
                    "En caso de una violación de seguridad que comprometa tus datos personales, "
                    "tu empleador notificará a la URCDP dentro de las 72 horas siguientes, conforme "
                    "a la normativa uruguaya. Si la brecha implica un alto riesgo para tus derechos, "
                    "se te notificará de forma individual."
                )
            },
            {
                "title": "12. Contacto",
                "content": (
                    "Para consultas sobre tus datos personales, ejercer tus derechos ARCO+, o "
                    "presentar una reclamación:\n"
                    "• Contacta al administrador de tu empresa desde el panel de administración.\n"
                    "• URCDP (Unidad Reguladora y de Control de Datos Personales): "
                    "https://www.gub.uy/unidad-reguladora-control-datos-personales/"
                )
            }
        ]
    }


@router.get("/legal-notice")
async def get_legal_notice():
    """Legal notice about biometric data processing — for URCDP compliance"""
    return {
        "title": "Aviso Legal — Tratamiento de Datos Biométricos",
        "jurisdiction": "República Oriental del Uruguay",
        "applicable_laws": [
            "Ley 18.331 — Protección de Datos Personales",
            "Decreto 364/010 — Reglamentario de la Ley 18.331",
            "Ley 19.924 — Presupuesto Nacional (Art. 86, modificatoria sobre datos biométricos)",
        ],
        "biometric_data_classification": "Datos sensibles (Art. 4, Ley 18.331)",
        "dpia_completed": True,
        "urcdp_registration_required": True,
        "data_categories": [
            "Identificación facial (selfie de verificación)",
            "Embedding facial (vector de 128 dimensiones)",
            "Geolocalización GPS en el momento del registro",
            "Registros de asistencia (fecha, hora, tipo, estado)",
        ],
        "retention_summary": {
            "verification_photos": "90 días",
            "face_reference_photo": "Relación laboral + 30 días",
            "attendance_logs": "2 años",
            "streak_bonus_data": "Mes en curso + 1 año",
        },
        "rights": "Acceso, Rectificación, Cancelación, Oposición, Revocación (ARCO+)",
        "contact": "Administrador de la empresa / URCDP: https://www.gub.uy/unidad-reguladora-control-datos-personales/"
    }
