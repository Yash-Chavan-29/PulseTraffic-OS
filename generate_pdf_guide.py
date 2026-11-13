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
    elements.append(Paragraph("Smart Route — Belgaum Traffic Management System", title_style))
    elements.append(Paragraph("1-Click Adaptive Signal Optimization &amp; Emergency Corridor | http://localhost:5000", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=c_accent, spaceBefore=2, spaceAfter=8))

    # Executive Summary
    summary_text = (
        "<b>Executive Summary for Judges:</b> Smart Route is an autonomous, 1-click adaptive traffic control system "
        "designed specifically for Belgaum's high-congestion corridors (Rani Chennamma Circle, College Road, Bogarves, and KLE Hospital). "
        "Replacing outdated static 90-second timers with <b>Webster's HCM formulation</b> and <b>A* dynamic routing</b>, "
        "Smart Route cuts average driver delays by <b>35.1%</b>, provides sub-200ms ambulance preemption green waves, and "
        "predicts congestion 15 to 30 minutes in advance with zero manual configuration."
    )
    summary_table = Table([[Paragraph(summary_text, body_style)]], colWidths=[532])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#bfdbfe")),
        ('PADDING', (0, 0), (-1, -1), 7),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 8))

    # The 5 Core Features strictly for Belgaum
    elements.append(Paragraph("The 5 Core Features Evaluated on Belgaum Corridors", h1_style))

    features_data = [
        [
            Paragraph("Sidebar Icon", table_header),
            Paragraph("Feature Name", table_header),
            Paragraph("Belgaum Real-World Action &amp; Map Result", table_header),
            Paragraph("Algorithm / Formula", table_header)
        ],
        [
            Paragraph("<b>🚦</b>", body_style),
            Paragraph("<b>1. Signal Optimization</b>", body_style),
            Paragraph("Dynamically balances Rani Chennamma Circle splits: College Rd gets 38s Green, Khanapur Rd gets 22s Green.", body_style),
            Paragraph("Webster's HCM:<br/><i>C = (1.5L + 5) / (1 - Y)</i>", body_style)
        ],
        [
            Paragraph("<b>🚨</b>", body_style),
            Paragraph("<b>2. Ambulance Preempt</b>", body_style),
            Paragraph("Locks Chennamma ➔ KLE Hospital corridor 100% GREEN for 30s; cross-traffic held at RED clearance.", body_style),
            Paragraph("Emergency Vehicle Preemption (EVP Priority Protocol)", body_style)
        ],
        [
            Paragraph("<b>🔮</b>", body_style),
            Paragraph("<b>3. Congestion Predict</b>", body_style),
            Paragraph("Predicts 72% congestion spike at Bogarves &amp; RPD Circle 20 mins ahead, marking corridor in Amber.", body_style),
            Paragraph("Multi-factor historical volume &amp; BPR peak forecasting", body_style)
        ],
        [
            Paragraph("<b>🔀</b>", body_style),
            Paragraph("<b>4. Smart Alternate Bypass</b>", body_style),
            Paragraph("Reroutes through Belgaum Ring Road bypass, completely avoiding central bottleneck and saving 9.5 mins.", body_style),
            Paragraph("A* heuristic pathfinding with congestion penalty", body_style)
        ],
        [
            Paragraph("<b>📊</b>", body_style),
            Paragraph("<b>5. Before vs After Proof</b>", body_style),
            Paragraph("Side-by-side benchmark: 63.6s fixed wait reduced to 41.3s (-35.1% saved), +17.1% vehicle throughput.", body_style),
            Paragraph("Highway Capacity Manual (HCM 2010) Delay Formulation", body_style)
        ]
    ]

    feat_table = Table(features_data, colWidths=[55, 115, 232, 130])
    feat_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_primary),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, c_border),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_card_bg]),
    ]))
    elements.append(feat_table)
    elements.append(Spacer(1, 10))

    # Live Demo Script for Judges
    elements.append(Paragraph("1-Minute Judge Evaluation Script", h1_style))
    demo_script = (
        "<b>Step 1:</b> Point to <code>http://localhost:5000</code> and select <b>Chennamma ➔ KLE Hospital</b>.<br/>"
        "<b>Step 2:</b> Click the <b>🚦 Signal</b> icon: Show judges the dynamic split (38s Green for College Rd).<br/>"
        "<b>Step 3:</b> Click the <b>🚨 Siren</b> icon: Show the red emergency corridor locking all signals green to KLE Hospital.<br/>"
        "<b>Step 4:</b> Click the <b>🔮 Crystal Ball</b> icon: Show the predicted 20-minute congestion spike at Bogarves in Amber.<br/>"
        "<b>Step 5:</b> Click the <b>🔀 Bypass</b> icon: Show the purple dashed Belgaum Ring Road detour that saves 9.5 minutes.<br/>"
        "<b>Step 6:</b> Click the <b>📊 Graph</b> icon: Show the -35.1% delay reduction verified under Webster HCM standards."
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
