import io
import os
import qrcode
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from config import settings

def generate_attendance_pdf(company_name: str, month_str: str, report_data: list, verification_url: str = None) -> bytes:
    """
    Generates a professional attendance and bonus report in PDF format with company info,
    executive summary, detailed employee breakdown, and verification QR code.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1e293b'),
        fontName='Helvetica-Bold'
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#64748b'),
        fontName='Helvetica'
    )
    section_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#0f172a'),
        fontName='Helvetica-Bold',
        spaceBefore=12,
        spaceAfter=6
    )
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#334155')
    )
    cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=cell_style,
        fontName='Helvetica-Bold'
    )
    header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.white,
        fontName='Helvetica-Bold'
    )

    story = []

    # 1. Header (Company and Title)
    header_data = [
        [
            Paragraph(f"<b>{company_name}</b>", title_style),
            Paragraph(f"<b>Emisión:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}<br/><b>Período:</b> {month_str}", subtitle_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[340, 200])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))

    # Divider bar
    story.append(Paragraph(
        "<font color='#2563eb'><b>INFORME OFICIAL DE ASISTENCIA Y PUNTUALIDAD</b></font>",
        ParagraphStyle('MainBadge', fontSize=12, leading=16, fontName='Helvetica-Bold', textColor=colors.HexColor('#2563eb'))
    ))
    story.append(Spacer(1, 10))

    # 2. Executive Summary Metrics
    total_employees = len(report_data)
    bonus_earned_count = sum(1 for item in report_data if item.get('bonus_earned'))
    total_streak_sum = sum(item.get('streak_achieved', 0) for item in report_data)
    avg_streak = round(total_streak_sum / total_employees, 1) if total_employees > 0 else 0
    pct_bonus = round((bonus_earned_count / total_employees) * 100, 1) if total_employees > 0 else 0

    kpi_data = [
        [
            Paragraph("<b>Total Evaluados</b>", cell_bold),
            Paragraph("<b>Bonos Otorgados</b>", cell_bold),
            Paragraph("<b>Tasa Cumplimiento</b>", cell_bold),
            Paragraph("<b>Días Promedio</b>", cell_bold)
        ],
        [
            Paragraph(f"<font size=14><b>{total_employees}</b></font>", cell_style),
            Paragraph(f"<font size=14 color='#16a34a'><b>{bonus_earned_count}</b></font>", cell_style),
            Paragraph(f"<font size=14 color='#2563eb'><b>{pct_bonus}%</b></font>", cell_style),
            Paragraph(f"<font size=14><b>{avg_streak} días</b></font>", cell_style)
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[135, 135, 135, 135])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 15))

    # 3. Detailed Employees Table
    story.append(Paragraph("Desglose Individual por Empleado", section_style))

    table_rows = [
        [
            Paragraph("Empleado", header_style),
            Paragraph("Email", header_style),
            Paragraph("Días Cumplidos", header_style),
            Paragraph("Bono Puntualidad", header_style)
        ]
    ]

    for item in report_data:
        emp_name = item.get('employee_name') or 'N/A'
        emp_email = item.get('email') or '-'
        streak = item.get('streak_achieved', 0)
        earned = item.get('bonus_earned', False)

        bonus_label = "<font color='#16a34a'><b>SI (Aprobado)</b></font>" if earned else "<font color='#dc2626'>NO</font>"

        table_rows.append([
            Paragraph(emp_name, cell_bold),
            Paragraph(emp_email, cell_style),
            Paragraph(f"<b>{streak}</b> días", cell_style),
            Paragraph(bonus_label, cell_style)
        ])

    emp_table = Table(table_rows, colWidths=[170, 190, 90, 90])
    emp_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
    ]))
    story.append(emp_table)
    story.append(Spacer(1, 20))

    # 4. QR Code & Validation Footer
    base_url = settings.FRONTEND_URL.rstrip('/')
    qr_url = verification_url or f"{base_url}/verify?company={company_name}&period={month_str}"
    qr_img = qrcode.make(qr_url)
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    qr_rl_img = RLImage(qr_buffer, width=1.1*inch, height=1.1*inch)

    footer_data = [
        [
            qr_rl_img,
            Paragraph(
                f"<b>Validación Digital de Autenticidad:</b><br/>"
                f"<font size=7.5 color='#64748b'>Este documento es un registro oficial emitido por el sistema UruCheck IA SaaS Multi-Tenant. "
                f"La integridad de los datos de fichada y marcas biométricas se encuentra respaldada por firma criptográfica y registros de auditoría inmutables.<br/>"
                f"<b>Código de Verificación:</b> {os.urandom(6).hex().upper()}</font>",
                subtitle_style
            )
        ]
    ]
    footer_table = Table(footer_data, colWidths=[90, 450])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEABOVE', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
    ]))

    story.append(KeepTogether([footer_table]))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
