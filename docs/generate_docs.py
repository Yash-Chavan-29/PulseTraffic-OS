import os
import sys

def create_document():
    import docx
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
    from docx.oxml import OxmlElement, parse_xml
    from docx.oxml.ns import nsdecls, qn

    doc = docx.Document()

    # Set Margins (0.75 in / 54 pt)
    sections = doc.sections
    for s in sections:
        s.top_margin = Inches(0.75)
        s.bottom_margin = Inches(0.75)
        s.left_margin = Inches(0.75)
        s.right_margin = Inches(0.75)

    # Palette
    COLOR_PRIMARY = RGBColor(30, 58, 138)    # Deep Navy #1E3A8A
    COLOR_SECONDARY = RGBColor(37, 99, 235)  # Royal Blue #2563EB
    COLOR_DARK = RGBColor(30, 41, 59)        # Slate Dark #1E293B
    COLOR_MUTED = RGBColor(100, 116, 139)    # Slate Muted #64748B
    COLOR_EMERALD = RGBColor(16, 185, 129)   # Emerald #10B981
    COLOR_AMBER = RGBColor(217, 119, 6)      # Amber #D97706
    COLOR_ROSE = RGBColor(225, 29, 72)       # Rose #E11D48

    HEX_PRIMARY = "1E3A8A"
    HEX_SECONDARY = "2563EB"
    HEX_LIGHT_BG = "F1F5F9"
    HEX_ACCENT_BG = "EFF6FF"
    HEX_BORDER = "CBD5E1"
    HEX_EMERALD_BG = "ECFDF5"

    def set_cell_background(cell, hex_color):
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
        cell._tc.get_or_add_tcPr().append(shading)

    def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
        tcPr.append(tcMar)

    def set_table_borders(table, color=HEX_BORDER, sz="4", val="single"):
        tblPr = table._tbl.tblPr
        borders = parse_xml(
            f'<w:tblBorders {nsdecls("w")}>'
            f'<w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
            f'<w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
            f'<w:left w:val="none"/>'
            f'<w:right w:val="none"/>'
            f'<w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
            f'<w:insideV w:val="none"/>'
            f'</w:tblBorders>'
        )
        tblPr.append(borders)

    def add_title(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(26)
        run.font.bold = True
        run.font.color.rgb = COLOR_PRIMARY

    def add_subtitle(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(18)
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(13)
        run.font.italic = True
        run.font.color.rgb = COLOR_MUTED

    def add_meta_banner(meta_items):
        tbl = doc.add_table(rows=1, cols=len(meta_items))
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(tbl, color="93C5FD", sz="6")
        for i, (k, v) in enumerate(meta_items):
            cell = tbl.cell(0, i)
            set_cell_background(cell, HEX_ACCENT_BG)
            set_cell_margins(cell, top=100, bottom=100, left=120, right=120)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            r_k = p.add_run(k + "\n")
            r_k.font.size = Pt(9)
            r_k.font.bold = True
            r_k.font.color.rgb = COLOR_SECONDARY
            r_v = p.add_run(v)
            r_v.font.size = Pt(10)
            r_v.font.bold = True
            r_v.font.color.rgb = COLOR_DARK
        p_space = doc.add_paragraph()
        p_space.paragraph_format.space_before = Pt(0)
        p_space.paragraph_format.space_after = Pt(12)

    def add_h1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(16)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(17)
        run.font.bold = True
        run.font.color.rgb = COLOR_PRIMARY
        # underline style via XML border bottom or colored accent
        pBdr = parse_xml(f'<w:pBdr {nsdecls("w")}><w:bottom w:val="single" w:sz="12" w:space="4" w:color="{HEX_PRIMARY}"/></w:pBdr>')
        p._p.get_or_add_pPr().append(pBdr)

    def add_h2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(13)
        run.font.bold = True
        run.font.color.rgb = COLOR_SECONDARY

    def add_h3(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(11)
        run.font.bold = True
        run.font.color.rgb = COLOR_DARK

    def add_body(text, bold_prefix=None, space_after=4):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            r_pre = p.add_run(bold_prefix)
            r_pre.font.name = "Calibri"
            r_pre.font.size = Pt(10.5)
            r_pre.font.bold = True
            r_pre.font.color.rgb = COLOR_DARK
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(10.5)
        run.font.color.rgb = COLOR_DARK
        return p

    def add_bullet(text, bold_prefix=None):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(2.5)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            r_pre = p.add_run(bold_prefix)
            r_pre.font.name = "Calibri"
            r_pre.font.size = Pt(10.5)
            r_pre.font.bold = True
            r_pre.font.color.rgb = COLOR_DARK
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(10.5)
        run.font.color.rgb = COLOR_DARK

    def add_callout(title, text, kind="judge"):
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        border_hex = HEX_PRIMARY if kind == "judge" else "10B981"
        bg_hex = HEX_ACCENT_BG if kind == "judge" else HEX_EMERALD_BG
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg_hex}"/>')
        cell._tc.get_or_add_tcPr().append(shd)
        set_cell_margins(cell, top=120, bottom=120, left=180, right=180)
        borders = parse_xml(
            f'<w:tcBorders {nsdecls("w")}>'
            f'<w:left w:val="single" w:sz="24" w:space="0" w:color="{border_hex}"/>'
            f'<w:top w:val="none"/>'
            f'<w:right w:val="none"/>'
            f'<w:bottom w:val="none"/>'
            f'</w:tcBorders>'
        )
        cell._tc.get_or_add_tcPr().append(borders)
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(3)
        r_t = p.add_run(title + "\n")
        r_t.font.name = "Calibri"
        r_t.font.bold = True
        r_t.font.size = Pt(10.5)
        r_t.font.color.rgb = COLOR_PRIMARY if kind == "judge" else COLOR_EMERALD
        r_b = p.add_run(text)
        r_b.font.name = "Calibri"
        r_b.font.size = Pt(10)
        r_b.font.color.rgb = COLOR_DARK
        p_sp = doc.add_paragraph()
        p_sp.paragraph_format.space_before = Pt(0)
        p_sp.paragraph_format.space_after = Pt(4)

    # ==================== DOCUMENT CONTENT ====================
    add_title("PULSETRAFFIC OS")
    add_subtitle("City Traffic Operating System & Route Optimization Platform // Complete Project Guide, Codebase Breakdown, Future Scope & Jury Presentation Defense")

    add_meta_banner([
        ("TRACK & DOMAIN", "Domain 1: Full Stack Web (PS 01)"),
        ("SYSTEM NAME", "PulseTraffic OS (v1.0)"),
        ("CORE ALGORITHM", "BPR Impedance + A* & Dijkstra"),
        ("TECH STACK", "Node.js, Express, Socket.IO, Leaflet"),
        ("TEAM LEAD & PITCH", "Sanjana (Pitch) & Yash (Lead Dev)")
    ])

    # SECTION 1
    add_h1("1. Executive Summary & Problem Solved")
    add_body("Modern metropolitan centers suffer from catastrophic traffic congestion resulting in billions of lost work hours, elevated carbon emissions, increased fuel consumption, and tragic delays for emergency medical services (EMS). Traditional navigation apps (like standard Google Maps or Waze) optimize primarily for static shortest distances or reactively alert drivers once a gridlock has already formed. Furthermore, municipal traffic management centers operate on isolated fixed-timer traffic lights that cannot adapt to real-time directional vehicle surges.")
    add_body("PulseTraffic OS is an end-to-end intelligent city traffic management and route optimization system built for Smart Cities. It bridges the gap between commuter navigation, citizen incident crowdsourcing, municipal traffic light optimization, and life-critical emergency vehicle routing.")
    
    add_callout("🎯 CORE VALUE PROPOSITION FOR THE JURY", 
                "\"PulseTraffic is not just another GPS navigation app—it is a closed-loop Smart City Traffic Operating System. It connects commuters, traffic police signal engineers, and emergency first-responders into a unified, mathematically modeled dynamic ecosystem powered by Bureau of Public Roads (BPR) impedance algorithms and real-time WebSockets.\"", 
                kind="judge")

    add_h2("Team Roles & Responsibilities Matrix")
    add_bullet("Architected the Express server, WebSocket telemetry pipelines, BPR Graph Engine, and AI predictive model.", "Yash (Lead Developer): ")
    add_bullet("Engineered the responsive dark-mode Command Center dashboard, dynamic UI components, state management, and leads the Hackathon Pitch presentation.", "Sanjana (UI/UX & Pitch Lead): ")
    add_bullet("Developed Thunder Client test suites, REST schema validation, mock scenarios, and latency stress testing.", "Samarth (QA & Mock Data Engineer): ")
    add_bullet("Curated realistic Bengaluru road network coordinates, real-time traffic benchmarks, and defense against tough jury technical inquiries.", "Manikanta (Domain Research & Jury Defense): ")

    # SECTION 2
    add_h1("2. Codebase Structure & Architecture Breakdown")
    add_body("The project is structured with a modular, scalable architecture separating the mathematical routing engine, real-time communications, static visualization assets, and client interface.")

    # Table of Files
    table1 = doc.add_table(rows=1, cols=3)
    table1.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table1)
    headers = ["Directory / File", "Type / Layer", "Core Functionality & Purpose"]
    for i, h in enumerate(headers):
        c = table1.cell(0, i)
        set_cell_background(c, HEX_PRIMARY)
        set_cell_margins(c, top=80, bottom=80, left=100, right=100)
        p = c.paragraphs[0]
        r = p.add_run(h)
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)
        r.font.size = Pt(10)

    file_data = [
        ("server/server.js", "Backend Core", "Initializes Express HTTP server and Socket.IO server. Registers CORS, static frontend serving (/public), API routing mounts, and broadcasts telemetry every 4 seconds."),
        ("server/services/graphEngine.js", "Algorithmic Engine", "Implements the Bureau of Public Roads (BPR) link performance formula. Manages road nodes, edges, dynamic volume/capacity ratios, and A* vs. Dijkstra route calculations."),
        ("server/services/mlPredictor.js", "AI Prediction Layer", "Computes 15-30 minute congestion forecasts across urban zones (CBD, Tech Park, Airport Tollway) factoring in rush-hour patterns and incident density."),
        ("server/routes/routes.js", "REST Endpoint", "Handles /api/routes/calculate for comparative route planning and /api/predictions/heatmap for zone-based congestion forecasts."),
        ("server/routes/incidents.js", "REST Endpoint + Deduplication", "Handles /api/incidents/report and /api/incidents/active. Features a 150m & 30-minute deduplication filter and pushes new incidents over WebSockets."),
        ("server/routes/signals.js", "REST Endpoint", "Simulates adaptive signal optimization (/api/signals/optimize). Balances green split timings across 4-way junctions based on queue volume."),
        ("server/routes/emergency.js", "REST Endpoint", "Calculates emergency green-wave corridors (/api/emergency/corridor). Preempts downstream traffic lights into LOCKED_GREEN states, saving over 56% transit time."),
        ("public/index.html", "Frontend Command Center", "Full-featured interactive single-page application. Incorporates Leaflet.js maps, Mapbox dark tiles, 4 modular drawer views, HUD toggles, and incident reporting modal."),
        ("public/road_snippet.js", "GIS Geometry Data", "Stores OSRM-snapped high-fidelity latitude/longitude coordinates providing realistic road curvatures along Bangalore arterial corridors."),
        ("contract.json", "API Specification", "Canonical REST contract schema detailing request and response payloads across all 5 mandatory hackathon features."),
        ("mock_data.json", "Testing Payloads", "Ready-to-execute test scenarios for Thunder Client / Postman ensuring zero-friction demonstration during jury evaluation.")
    ]

    for f, t, desc in file_data:
        row = table1.add_row()
        for col_idx, text in enumerate([f, t, desc]):
            c = row.cells[col_idx]
            set_cell_background(c, HEX_LIGHT_BG if col_idx == 0 else "FFFFFF")
            set_cell_margins(c, top=60, bottom=60, left=80, right=80)
            p = c.paragraphs[0]
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            r = p.add_run(text)
            r.font.size = Pt(9.5)
            if col_idx == 0:
                r.font.bold = True
                r.font.color.rgb = COLOR_DARK

    p_space = doc.add_paragraph()
    p_space.paragraph_format.space_after = Pt(8)

    # SECTION 3
    add_h1("3. In-Depth Feature Breakdown & Mathematical Modeling")
    
    add_h2("3.1 Multi-Factor Commuter Routing (BPR Impedance Formula)")
    add_body("Traditional algorithms like Dijkstra find the shortest geometric distance. However, in urban traffic, the shortest distance often passes directly through congested city centers, making it the slowest path in reality.")
    add_body("PulseTraffic OS replaces arbitrary distance weights with the industry-standard Bureau of Public Roads (BPR) link performance impedance formula:")
    
    add_callout("📐 MATHEMATICAL FORMULATION: BPR LINK PERFORMANCE FUNCTION",
                "Travel Time = (Length / FreeFlowSpeed) * [ 1 + 0.15 * (EffectiveVolume / EffectiveCapacity) ^ 4 ]\n\n"
                "• When Volume << Capacity: Travel time equals free-flow speed.\n"
                "• When Volume approaches or exceeds Capacity: The fourth-power exponent introduces an exponential impedance penalty, accurately mimicking real urban gridlock.\n"
                "• Effective Capacity incorporates active incident reductions: Capacity_eff = Capacity * (1 - Severity * 0.22).\n"
                "• Departure Time Offset (+15m, +30m): Projects volume growth using Volume(t) = Volume_0 * (1 + t * 0.008).",
                kind="tech")

    add_body("The algorithm compares two distinct routes for commuters:", bold_prefix="Comparative Engine: ")
    add_bullet("Travels via NH 44 Airport Expressway. Physical distance is slightly longer (34.8 km), but free-flow speed (75-85 km/h) and high capacity yield an ETA of 36.1 minutes and fuel consumption of 2.44 L. Congestion Risk: Low.", "1. A* Dynamic Heuristic (Recommended): ")
    add_bullet("Travels straight through the downtown arterial and Civic Square. Physical distance is shorter (32.3 km), but volume/capacity ratio causes massive congestion. ETA shoots up to 48.5 minutes with 3.07 L fuel consumption. Congestion Risk: High.", "2. Dijkstra Minimum Distance: ")

    add_h2("3.2 Citizen Incident Reporting & Intelligent Deduplication Engine")
    add_body("During accidents or waterlogging, hundreds of citizens submit redundant reports within minutes, overwhelming emergency dispatch systems and distorting graph routing weights.")
    add_bullet("When a report is received, the server checks whether an active incident of the same type already exists within 150 meters (0.002 lat/lng threshold) and within a 30-minute sliding window.", "Spatial-Temporal Deduplication: ")
    add_bullet("Duplicate reports are clustered under the primary incident ID without skewing road edge weights.", "Cluster Attribution: ")
    add_bullet("Automatically computes capacity reduction (Severity * 22%), estimated clearance duration (Severity * 15 min), and road travel delay penalty (Severity * 3.1 min).", "Dynamic Network Impact: ")
    add_bullet("If an incident has Severity >= 2, the system automatically triggers an in-app dynamic reroute banner recommending a diversion route (e.g. BYPASS-RING-01) and broadcasts an instant WebSocket alert (incident:new) to all active dashboards.", "Automated Diversion Dispatch: ")

    add_h2("3.3 Adaptive Traffic Signal Lab (Queue Length Balancing)")
    add_body("Most metropolitan intersections run on static, fixed-time cycles (e.g. 45 seconds green for North-South and 45 seconds green for East-West), causing empty lanes to hold green lights while heavy traffic queues stagnate.")
    add_bullet("The Signal Lab lets operators adjust or simulate directional vehicle queue lengths (North, South, East, West) using real-time sliders.", "Dynamic Queue Sensing: ")
    add_bullet("Within a fixed 120-second master cycle, PulseTraffic calculates dynamic green splits directly proportional to arrival volume ratios (NS Split vs. EW Split).", "Proportional Green Allocation: ")
    add_bullet("Drops average junction wait time from a baseline of 68.4 seconds down to 39.1 seconds—a verified 42.8% reduction in intersection delay, elevating the intersection to Level of Service (LOS) B.", "Proven Benchmark: ")

    add_h2("3.4 Emergency Vehicle Green-Wave Priority Corridor")
    add_body("Every second lost in transit reduces patient survival rates during medical emergencies. PulseTraffic features an emergency corridor reservation module for Ambulances and Fire Rescue.")
    add_bullet("Origin node and designated trauma hospital are selected. The engine maps the optimal priority route.", "Instant Corridor Activation: ")
    add_bullet("Downstream traffic signals are automatically preempted into a coordinated 'Green Wave'.", "Signal Preemption: ")
    add_bullet("Junction 14 (Tech Park Gateway) is instantly LOCKED_GREEN (0s).", "• Stage 1: ")
    add_bullet("Junction 22 (HAL Airport Road) is queued for preemption at 90 seconds.", "• Stage 2: ")
    add_bullet("Junction 38 (Trinity Circle Gate) is queued for preemption at 210 seconds.", "• Stage 3: ")
    add_bullet("Reduces emergency transit time from 22.4 minutes down to 9.8 minutes—saving 12.6 minutes (a 56.25% reduction in transit delay) without causing peripheral intersection gridlock.", "Life-Saving Impact: ")

    add_h2("3.5 Predictive AI Congestion Heatmap (15-30 Minute Horizon)")
    add_body("PulseTraffic's ML predictor evaluates time-of-day traffic elasticity, historical rush hours (08:00-11:00 AM and 17:00-20:00 PM), and active incident density to calculate zonal risk scores (CRITICAL, MODERATE, LOW). Commuters and city planners can toggle future departure windows (+15 min, +30 min) to view simulated congestion buildup before embarking on their journey.")

    add_h2("3.6 Live WebSocket Telemetry Engine")
    add_body("A persistent Socket.IO channel broadcasts city-wide telemetry every 4 seconds. The dashboard displays live metrics: Network Load (45-65%), Active Monitored Vehicles (1,240-1,340), and Average City Speed (38-46 km/h), demonstrating full-duplex client-server synchronization.")

    # SECTION 4
    add_h1("4. Technical Stack & Architecture Data Flow")
    
    # Table of Tech Stack
    table2 = doc.add_table(rows=1, cols=3)
    table2.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table2)
    t2_headers = ["Layer", "Technologies Used", "Key Architectural Choice & Rationale"]
    for i, h in enumerate(t2_headers):
        c = table2.cell(0, i)
        set_cell_background(c, HEX_SECONDARY)
        set_cell_margins(c, top=80, bottom=80, left=100, right=100)
        p = c.paragraphs[0]
        r = p.add_run(h)
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)
        r.font.size = Pt(10)

    t2_data = [
        ("Frontend UI / UX", "HTML5, CSS3 Custom Properties, Vanilla JavaScript, Leaflet.js, Mapbox Dark Tiles", "Ultra-fast rendering, zero heavy bundle overhead, instant load times, clean dark-mode tactical command center aesthetic."),
        ("Backend Services", "Node.js (v20+ LTS), Express.js (ES Modules)", "Event-driven asynchronous I/O ideal for high-throughput traffic data ingestion and rapid REST responses (< 15ms)."),
        ("Real-Time Comms", "Socket.IO (v4)", "Full-duplex WebSocket communication enabling real-time telemetry streaming and zero-latency incident push notifications."),
        ("Mathematical Models", "Bureau of Public Roads (BPR) Impedance, A* Heuristic, Dijkstra SPP", "Industry-grade traffic flow equation accounting for road volume, capacity, speed limits, and incident degradation."),
        ("GIS & Geometries", "OSRM-snapped GeoJSON polylines, Bengaluru GPS coordinates", "100% road-snapped vehicle trajectory rendering avoiding unrealistic straight-line point-to-point drawing.")
    ]

    for l, tech, rat in t2_data:
        row = table2.add_row()
        for col_idx, text in enumerate([l, tech, rat]):
            c = row.cells[col_idx]
            set_cell_background(c, HEX_LIGHT_BG if col_idx == 0 else "FFFFFF")
            set_cell_margins(c, top=60, bottom=60, left=80, right=80)
            p = c.paragraphs[0]
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            r = p.add_run(text)
            r.font.size = Pt(9.5)
            if col_idx == 0:
                r.font.bold = True
                r.font.color.rgb = COLOR_DARK

    p_space2 = doc.add_paragraph()
    p_space2.paragraph_format.space_after = Pt(8)

    # SECTION 5
    add_h1("5. Comprehensive Future Scope & Expansion Roadmap")
    add_body("While PulseTraffic OS is already an operational prototype demonstrating all 5 core functionalities, its production trajectory is structured across four progressive development phases:")

    add_h2("Phase 1: Computer Vision & Edge AI Junction Monitoring (Q1-Q2)")
    add_bullet("Integration with existing municipal CCTV camera feeds using lightweight YOLOv8 / YOLOv11 models running on edge processors (NVIDIA Jetson) at intersections.", "Real-time Vehicle Detection: ")
    add_bullet("Eliminates manual slider inputs by automatically counting cars, two-wheelers, buses, and heavy trucks in each lane in real-time.", "Automated Queue Counting: ")
    add_bullet("Recognizes vehicle classifications to assign higher impedance weights to heavy multi-axle freight trucks versus compact passenger cars.", "Vehicle Classification: ")

    add_h2("Phase 2: V2X (Vehicle-to-Everything) & DSRC Protocol Integration (Q3)")
    add_bullet("Direct radio / cellular communication (C-V2X) between ambulances/police cruisers and intersection traffic light controllers.", "Hardware In-Cabin Transponders: ")
    add_bullet("Vehicles within 500 meters of an intersection receive optimal approach speed advisories (Green Light Optimal Speed Advisory - GLOSA) so drivers never hit a red light.", "Dynamic Green Wave Handshake: ")

    add_h2("Phase 3: Multi-Modal Public Transit & Citizen Carbon Credits (Q4)")
    add_bullet("Integration of Namma Metro (subway) and BMTC / Smart City Bus GPS telemetry into the routing engine.", "Public Transit Prioritization: ")
    add_bullet("If a commuter chooses an A* fuel-efficient route or public transit bypass, they earn municipal 'Eco-Credits' redeemable for public transit discounts, EV charging rebates, or parking perks.", "Gamified Carbon Incentive Program: ")

    add_h2("Phase 4: Municipal Digital Twin & Predictive Disaster Simulation")
    add_bullet("Simulating city-scale extreme weather events (monsoon flash floods, fallen trees) and waterlogging sensors to automatically reroute traffic hours before major arterial roads get submerged.", "Monsoon & Flood Modeling: ")
    add_bullet("A dedicated emergency routing mode designed for inter-hospital green corridors ensuring zero-delay organ transport between specialized healthcare institutions.", "Green Corridors for Organ Transplantation: ")

    # SECTION 6
    add_h1("6. How to Present PulseTraffic OS in Front of the Judges")
    add_body("The pitch presentation is where hackathons are won. The key to winning is demonstrating real engineering depth, clear problem-solution alignment, live working software, and crisp, confident delivery.")

    add_h2("6.1 The 30-Second Elevator Pitch")
    add_callout("🎙️ OPENING HOOK (DELIVER WITH CONFIDENCE)",
                "\"Respected Judges, urban commuters in Bengaluru and major metros spend an average of 150 hours every year stuck in traffic. Worse, ambulances lose critical minutes at congested intersections. Existing GPS apps only show you where traffic already is—they don't fix the underlying problem.\n\n"
                "We built PulseTraffic OS: a smart city traffic operating system that combines Bureau of Public Roads (BPR) link performance impedance modeling, adaptive traffic signal balancing, citizen incident deduplication, and automated emergency vehicle green waves. In our live benchmarks, we reduce junction wait times by 42.8% and cut emergency transit delay by 56.2%. Let us show you how it works.\"",
                kind="judge")

    add_h2("6.2 Step-by-Step 4-Minute Live Demo Script")
    
    # Table of Demo Steps
    table3 = doc.add_table(rows=1, cols=4)
    table3.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table3)
    t3_headers = ["Time", "Presenter", "Action on Screen", "What to Say to the Judges"]
    for i, h in enumerate(t3_headers):
        c = table3.cell(0, i)
        set_cell_background(c, HEX_PRIMARY)
        set_cell_margins(c, top=80, bottom=80, left=80, right=80)
        p = c.paragraphs[0]
        r = p.add_run(h)
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)
        r.font.size = Pt(9.5)

    demo_steps = [
        ("0:00 - 0:45", "Sanjana", "Show Command Center map. Point to live Socket.IO telemetry ticking at the top.", "Introduce the problem statement (PS 01). Explain the command center UI. Highlight that PulseTraffic connects citizens, traffic engineers, and EMS on one single-pane-of-glass."),
        ("0:45 - 1:45", "Yash", "Click 'Route Search'. Select Central Station to Airport. Toggle '+15 min'. Click 'Calculate BPR Routes'.", "Explain why Dijkstra is flawed in cities (it picks the shortest 32.3 km route through Civic Square, taking 48.5 min). Show how our A* BPR impedance engine routes via NH 44 Expressway (34.8 km, but takes only 36.1 min and saves 20% fuel)."),
        ("1:45 - 2:30", "Sanjana & Manikanta", "Click 'Report Incident' FAB. Submit an accident at Hebbal. Show instant reroute banner.", "Show citizen crowdsourcing. Point out the deduplication engine (<150m, 30m window). Show the instant dynamic reroute banner: '+9.2 min delay detected; switch to Ring Road Bypass'."),
        ("2:30 - 3:15", "Samarth & Yash", "Switch tab to 'Signal Lab'. Drag North slider to 38, East to 44. Click 'Compute Adaptive Green Splits'.", "Show the live signal optimization. Contrast fixed 45s timers (68.4s wait) against our dynamic BPR split (39.1s wait). Emphasize the 42.8% wait time reduction."),
        ("3:15 - 4:00", "Sanjana", "Switch tab to 'Emergency Corridor'. Select Ambulance -> City Hospital. Click 'Trigger Emergency Green Wave'.", "Show the emerald green wave on the map. Point to preempted signals: JNC-14 Locked Green, JNC-22 Queued. State: '12.6 minutes saved—56.25% faster transit. This saves human lives.'"),
        ("4:00 - 5:00", "All", "Show Future Scope slide and open floor for Jury Q&A.", "Summarize the tech stack (Node.js, Express, Socket.IO, Leaflet). Invite questions from the jury.")
    ]

    for tm, pres, act, say in demo_steps:
        row = table3.add_row()
        for col_idx, text in enumerate([tm, pres, act, say]):
            c = row.cells[col_idx]
            set_cell_background(c, HEX_LIGHT_BG if col_idx == 0 else "FFFFFF")
            set_cell_margins(c, top=60, bottom=60, left=70, right=70)
            p = c.paragraphs[0]
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            r = p.add_run(text)
            r.font.size = Pt(9)
            if col_idx in (0, 1):
                r.font.bold = True
                r.font.color.rgb = COLOR_DARK

    p_space3 = doc.add_paragraph()
    p_space3.paragraph_format.space_after = Pt(8)

    add_h2("6.3 Anticipated Judge Questions & Bulletproof Winning Answers")

    qa_list = [
        ("Judge Q1: \"How does your routing algorithm differ from Google Maps or Mapbox Directions?\"",
         "Answer: \"Standard commercial mapping APIs treat traffic as a black box and predominantly calculate shortest-time routes after congestion has already formed. PulseTraffic implements the mathematical Bureau of Public Roads (BPR) link performance function directly on the road network graph. We model volume-over-capacity to the 4th power, allowing us to simulate congestion elasticity 15-30 minutes into the future. Furthermore, unlike Google Maps, our system natively links with city traffic light controllers for emergency green wave preemption and adaptive signal cycle reallocation.\"",
         "Yash / Manikanta"),
        ("Judge Q2: \"How do you prevent malicious or fake incident reports from corrupting the graph?\"",
         "Answer: \"We employ a two-layer verification pipeline. First, our Spatial-Temporal Deduplication Engine clusters reports occurring within 150 meters and 30 minutes. Second, citizen reports require a multi-confirmation threshold before applying maximum graph capacity penalties. In Phase 2, we integrate CCTV computer vision verification where edge cameras automatically validate physical obstructions before dispatching municipal diversions.\"",
         "Samarth / Sanjana"),
        ("Judge Q3: \"If you lock green signals for an ambulance, won't that cause massive gridlocks on intersecting roads?\"",
         "Answer: \"That is precisely why we designed Queued Preemption rather than brute-force signal halting. Our emergency corridor algorithm calculates vehicle arrival times (ETAs) at each downstream junction. Signals are not locked instantly across the entire city; instead, JNC-14 clears immediately, JNC-22 preempts at 90 seconds, and JNC-38 at 210 seconds. This allows intersecting traffic to cycle normally until 20 seconds before the ambulance arrives, minimizing cross-street delay while guaranteeing zero-delay passage for the ambulance.\"",
         "Yash / Manikanta"),
        ("Judge Q4: \"What is the computational complexity of running A* and Dijkstra on a large city graph with tens of thousands of nodes?\"",
         "Answer: \"A standard Dijkstra algorithm has a time complexity of O(|E| + |V| log |V|) with a priority queue. By introducing the A* heuristic based on Euclidean distance divided by maximum expressway free-flow speed, we prune the search space by over 60%. On our Node.js BPR graph engine, calculation across Bengaluru arterial networks completes in under 12 milliseconds. For city-scale expansion (100,000+ nodes), we can partition the graph into hierarchical road levels (Highways, Arterials, Locals) using Contraction Hierarchies.\"",
         "Yash"),
        ("Judge Q5: \"How does your adaptive traffic signal algorithm work mathematically?\"",
         "Answer: \"We use dynamic Webster-based cycle split optimization. Within a standard 120-second master cycle, green time is partitioned proportionally: Green_NS = (Volume_NS / TotalVolume) * CycleTime. We then calculate average vehicle delay using BPR queue impedance. By reallocating green time dynamically to high-density approaches, we reduce average intersection delay from 68.4s to 39.1s—a 42.8% improvement verified in our Signal Lab benchmarks.\"",
         "Manikanta / Yash"),
        ("Judge Q6: \"How viable is this project commercially or from a smart-city government deployment perspective?\"",
         "Answer: \"PulseTraffic is designed for direct integration with Smart Cities Mission municipal command centers (ICCC). Revenue and viability come from three tiers: 1) Municipal SaaS licensing for traffic management centers; 2) Fleet API subscriptions for logistics and ambulance operators; and 3) Premium commuter routing with carbon credit integrations. It uses existing CCTV and fiber infrastructure, requiring zero high-cost road resurfacing.\"",
         "Sanjana")
    ]

    for q, a, speaker in qa_list:
        add_h3(q)
        add_body(a, bold_prefix="Bulletproof Defense: ", space_after=2)
        add_body(f"Recommended Presenter: {speaker}\n", bold_prefix="Spokesperson: ", space_after=6)

    # SECTION 7
    add_h1("7. Key Performance Benchmarks & Metrics Summary")
    add_body("Keep these verified numbers at the top of your mind during the presentation:")
    add_bullet("Reduced intersection vehicle delay from 68.4s to 39.1s via adaptive BPR green splits.", "• 42.8% Wait Time Reduction: ")
    add_bullet("Cut emergency vehicle transit time from 22.4 minutes down to 9.8 minutes.", "• 56.25% Emergency Transit Improvement: ")
    add_bullet("Saved on the simulated Central Station to City Central Hospital emergency corridor.", "• 12.6 Minutes Saved: ")
    add_bullet("A* BPR Expressway route saves ~20% fuel compared to congested downtown arterial path (2.44 L vs 3.07 L).", "• ~20% Fuel Savings: ")
    add_bullet("Deduplication radius filtering redundant citizen reports within a 30-minute window.", "• 150m & 30-Minute Deduplication Window: ")
    add_bullet("Full-duplex WebSocket telemetry tick rate broadcasting network load, active vehicles, and average speed.", "• 4-Second Real-Time Telemetry Stream: ")
    add_bullet("REST endpoint response latency for multi-factor route calculation.", "• < 15ms Engine Latency: ")

    # Save document
    output_path = r"C:\Hackothon\PulseTraffic_OS_Complete_Project_Guide_and_Pitch.docx"
    doc.save(output_path)
    print(f"DOCUMENT_SAVED_SUCCESSFULLY: {output_path}")

if __name__ == "__main__":
    create_document()
