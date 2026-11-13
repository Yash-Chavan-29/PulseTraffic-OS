let Database;
try {
  const mod = await import('better-sqlite3');
  Database = mod.default;
} catch {
  const { DatabaseSync } = await import('node:sqlite');
  Database = class extends DatabaseSync {
    pragma(str) {
      try {
        return this.exec(`PRAGMA ${str}`);
      } catch (err) {
        return null;
      }
    }
  };
}
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const dbPath = path.join(__dirname, '..', 'traffic.db');
const db = new Database(dbPath);

// Enable WAL mode for high concurrency
db.pragma('journal_mode = WAL');

// Initialize schema with safety
db.exec(`
  CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    severity INTEGER NOT NULL DEFAULT 1,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    road_segment_id TEXT,
    description TEXT,
    reported_by TEXT,
    status TEXT NOT NULL DEFAULT 'unverified',
    confirmations INTEGER NOT NULL DEFAULT 1,
    cluster_incident_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS incident_reports (
    report_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    type TEXT NOT NULL,
    title TEXT,
    description TEXT,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    road_segment_id TEXT,
    lanes_blocked INTEGER DEFAULT 1,
    total_lanes INTEGER DEFAULT 3,
    reported_by TEXT DEFAULT 'Citizen',
    is_duplicate INTEGER DEFAULT 0,
    match_confidence REAL DEFAULT 0,
    match_reason TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS road_closure_simulations (
    simulation_id TEXT PRIMARY KEY,
    road_segment_id TEXT NOT NULL,
    incident_id TEXT,
    closure_type TEXT NOT NULL,
    blocked_lanes INTEGER DEFAULT 1,
    total_lanes INTEGER DEFAULT 3,
    capacity_reduction_percent REAL DEFAULT 50.0,
    estimated_duration_min INTEGER DEFAULT 60,
    notes TEXT,
    active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS incident_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    changed_by TEXT DEFAULT 'System',
    notes TEXT,
    changed_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS signal_junctions (
    junction_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    queue_north INTEGER DEFAULT 0,
    queue_south INTEGER DEFAULT 0,
    queue_east INTEGER DEFAULT 0,
    queue_west INTEGER DEFAULT 0,
    baseline_wait_sec REAL DEFAULT 65.0,
    optimized_wait_sec REAL DEFAULT 42.0,
    green_split_ns INTEGER DEFAULT 50,
    green_split_ew INTEGER DEFAULT 50,
    cycle_time_sec INTEGER DEFAULT 90,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS route_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origin_name TEXT,
    destination_name TEXT,
    astar_eta_min REAL,
    dijkstra_eta_min REAL,
    distance_km REAL,
    fuel_litres REAL,
    reliability_score REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
`);

// Safe column migrations on incidents table
const safeAddColumns = [
  "ALTER TABLE incidents ADD COLUMN title TEXT",
  "ALTER TABLE incidents ADD COLUMN lanes_blocked INTEGER DEFAULT 1",
  "ALTER TABLE incidents ADD COLUMN total_lanes INTEGER DEFAULT 3",
  "ALTER TABLE incidents ADD COLUMN estimated_duration_min INTEGER DEFAULT 45",
  "ALTER TABLE incidents ADD COLUMN severity_category TEXT DEFAULT 'MEDIUM'",
  "ALTER TABLE incidents ADD COLUMN severity_score REAL DEFAULT 50.0",
  "ALTER TABLE incidents ADD COLUMN severity_factors TEXT DEFAULT '[]'",
  "ALTER TABLE incidents ADD COLUMN is_duplicate INTEGER DEFAULT 0",
  "ALTER TABLE incidents ADD COLUMN parent_incident_id TEXT",
  "ALTER TABLE incidents ADD COLUMN duplicate_confidence REAL DEFAULT 0.0",
  "ALTER TABLE incidents ADD COLUMN duplicate_reason TEXT",
  "ALTER TABLE incidents ADD COLUMN affected_road_name TEXT",
  "ALTER TABLE incidents ADD COLUMN closure_type TEXT DEFAULT 'none'",
  "ALTER TABLE incidents ADD COLUMN response_priority TEXT DEFAULT 'Standard'"
];

