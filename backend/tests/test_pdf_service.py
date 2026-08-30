import pytest
from pdf_service import generate_attendance_pdf

def test_generate_attendance_pdf():
    company_name = "Empresa Demo S.A."
    month_str = "2026-08"
    report_data = [
        {
            "employee_name": "Juan Perez",
            "email": "juan@demo.com",
            "streak_achieved": 22,
            "bonus_earned": True
        },
        {
            "employee_name": "Maria Lopez",
            "email": "maria@demo.com",
            "streak_achieved": 15,
            "bonus_earned": False
        }
    ]

    pdf_bytes = generate_attendance_pdf(company_name, month_str, report_data)
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")
