"""
Face verification service.
Supports two providers:
  1. face_recognition (dlib-based, fast, local) — default
  2. gemini_vision (Google Gemini API, non-blocking multimodal verification)
"""
import os
import json
import re
import asyncio
import logging
from typing import Optional, Tuple
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

# ─── Pillow Image Helper ──────────────────────────────────────────────────────
try:
    from PIL import Image, ImageOps
    _pillow_available = True
except ImportError:
    _pillow_available = False


def _load_and_normalize_image(image_path: str):
    """
    Safely load an image with Pillow, apply EXIF orientation transpose,
    and convert to RGB. Returns PIL.Image or None on failure.
    """
    if not _pillow_available or not os.path.exists(image_path):
        return None
    try:
        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        return img
    except Exception as e:
        logger.warning("[face_service] Error al cargar/normalizar imagen %s: %s", image_path, e)
        return None


# ─── Provider 1: face_recognition (local, dlib) ──────────────────────────────
_face_recognition_available = False
try:
    import face_recognition
    import numpy as np
    _face_recognition_available = True
except ImportError:
    pass


def _encode_face_local(image_path: str) -> Optional["np.ndarray"]:
    """Return 128-d embedding or None if no face detected."""
    if not _face_recognition_available:
        return None
    try:
        image = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(image)
        if encodings:
            return encodings[0]
    except Exception as e:
        logger.warning("[face_service] Local encode error: %s", e)
    return None


def _verify_local(selfie_path: str, reference_path: str, threshold: float = 0.6) -> Tuple[bool, float]:
    """
    Compare two face images using dlib. Returns (is_same_person, confidence_distance).
    Lower distance = more similar. Default threshold 0.6 (dlib recommendation).
    """
    enc_selfie = _encode_face_local(selfie_path)
    enc_ref = _encode_face_local(reference_path)

    if enc_selfie is None or enc_ref is None:
        return False, -1.0

    distance = float(face_recognition.face_distance([enc_ref], enc_selfie)[0])
    is_match = distance <= threshold
    return is_match, distance


# ─── Provider 2: Gemini Vision (cloud async) ──────────────────────────────────
_gemini_available = False
genai = None
try:
    import google.generativeai as genai
    _gemini_available = True
except ImportError:
    pass


def _parse_gemini_json_response(raw_text: str) -> dict:
    """
    Defensively extract and parse JSON from Gemini's response text.
    Handles pure JSON, markdown blocks, and leading/trailing chatter.
    """
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: search for first { ... } block
        match = re.search(r"\{.*?\}", raw_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    logger.warning("[face_service] Fallo al parsear JSON de Gemini: %s", raw_text)
    return {}


async def _verify_gemini(selfie_path: str, reference_path: str) -> Tuple[bool, float]:
    """
    Asynchronously use Gemini Vision to compare selfie and reference images.
    Non-blocking, with strict JSON output and Pillow image normalization.
    Returns (is_same_person, confidence 0.0-1.0).
    """
    if not _gemini_available or not settings.GEMINI_API_KEY:
        logger.warning("[face_service] Gemini no disponible o GEMINI_API_KEY no configurada.")
        return False, 0.0

    img_selfie = _load_and_normalize_image(selfie_path)
    img_ref = _load_and_normalize_image(reference_path)

    if img_selfie is None or img_ref is None:
        logger.warning("[face_service] No se pudieron cargar las imágenes para Gemini.")
        return False, 0.0

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            "gemini-2.0-flash",
            generation_config={"response_mime_type": "application/json"}
        )

        prompt = (
            "You are an expert biometric verification assistant. "
            "Compare the two provided face images. "
            "Determine if they depict the EXACT SAME person. "
            "Output a single valid JSON object in this format: "
            '{"same_person": true, "confidence": 0.95} '
            "where 'same_person' is a boolean and 'confidence' is a float between 0.0 and 1.0."
        )

        # Non-blocking async API call with timeout
        response = await asyncio.wait_for(
            model.generate_content_async([prompt, img_selfie, img_ref]),
            timeout=8.0
        )
        data = _parse_gemini_json_response(response.text)

        is_same = bool(data.get("same_person", False))
        confidence = float(data.get("confidence", 0.0))
        return is_same, max(0.0, min(1.0, confidence))

    except asyncio.TimeoutError:
        logger.error("[face_service] Timeout (8s) en verificación facial de Gemini.")
        return False, 0.0
    except Exception as e:
        logger.error("[face_service] Error en verificación facial de Gemini: %s", e)
        return False, 0.0


