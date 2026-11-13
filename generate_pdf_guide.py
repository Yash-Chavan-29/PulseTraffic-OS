import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

def generate_pdf(output_path="Y:\\Hackothon\\SmartRoute_Presentation_Guide.pdf"):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    c_primary = colors.HexColor("#0f172a")
    c_accent = colors.HexColor("#2563eb")
    c_card_bg = colors.HexColor("#f8fafc")
    c_border = colors.HexColor("#cbd5e1")

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=c_primary,
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=c_accent,
        spaceAfter=10
    )

    h1_style = ParagraphStyle(
        'H1',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=c_primary,
        spaceBefore=10,
        spaceAfter=5
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155")
    )

    table_header = ParagraphStyle(
        'TableHeader',
        parent=body_style,
        fontName='Helvetica-Bold',
        textColor=colors.white,
        fontSize=8.5
    )

    elements = []

    # Title & Header
    elements.append(Paragraph("SmartRoutes — Intelligent Traffic Management &amp; Route Optimization", title_style))
    elements.append(Paragraph("Domain 1: Full Stack Web Development (PS 01) | Live Localhost: http://localhost:5000", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=c_accent, spaceBefore=2, spaceAfter=8))

    # Executive Summary
    summary_text = (
        "<b>Executive Summary for Judges:</b> SmartRoutes satisfies all core deliverables of Problem Statement 01: "
        "allowing users to input source and destination (with current location locked by default inside a <b>500m blue accuracy radius</b>), "
        "calculating and displaying <b>2 to 3 route options</b> with the fastest in <b>Solid Blue</b> and alternatives in <b>Yellow</b>, "
        "comparing shortest vs. fastest distance and travel time (in hours &amp; minutes), "
        "displaying <b>persistent live road incidents</b> at all times, "
        "providing a <b>citizen incident reporting modal</b> with automatic alternate route diversions, and "
        "offering a <b>dual-dashboard architecture</b> with a secure <b>Administration portal</b> requiring login to review and moderate incidents."
    )
    summary_table = Table([[Paragraph(summary_text, body_style)]], colWidths=[532])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#bfdbfe")),
        ('PADDING', (0, 0), (-1, -1), 7),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 8))

    # Problem Statement Core Features Table
    elements.append(Paragraph("Core Feature Implementation Checklist", h1_style))

    features_data = [
        [
            Paragraph("Core Deliverable", table_header),
            Paragraph("System Implementation", table_header),
            Paragraph("Judge Demonstration Flow", table_header)
        ],
        [
            Paragraph("<b>500m Blue Accuracy Circle</b>", body_style),
            Paragraph("<code>L.circle([lat, lng], { radius: 500 })</code> rendered around GPS origin.", body_style),
            Paragraph("Visible immediately upon launch centered at Rani Chennamma Hub.", body_style)
        ],
        [
            Paragraph("<b>Source &amp; Destination Inputs</b>", body_style),
            Paragraph("Default origin auto-filled with current location; destination selectable via text or quick chips.", body_style),
            Paragraph("Type any city or click chips (Dharwad, Bagalkot, Hubballi, Airport) to trigger instant routing.", body_style)
        ],
        [
            Paragraph("<b>Single Fastest Route Display</b>", body_style),
            Paragraph("A* optimal route rendered in prominent <b>Solid Blue</b> with distance and travel time.", body_style),
            Paragraph("Shows distance in km and arrival time in hours/mins (e.g. 1h 14m) with optimal free flow.", body_style)
        ],
        [
            Paragraph("<b>Persistent Live Incidents</b>", body_style),
            Paragraph("Active roadblocks, accidents, and congestion permanently plotted on map at all times.", body_style),
            Paragraph("Clicking an incident marker zooms to the hazard and reveals details and severity.", body_style)
        ],
        [
            Paragraph("<b>Citizen Incident Reporting</b>", body_style),
            Paragraph("Modal allowing drivers to submit accidents, roadblocks, or congestion with instant diversion.", body_style),
            Paragraph("Click <b>⚠ Report Incident</b>, submit details, and watch the map reroute traffic immediately.", body_style)
        ],
        [
            Paragraph("<b>Dual Dashboard (Admin Login)</b>", body_style),
            Paragraph("<b>Client Dashboard</b> for public navigation; <b>Administration Dashboard</b> with login gate.", body_style),
            Paragraph("Click <b>🔒 Administration</b>, log in with <code>admin / admin123</code> to review and moderate reports.", body_style)
        ]
    ]

    feat_table = Table(features_data, colWidths=[130, 202, 200])
    feat_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_primary),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, c_border),
        ('PADDING', (0, 0), (-1, -1), 4.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_card_bg]),
    ]))
    elements.append(feat_table)
    elements.append(Spacer(1, 8))

    # Live Evaluation Walkthrough
    elements.append(Paragraph("1-Minute Judge Walkthrough Script", h1_style))
    demo_script = (
        "<b>1. Client Map:</b> Point out the 500m blue accuracy circle locked around your current location.<br/>"
        "<b>2. Fastest Route:</b> Click <b>Dharwad</b>. Show the <b>Fastest Route in Solid Blue</b> with exact distance and estimated travel time in hours and minutes.<br/>"
        "<b>3. Incident Reporting:</b> Click <b>⚠ Report Incident</b>, submit an accident report, and show judges how the system immediately flags the road with live markers.<br/>"
        "<b>4. Admin Portal:</b> Switch to <b>🔒 Administration</b>, sign in with <code>admin / admin123</code>, and show the moderation queue where administrators review, verify, or close roads in real time."
    )
    demo_table = Table([[Paragraph(demo_script, body_style)]], colWidths=[532])
    demo_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f0fdf4")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#bbf7d0")),
        ('PADDING', (0, 0), (-1, -1), 7),
    ]))
    elements.append(demo_table)

    doc.build(elements)
    print(f"PDF successfully generated at: {output_path}")

if __name__ == '__main__':
    generate_pdf()
