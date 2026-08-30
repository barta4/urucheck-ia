import pytest
from datetime import time, datetime
import math
import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rules_engine import ensure_time

def test_ensure_time_from_time_obj():
    t = time(8, 30, 0)
    assert ensure_time(t) == time(8, 30, 0)

def test_ensure_time_from_string():
    assert ensure_time("09:15:00") == time(9, 15, 0)
    assert ensure_time("09:15") == time(9, 15, 0)
    assert ensure_time("invalid") is None

def test_ensure_time_from_datetime():
    dt = datetime(2026, 8, 28, 14, 45, 30)
    assert ensure_time(dt) == time(14, 45, 30)

def test_ensure_time_none():
    assert ensure_time(None) is None

def test_haversine_distance_calculation():
    # Test geofence distance calculation logic
    lat1, lon1 = -34.901112, -56.164532 # Montevideo Point A
    lat2, lon2 = -34.901200, -56.164600 # Montevideo Point B (~12 meters away)
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    R = 6371000
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    dist = 2 * R * math.asin(math.sqrt(a))
    
    assert dist < 20.0 # Should be within 20 meters
