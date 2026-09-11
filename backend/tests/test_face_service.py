import pytest
import sys
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from face_service import (
    verify_face,
    has_face_reference,
    _parse_gemini_json_response,
    _load_and_normalize_image
)


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.fixture
def dummy_images(tmp_path):
    img1_path = str(tmp_path / "selfie.jpg")
    img2_path = str(tmp_path / "ref.jpg")

    img = Image.new("RGB", (100, 100), color="blue")
    img.save(img1_path)
    img.save(img2_path)

    return img1_path, img2_path


def test_parse_gemini_json_response():
    """Verify parsing handles clean JSON, markdown backticks, and conversational text."""
    # 1. Pure JSON
    clean = '{"same_person": true, "confidence": 0.95}'
    assert _parse_gemini_json_response(clean) == {"same_person": True, "confidence": 0.95}

    # 2. Markdown wrapped
    md = '```json\n{"same_person": false, "confidence": 0.2}\n```'
    assert _parse_gemini_json_response(md) == {"same_person": False, "confidence": 0.2}

    # 3. Conversational preamble & postamble
    chatter = 'Here is the result:\n{"same_person": true, "confidence": 0.88}\nHope this helps.'
    assert _parse_gemini_json_response(chatter) == {"same_person": True, "confidence": 0.88}

    # 4. Malformed
    assert _parse_gemini_json_response("This is not json") == {}


def test_load_and_normalize_image(dummy_images):
    """Verify Pillow loader handles valid and non-existent files."""
    img1, _ = dummy_images
    loaded = _load_and_normalize_image(img1)
    assert loaded is not None
    assert loaded.mode == "RGB"

    assert _load_and_normalize_image("/non/existent/path.jpg") is None


@pytest.mark.anyio
async def test_verify_face_missing_reference(tmp_path):
    """Verify error when reference photo does not exist."""
    selfie = str(tmp_path / "selfie.jpg")
    ref = str(tmp_path / "missing_ref.jpg")
    Image.new("RGB", (50, 50)).save(selfie)

    res = await verify_face(selfie, ref, provider="gemini_vision")
    assert res["verified"] is False
    assert "no encontrada" in res["error"].lower()


@pytest.mark.anyio
async def test_verify_face_gemini_success(dummy_images):
    """Verify successful verification with high confidence."""
    img1, img2 = dummy_images

    mock_response = MagicMock()
    mock_response.text = '{"same_person": true, "confidence": 0.96}'

    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    mock_genai = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model

    with patch("face_service._gemini_available", True), \
         patch("face_service.genai", mock_genai), \
         patch("face_service.settings.GEMINI_API_KEY", "test-key"):

        res = await verify_face(img1, img2, provider="gemini_vision", threshold=0.7)
        assert res["verified"] is True
        assert res["confidence"] == 0.96
        assert res["error"] is None
        assert res["provider_used"] == "gemini_vision"


@pytest.mark.anyio
async def test_verify_face_gemini_low_confidence(dummy_images):
    """Verify failure when same_person is true but confidence is below threshold."""
    img1, img2 = dummy_images

    mock_response = MagicMock()
    mock_response.text = '{"same_person": true, "confidence": 0.58}'

    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    mock_genai = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model

    with patch("face_service._gemini_available", True), \
         patch("face_service.genai", mock_genai), \
         patch("face_service.settings.GEMINI_API_KEY", "test-key"):

        res = await verify_face(img1, img2, provider="gemini_vision", threshold=0.7)
        assert res["verified"] is False
        assert res["confidence"] == 0.58
        assert res["error"] is not None
        assert "58%" in res["error"]


@pytest.mark.anyio
async def test_verify_face_gemini_different_person(dummy_images):
    """Verify failure when faces do not match."""
    img1, img2 = dummy_images

    mock_response = MagicMock()
    mock_response.text = '{"same_person": false, "confidence": 0.15}'

    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    mock_genai = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model

    with patch("face_service._gemini_available", True), \
         patch("face_service.genai", mock_genai), \
         patch("face_service.settings.GEMINI_API_KEY", "test-key"):

        res = await verify_face(img1, img2, provider="gemini_vision", threshold=0.7)
        assert res["verified"] is False
        assert res["confidence"] == 0.15
        assert res["error"] is not None
        assert "no se pudo verificar" in res["error"].lower()


@pytest.mark.anyio
async def test_verify_face_gemini_timeout(dummy_images):
    """Verify timeout does not crash and returns friendly error."""
    img1, img2 = dummy_images

    mock_genai = MagicMock()

    with patch("face_service._gemini_available", True), \
         patch("face_service.genai", mock_genai), \
         patch("face_service.settings.GEMINI_API_KEY", "test-key"), \
         patch("face_service.asyncio.wait_for", side_effect=asyncio.TimeoutError):

        res = await verify_face(img1, img2, provider="gemini_vision")
        assert res["verified"] is False
        assert res["confidence"] == 0.0
        assert res["error"] is not None
        assert "no se pudo verificar" in res["error"].lower()


@pytest.mark.anyio
async def test_has_face_reference_gemini(dummy_images):
    """Verify face detection in reference photo during employee registration."""
    _, ref_path = dummy_images

    # 1. Face detected
    mock_resp_true = MagicMock(text='{"has_face": true}')
    mock_model_true = MagicMock()
    mock_model_true.generate_content_async = AsyncMock(return_value=mock_resp_true)

    mock_genai = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model_true

    with patch("face_service._gemini_available", True), \
         patch("face_service.genai", mock_genai), \
         patch("face_service.settings.GEMINI_API_KEY", "test-key"):

        has_face = await has_face_reference(ref_path, provider="gemini_vision")
        assert has_face is True

    # 2. No face detected
    mock_resp_false = MagicMock(text='{"has_face": false}')
    mock_model_false = MagicMock()
    mock_model_false.generate_content_async = AsyncMock(return_value=mock_resp_false)
    mock_genai.GenerativeModel.return_value = mock_model_false

    with patch("face_service._gemini_available", True), \
         patch("face_service.genai", mock_genai), \
         patch("face_service.settings.GEMINI_API_KEY", "test-key"):

        has_face = await has_face_reference(ref_path, provider="gemini_vision")
        assert has_face is False