for (const sql of safeAddColumns) {
  try {
    db.exec(sql);
  } catch (err) {
    // Column already exists or error ignored
  }
}

// Create indexes
try {
  db.exec(`
    CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
    CREATE INDEX IF NOT EXISTS idx_incidents_created ON incidents(created_at);
    CREATE INDEX IF NOT EXISTS idx_reports_incident ON incident_reports(incident_id);
    CREATE INDEX IF NOT EXISTS idx_closures_active ON road_closure_simulations(active);
  `);
} catch (e) {}

/**
 * Haversine formula to compute distance in meters between two lat/lng pairs
 */
export function haversineDistanceMeters(lat1, lon1, lat2, lon2) {
  const R = 6371e3; // Earth radius in meters
  const phi1 = (lat1 * Math.PI) / 180;
  const phi2 = (lat2 * Math.PI) / 180;
  const deltaPhi = ((lat2 - lat1) * Math.PI) / 180;
  const deltaLambda = ((lon2 - lon1) * Math.PI) / 180;

  const a =
    Math.sin(deltaPhi / 2) * Math.sin(deltaPhi / 2) +
    Math.cos(phi1) * Math.cos(phi2) * Math.sin(deltaLambda / 2) * Math.sin(deltaLambda / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

  return R * c;
}

/**
 * Jaccard text token similarity
 */
export function textSimilarity(text1, text2) {
  if (!text1 || !text2) return 0;
  const clean1 = text1.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').split(/\s+/).filter(w => w.length > 2);
  const clean2 = text2.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').split(/\s+/).filter(w => w.length > 2);
  if (!clean1.length || !clean2.length) return 0;
  const set1 = new Set(clean1);
  const set2 = new Set(clean2);
  let intersection = 0;
  for (const word of set1) {
    if (set2.has(word)) intersection++;
  }
  const union = new Set([...clean1, ...clean2]).size;
  return union > 0 ? (intersection / union) : 0;
}

/**
 * Transparent Rule-Based Severity Scoring Engine
 */
export function calculateIncidentSeverity({
  type = 'accident',
  lanesBlocked = 1,
  totalLanes = 3,
  roadType = 'arterial',
  estimatedDurationMin = 45,
  isEmergencyCorridor = false
}) {
  const factors = [];
  let score = 0;

  // 1. Base Disruption Type Impact (max 35 pts)
  const typeMap = {
    accident: { pts: 35, label: "Traffic Collision / Accident" },
    road_closure: { pts: 35, label: "Full / Partial Road Closure" },
    flooding: { pts: 30, label: "Severe Monsoon Waterlogging" },
    hazard: { pts: 25, label: "Hazardous Obstruction / Debris" },
    traffic_obstruction: { pts: 25, label: "Traffic Chokepoint / Jam" },
    road_construction: { pts: 20, label: "Road Construction / Maintenance" },
    breakdown: { pts: 15, label: "Vehicle Mechanical Breakdown" },
    other: { pts: 15, label: "Reported Disruption" }
  };
  const typeInfo = typeMap[type] || typeMap.other;
  score += typeInfo.pts;
  factors.push({ name: "Disruption Type", points: typeInfo.pts, detail: typeInfo.label });

  // 2. Lane Blockage Ratio (max 30 pts)
  const laneRatio = Math.min(1.0, Math.max(0.1, lanesBlocked / Math.max(1, totalLanes)));
  const lanePts = Math.round(laneRatio * 30);
  score += lanePts;
  factors.push({
    name: "Lane Blockage",
    points: lanePts,
    detail: `${lanesBlocked} of ${totalLanes} lanes blocked (${Math.round(laneRatio * 100)}% capacity reduction)`
  });

  // 3. Road Hierarchy & Traffic Spine (max 20 pts)
  let roadPts = 12;
  let roadLabel = "Secondary City Corridor";
  if (roadType === 'expressway' || roadType === 'highway' || roadType === 'primary_spine') {
    roadPts = 20;
    roadLabel = "Primary Highway / Arterial Expressway (High Volume)";
  } else if (roadType === 'local') {
    roadPts = 6;
    roadLabel = "Local Transit Sector";
  }
  score += roadPts;
  factors.push({ name: "Road Hierarchy", points: roadPts, detail: roadLabel });

  // 4. Estimated Duration Impact (max 10 pts)
  let durPts = 5;
  if (estimatedDurationMin >= 120) {
    durPts = 10;
  } else if (estimatedDurationMin >= 60) {
    durPts = 8;
  }
  score += durPts;
  factors.push({ name: "Duration", points: durPts, detail: `Estimated clearance: ~${estimatedDurationMin} minutes` });

  // 5. Emergency Corridor / Hospital Transit Factor (max 5 pts)
  if (isEmergencyCorridor) {
    score += 5;
    factors.push({ name: "Emergency Priority", points: 5, detail: "Directly impacts critical hospital/ambulance corridor" });
  }

  score = Math.min(100, Math.max(10, score));

  // Classification into standard categories
  let category = "MEDIUM";
  let numericalSeverity = 2;
  let responsePriority = "Medium Priority";
  let recommendedAction = "Deploy local traffic marshals; advisory speed reduction";

  if (score >= 80) {
    category = "CRITICAL";
    numericalSeverity = 4;
    responsePriority = "Immediate Emergency Response";
    recommendedAction = "Dispatch emergency units; activate automated perimeter ring road diversions and signal preemption";
  } else if (score >= 55) {
    category = "HIGH";
    numericalSeverity = 3;
    responsePriority = "High Priority";
    recommendedAction = "Deploy rapid response patrol; trigger adaptive signal timing and automated diversion warning";
  } else if (score < 30) {
    category = "LOW";
    numericalSeverity = 1;
    responsePriority = "Routine Monitoring";
    recommendedAction = "Monitor traffic telemetry cameras; surface advisory alert";
  }

  return {
    score,
    numericalSeverity,
    category,
    responsePriority,
    recommendedAction,
    factors
  };
}

/**
 * Intelligent Duplicate Incident Detection
 */
export function detectDuplicateIncident({
  lat,
  lng,
  type = 'accident',
  description = '',
  radiusMeters = 200,
  windowMinutes = 60
}) {
  const stmt = db.prepare(`
    SELECT * FROM incidents
    WHERE status != 'resolved' AND status != 'rejected'
      AND datetime(created_at) >= datetime('now', '-' || ? || ' minute')
    ORDER BY created_at DESC
  `);
  const activeList = stmt.all(windowMinutes);

  for (const inc of activeList) {
    const dist = haversineDistanceMeters(lat, lng, inc.lat, inc.lng);
    if (dist <= radiusMeters) {
      // Proximity score: high within 100m
      const geoScore = dist <= 75 ? 1.0 : Math.max(0.3, 1 - (dist / radiusMeters));

      // Type match: 1.0 if identical, 0.5 if related disruption
      const typeScore = (inc.type === type) ? 1.0 : 0.4;

      // Text description similarity
      const txtSim = textSimilarity(description, inc.description || inc.title || '');

      // Composite Confidence Score
      const confidence = Number(((geoScore * 0.50) + (typeScore * 0.30) + (txtSim * 0.20)).toFixed(2));

      if (confidence >= 0.55 || dist <= 120) {
        const reasons = [];
        reasons.push(`Within ${Math.round(dist)}m of active incident ${inc.id}`);
        if (inc.type === type) {
          reasons.push(`Identical disruption type (${type})`);
        } else {
          reasons.push(`Related disruption type (${type} vs ${inc.type})`);
        }
        if (txtSim > 0.20) {
          reasons.push(`Description similarity match: ${Math.round(txtSim * 100)}%`);
        }

        return {
          isDuplicate: true,
          confidence: Math.min(0.98, Math.max(0.70, confidence)),
          parentIncident: inc,
          reasons
        };
      }
    }
  }

  return {
    isDuplicate: false,
    confidence: 0,
    parentIncident: null,
    reasons: []
  };
}

/**
 * Record a new incident report with intelligent deduplication
 */
export function recordIncidentReport(data) {
  const {
    id = `INC-${Math.floor(1000 + Math.random() * 9000)}`,
    reportId = `REP-${Math.floor(1000 + Math.random() * 9000)}`,
    title = '',
    type = 'accident',
    description = '',
    lat,
    lng,
    roadSegmentId = 'BEL-CORRIDOR-01',
    affectedRoadName = 'Belagavi City Arterial',
    lanesBlocked = 1,
    totalLanes = 3,
    estimatedDurationMin = 45,
    reportedBy = 'Citizen',
    roadType = 'arterial',
    isEmergencyCorridor = false
  } = data;

  // Run transparent severity evaluation
  const severityEval = calculateIncidentSeverity({
    type,
    lanesBlocked,
    totalLanes,
    roadType,
    estimatedDurationMin,
    isEmergencyCorridor
  });

  // Check for duplicate reports
  const duplicateCheck = detectDuplicateIncident({
    lat,
    lng,
    type,
    description,
    radiusMeters: 200,
    windowMinutes: 60
  });

  if (duplicateCheck.isDuplicate && duplicateCheck.parentIncident) {
    const parent = duplicateCheck.parentIncident;
    const newConfirmations = (parent.confirmations || 1) + 1;
    const updatedSeverity = Math.max(parent.severity || 1, severityEval.numericalSeverity);

    // Update parent incident in DB without deleting report
    const updateStmt = db.prepare(`
      UPDATE incidents
      SET confirmations = ?,
          severity = ?,
          updated_at = CURRENT_TIMESTAMP
      WHERE id = ?
    `);
    updateStmt.run(newConfirmations, updatedSeverity, parent.id);

    // Save report in incident_reports linked to parent
    const insertRep = db.prepare(`
      INSERT INTO incident_reports (
        report_id, incident_id, type, title, description, lat, lng,
        road_segment_id, lanes_blocked, total_lanes, reported_by,
        is_duplicate, match_confidence, match_reason
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
    `);
    insertRep.run(
      reportId,
      parent.id,
      type,
      title || `${type.toUpperCase()} Report`,
      description,
      lat,
      lng,
      roadSegmentId,
      lanesBlocked,
      totalLanes,
      reportedBy,
      duplicateCheck.confidence,
      duplicateCheck.reasons.join('; ')
    );

    return {
      incidentId: parent.id,
      reportId,
      isDuplicate: true,
      duplicateConfidence: duplicateCheck.confidence,
      duplicateReasons: duplicateCheck.reasons,
      parentIncidentId: parent.id,
      confirmations: newConfirmations,
      status: parent.status,
      severity: updatedSeverity,
      severityCategory: parent.severity_category || severityEval.category,
      severityScore: parent.severity_score || severityEval.score,
      severityFactors: severityEval.factors,
      responsePriority: severityEval.responsePriority,
      recommendedAction: severityEval.recommendedAction,
      lat: parent.lat,
      lng: parent.lng,
      roadSegmentId: parent.road_segment_id || roadSegmentId,
      description: parent.description,
      created_at: parent.created_at
    };
  }

  // Create new master incident record
  const insertInc = db.prepare(`
    INSERT INTO incidents (
      id, type, severity, lat, lng, road_segment_id, description, reported_by,
      status, confirmations, cluster_incident_id, title, lanes_blocked, total_lanes,
      estimated_duration_min, severity_category, severity_score, severity_factors,
      is_duplicate, parent_incident_id, duplicate_confidence, duplicate_reason,
      affected_road_name, response_priority
    ) VALUES (
      ?, ?, ?, ?, ?, ?, ?, ?,
      'unverified', 1, ?, ?, ?, ?,
      ?, ?, ?, ?,
      0, NULL, 0, NULL,
      ?, ?
    )
  `);

  insertInc.run(
    id,
    type,
    severityEval.numericalSeverity,
    lat,
    lng,
    roadSegmentId,
    description || title || 'Reported Road Incident',
    reportedBy,
    id,
    title || `${type.toUpperCase()} at ${affectedRoadName}`,
    lanesBlocked,
    totalLanes,
    estimatedDurationMin,
    severityEval.category,
    severityEval.score,
    JSON.stringify(severityEval.factors),
    affectedRoadName,
    severityEval.responsePriority
  );

  // Record initial report in incident_reports table
  const insertRep = db.prepare(`
    INSERT INTO incident_reports (
      report_id, incident_id, type, title, description, lat, lng,
      road_segment_id, lanes_blocked, total_lanes, reported_by,
      is_duplicate, match_confidence, match_reason
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 'Initial Verified Master Report')
  `);
  insertRep.run(
    reportId,
    id,
    type,
    title || `${type.toUpperCase()} Report`,
    description,
    lat,
    lng,
    roadSegmentId,
    lanesBlocked,
    totalLanes,
    reportedBy
  );

  return {
    incidentId: id,
    reportId,
    isDuplicate: false,
    duplicateConfidence: 0,
    duplicateReasons: [],
    parentIncidentId: null,
    confirmations: 1,
    status: 'unverified',
    severity: severityEval.numericalSeverity,
    severityCategory: severityEval.category,
    severityScore: severityEval.score,
    severityFactors: severityEval.factors,
    responsePriority: severityEval.responsePriority,
    recommendedAction: severityEval.recommendedAction,
    lat,
    lng,
    roadSegmentId,
    affectedRoadName,
    description: description || title || 'Reported Road Incident',
    created_at: new Date().toISOString()
  };
}

/**
 * Backward compatibility alias for legacy code
 */
export function saveOrUpdateIncident(data) {
  return recordIncidentReport(data);
}

/**
 * Query active incidents with optional search & filtering
 */
export function getActiveIncidents(filters = {}) {
  let query = `SELECT * FROM incidents WHERE status != 'resolved' AND status != 'rejected'`;
  const params = [];

  if (filters.type && filters.type !== 'all') {
    query += ` AND type = ?`;
    params.push(filters.type);
  }
  if (filters.status && filters.status !== 'all') {
    query += ` AND status = ?`;
    params.push(filters.status);
  }
  if (filters.severityCategory && filters.severityCategory !== 'all') {
    query += ` AND severity_category = ?`;
    params.push(filters.severityCategory);
  }
  if (filters.search) {
    query += ` AND (description LIKE ? OR title LIKE ? OR road_segment_id LIKE ? OR affected_road_name LIKE ?)`;
    const s = `%${filters.search}%`;
    params.push(s, s, s, s);
  }

  query += ` ORDER BY created_at DESC`;
  const stmt = db.prepare(query);
  return stmt.all(...params);
}

/**
 * Retrieve incident by ID with linked reports
 */
export function getIncidentById(id) {
  const inc = db.prepare('SELECT * FROM incidents WHERE id = ?').get(id);
  if (!inc) return null;

  const reports = db.prepare('SELECT * FROM incident_reports WHERE incident_id = ? ORDER BY created_at DESC').all(id);
  const history = db.prepare('SELECT * FROM incident_status_history WHERE incident_id = ? ORDER BY changed_at DESC').all(id);

  let factors = [];
  try {
    factors = JSON.parse(inc.severity_factors || '[]');
  } catch (e) {}

  return {
    ...inc,
    severityFactors: factors,
    linkedReports: reports,
    statusHistory: history
  };
}

/**
 * Update incident status with history logging
 */
export function updateIncidentStatus(id, newStatus, changedBy = 'Admin', notes = '') {
  const current = db.prepare('SELECT * FROM incidents WHERE id = ?').get(id);
  if (!current) return null;

  const updateStmt = db.prepare(`
    UPDATE incidents
    SET status = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
  `);
  updateStmt.run(newStatus, id);

  try {
    const historyStmt = db.prepare(`
      INSERT INTO incident_status_history (incident_id, old_status, new_status, changed_by, notes)
      VALUES (?, ?, ?, ?, ?)
    `);
    historyStmt.run(id, current.status, newStatus, changedBy, notes);
  } catch (e) {}

  return db.prepare('SELECT * FROM incidents WHERE id = ?').get(id);
}

/**
 * Manage duplicate relationship (confirm/reject)
 */
export function updateDuplicateRelationship(incidentId, { isDuplicate, parentId, action = 'confirm' }) {
  const inc = db.prepare('SELECT * FROM incidents WHERE id = ?').get(incidentId);
  if (!inc) return null;

  if (action === 'reject') {
    db.prepare(`
      UPDATE incidents
      SET is_duplicate = 0, parent_incident_id = NULL, duplicate_reason = 'Rejected by Administrator', updated_at = CURRENT_TIMESTAMP
      WHERE id = ?
    `).run(incidentId);
  } else {
    db.prepare(`
      UPDATE incidents
      SET is_duplicate = 1, parent_incident_id = ?, duplicate_reason = 'Confirmed by Administrator', updated_at = CURRENT_TIMESTAMP
      WHERE id = ?
    `).run(parentId || inc.parent_incident_id, incidentId);
  }

  return db.prepare('SELECT * FROM incidents WHERE id = ?').get(incidentId);
}

/**
 * Save road closure simulation
 */
export function saveRoadClosureSimulation(data) {
  const {
    simulationId = `SIM-${Math.floor(1000 + Math.random() * 9000)}`,
    roadSegmentId,
    incidentId = null,
    closureType = 'full_closure',
    blockedLanes = 2,
    totalLanes = 3,
    capacityReductionPercent = 100,
    estimatedDurationMin = 60,
    notes = ''
  } = data;

  const stmt = db.prepare(`
    INSERT INTO road_closure_simulations (
      simulation_id, road_segment_id, incident_id, closure_type,
      blocked_lanes, total_lanes, capacity_reduction_percent,
      estimated_duration_min, notes, active, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
  `);

  stmt.run(
    simulationId,
    roadSegmentId,
    incidentId,
    closureType,
    blockedLanes,
    totalLanes,
    capacityReductionPercent,
    estimatedDurationMin,
    notes
  );

  return db.prepare('SELECT * FROM road_closure_simulations WHERE simulation_id = ?').get(simulationId);
}

/**
 * Deactivate road closure simulation
 */
export function deactivateRoadClosureSimulation(roadSegmentId) {
  const stmt = db.prepare(`
    UPDATE road_closure_simulations
    SET active = 0, updated_at = CURRENT_TIMESTAMP
    WHERE road_segment_id = ? AND active = 1
  `);
  stmt.run(roadSegmentId);
  return { roadSegmentId, restored: true };
}

/**
 * Get active simulations
 */
export function getActiveRoadClosureSimulations() {
  return db.prepare('SELECT * FROM road_closure_simulations WHERE active = 1').all();
}

/**
 * System-wide incident statistics
 */
export function getIncidentStatistics() {
  const totalActive = db.prepare(`SELECT COUNT(*) as count FROM incidents WHERE status != 'resolved' AND status != 'rejected'`).get().count;
  const criticalCount = db.prepare(`SELECT COUNT(*) as count FROM incidents WHERE status != 'resolved' AND status != 'rejected' AND (severity_category = 'CRITICAL' OR severity >= 4)`).get().count;
  const highCount = db.prepare(`SELECT COUNT(*) as count FROM incidents WHERE status != 'resolved' AND status != 'rejected' AND (severity_category = 'HIGH' OR severity = 3)`).get().count;
  const duplicatesCount = db.prepare(`SELECT COUNT(*) as count FROM incident_reports WHERE is_duplicate = 1`).get().count;
  const activeClosures = db.prepare(`SELECT COUNT(*) as count FROM road_closure_simulations WHERE active = 1`).get().count;
  
  // Total affected segments
  const distinctSegments = db.prepare(`SELECT COUNT(DISTINCT road_segment_id) as count FROM incidents WHERE status != 'resolved' AND status != 'rejected'`).get().count;

  return {
    totalActive,
    criticalCount,
    highCount,
    duplicatesCount,
    activeClosures,
    affectedSegmentsCount: distinctSegments
  };
}

export default db;