async def _detect_face_gemini(image_path: str) -> bool:
    """
    Use Gemini Vision to check if an image contains a clear human face.
    Used when validating reference photos in employee registration.
    """
    if not _gemini_available or not settings.GEMINI_API_KEY:
        return True  # Fallback gracefully if API not ready

    img = _load_and_normalize_image(image_path)
    if img is None:
        return False

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            "gemini-2.0-flash",
            generation_config={"response_mime_type": "application/json"}
        )

        prompt = (
            "Determine if this image clearly contains a human face suitable as a biometric reference photo. "
            "Output JSON: {\"has_face\": true} or {\"has_face\": false}."
        )

        response = await asyncio.wait_for(
            model.generate_content_async([prompt, img]),
            timeout=5.0
        )
        data = _parse_gemini_json_response(response.text)
        return bool(data.get("has_face", True))
    except Exception as e:
        logger.warning("[face_service] Error en _detect_face_gemini: %s. Aceptando imagen por fallback.", e)
        return True


# ─── Public API ───────────────────────────────────────────────────────────────

async def verify_face(
    selfie_path: str,
    reference_path: str,
    provider: str = "face_recognition",
    threshold: float = 0.6
) -> dict:
    """
    Main verification function.
    Returns dict with:
      - verified: bool
      - confidence: float
      - provider_used: str
      - error: str | None
    """
    if not os.path.exists(reference_path):
        return {
            "verified": False,
            "confidence": 0.0,
            "provider_used": provider,
            "error": "Foto de referencia no encontrada en el sistema."
        }

    # 1. Local provider (face_recognition / dlib)
    if provider == "face_recognition" and _face_recognition_available:
        is_match, distance = _verify_local(selfie_path, reference_path, threshold)
        if distance < 0:
            return {
                "verified": False,
                "confidence": 0.0,
                "provider_used": "face_recognition",
                "error": "No se detectó un rostro claro en la selfie tomada. Mejora la iluminación y enfoca de frente."
            }
        confidence = max(0.0, min(1.0, 1.0 - distance))
        return {
            "verified": is_match,
            "confidence": round(confidence, 3),
            "provider_used": "face_recognition",
            "error": None if is_match else "No se pudo verificar tu identidad con el rostro registrado. Intenta con mejor iluminación."
        }

    # 2. Cloud provider (Gemini Vision)
    if provider == "gemini_vision" or not _face_recognition_available:
        min_confidence = threshold if (threshold and 0.0 < threshold <= 1.0) else 0.70
        is_same, confidence = await _verify_gemini(selfie_path, reference_path)

        if is_same and confidence >= min_confidence:
            return {
                "verified": True,
                "confidence": round(confidence, 3),
                "provider_used": "gemini_vision",
                "error": None
            }
        elif is_same and confidence < min_confidence:
            pct = int(round(confidence * 100))
            return {
                "verified": False,
                "confidence": round(confidence, 3),
                "provider_used": "gemini_vision",
                "error": f"Nivel de coincidencia insuficiente ({pct}%). Toma la foto de frente y con buena iluminación."
            }
        else:
            return {
                "verified": False,
                "confidence": round(confidence, 3),
                "provider_used": "gemini_vision",
                "error": "No se pudo verificar tu identidad con el rostro registrado. Intenta con mejor iluminación."
            }

    return {
        "verified": False,
        "confidence": 0.0,
        "provider_used": provider,
        "error": "Proveedor de verificación facial no disponible."
    }


async def has_face_reference(reference_path: str, provider: str = "face_recognition") -> bool:
    """Check if the reference image contains a detectable face."""
    if not reference_path or not os.path.exists(reference_path):
        return False

    if provider == "face_recognition" and _face_recognition_available:
        enc = _encode_face_local(reference_path)
        return enc is not None

    if provider == "gemini_vision":
        return await _detect_face_gemini(reference_path)

    return True
