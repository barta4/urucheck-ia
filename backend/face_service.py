"""
Face verification service.
Supports two providers:
  1. face_recognition (dlib-based, fast, local) — default
  2. gemini_vision (Google Gemini API, slower fallback)
"""
import os
import base64
from typing import Optional, Tuple
from pathlib import Path

from config import settings

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
        print(f"[face_service] Local encode error: {e}")
    return None


def _verify_local(selfie_path: str, reference_path: str, threshold: float = 0.6) -> Tuple[bool, float]:
    """
    Compare two face images. Returns (is_same_person, confidence_distance).
    Lower distance = more similar. Default threshold 0.6 (dlib recommendation).
    """
    enc_selfie = _encode_face_local(selfie_path)
    enc_ref = _encode_face_local(reference_path)

    if enc_selfie is None or enc_ref is None:
        return False, -1.0  # No face detected in one or both images

    distance = float(face_recognition.face_distance([enc_ref], enc_selfie)[0])
    is_match = distance <= threshold
    return is_match, distance


# ─── Provider 2: Gemini Vision (cloud fallback) ──────────────────────────────

_gemini_available = False
try:
    import google.generativeai as genai
    _gemini_available = True
except ImportError:
    pass


def _verify_gemini(selfie_path: str, reference_path: str) -> Tuple[bool, float]:
    """
    Use Gemini Vision to check if both images show the same person.
    Returns (is_same_person, confidence 0-1).
    """
    if not _gemini_available or not settings.GEMINI_API_KEY:
        return False, 0.0

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")

        def _img_to_genai(path: str):
            with open(path, "rb") as f:
                data = f.read()
            return {"mime_type": "image/jpeg", "data": data}

        prompt = (
            "You are a biometric verification assistant. "
            "Compare the two images provided. "
            "Do they show the SAME person? "
            "Respond ONLY with a JSON object in this exact format: "
            '{"same_person": true, "confidence": 0.95} '
            "where confidence is a float between 0 and 1."
        )

        img1 = _img_to_genai(selfie_path)
        img2 = _img_to_genai(reference_path)

        response = model.generate_content([prompt, img1, img2])
        text = response.text.strip()

        # Parse JSON from response
        import json
        # Try to extract JSON from possible markdown formatting
        text = text.strip("```json").strip("```").strip()
        result = json.loads(text)

        is_same = result.get("same_person", False)
        confidence = float(result.get("confidence", 0.0))
        return is_same, confidence

    except Exception as e:
        print(f"[face_service] Gemini verify error: {e}")
        return False, 0.0


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
        return {"verified": False, "confidence": 0.0, "provider_used": provider,
                "error": "Foto de referencia no encontrada"}

    # Try primary provider
    if provider == "face_recognition" and _face_recognition_available:
        is_match, distance = _verify_local(selfie_path, reference_path, threshold)
        # Convert distance to confidence (lower distance = higher confidence)
        confidence = max(0.0, min(1.0, 1.0 - distance))
        return {
            "verified": is_match,
            "confidence": round(confidence, 3),
            "provider_used": "face_recognition",
            "error": None if is_match else "No se pudo verificar tu identidad. Mejora la iluminación e intenta de nuevo."
        }

    # Fallback to Gemini
    if provider == "gemini_vision" or not _face_recognition_available:
        is_same, confidence = _verify_gemini(selfie_path, reference_path)
        return {
            "verified": is_same and confidence >= 0.7,
            "confidence": round(confidence, 3),
            "provider_used": "gemini_vision",
            "error": None if is_same else "No se pudo verificar tu identidad. Mejora la iluminación e intenta de nuevo."
        }

    return {"verified": False, "confidence": 0.0, "provider_used": provider,
            "error": "Proveedor de verificación facial no disponible"}


async def has_face_reference(reference_path: str, provider: str = "face_recognition") -> bool:
    """Check if the reference image contains a detectable face."""
    if not reference_path or not os.path.exists(reference_path):
        return False

    if provider == "face_recognition" and _face_recognition_available:
        enc = _encode_face_local(reference_path)
        return enc is not None

    # If using gemini_vision or local is disabled/failed, assume true (Gemini will verify at check-in time)
    return True
