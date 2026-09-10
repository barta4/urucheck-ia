import pytest
import os
import sys
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from datetime import time
from typing import List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the translation dict and handler from main without loading heavy optional routers
from main import FIELD_TRANSLATIONS_ES, validation_exception_handler

app_for_testing = FastAPI()
app_for_testing.add_exception_handler(RequestValidationError, validation_exception_handler)

class DummySchedulePayload(BaseModel):
    start_time: time
    end_time: time
    day_of_week: List[int]
    tolerance_minutes: Optional[int] = 5

@app_for_testing.post("/test-schedule")
def dummy_endpoint(payload: DummySchedulePayload):
    return {"status": "ok"}

client = TestClient(app_for_testing)

def test_validation_error_handler_spanish_translation():
    """
    Ensure missing required fields trigger 422 with readable Spanish detail.
    """
    response = client.post("/test-schedule", json={})
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    # Must be a readable string, not a raw list of technical dicts
    assert isinstance(data["detail"], str)
    assert "Hora de entrada" in data["detail"]
    assert "Hora de salida" in data["detail"]
    assert "Días de la semana" in data["detail"]
    assert "obligatorio" in data["detail"]

def test_validation_error_time_format():
    """
    Ensure malformed time values provide friendly Spanish time format advice.
    """
    response = client.post("/test-schedule", json={
        "start_time": "invalid-time",
        "end_time": "18:00",
        "day_of_week": [1]
    })
    assert response.status_code == 422
    data = response.json()
    assert isinstance(data["detail"], str)
    assert "Hora de entrada" in data["detail"]
    assert "formato de hora válido" in data["detail"]
