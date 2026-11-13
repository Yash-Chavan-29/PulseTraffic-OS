import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const dbPath = path.join(__dirname, '..', 'traffic.db');
const db = new Database(dbPath);

// Enable WAL mode for high concurrency
db.pragma('journal_mode = WAL');

// Initialize schema
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
 * Deduplicate incident: check if an active incident exists within 150m in the last 30 minutes
 */
export function findDuplicateIncident(lat, lng, radiusMeters = 150, windowMinutes = 30) {
  const stmt = db.prepare(`
    SELECT * FROM incidents
    WHERE status != 'resolved' AND status != 'rejected'
      AND datetime(created_at) >= datetime('now', '-' || ? || ' minute')
  `);
  const activeList = stmt.all(windowMinutes);

  for (const inc of activeList) {
    const dist = haversineDistanceMeters(lat, lng, inc.lat, inc.lng);
    if (dist <= radiusMeters) {
      return inc;
    }
  }
  return null;
}

/**
 * Record a new incident or increase confirmation if duplicate
 */
export function saveOrUpdateIncident({ id, type, severity, lat, lng, roadSegmentId, description, reportedBy }) {
  const existing = findDuplicateIncident(lat, lng);
  if (existing) {
    const updateStmt = db.prepare(`
      UPDATE incidents
      SET confirmations = confirmations + 1,
          severity = MAX(severity, ?),
          updated_at = CURRENT_TIMESTAMP
      WHERE id = ?
    `);
    updateStmt.run(severity || 1, existing.id);

    return {
      incidentId: existing.id,
      deduplicated: true,
      clusterIncidentId: existing.id,
      confirmations: existing.confirmations + 1,
      status: existing.status
    };
  }

  const insertStmt = db.prepare(`
    INSERT INTO incidents (id, type, severity, lat, lng, road_segment_id, description, reported_by, status, confirmations, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'unverified', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
  `);
  insertStmt.run(id, type, severity || 1, lat, lng, roadSegmentId || null, description || '', reportedBy || 'Citizen');

  return {
    incidentId: id,
    deduplicated: false,
    clusterIncidentId: id,
    confirmations: 1,
    status: 'unverified'
  };
}

/**
 * Get all active incidents
 */
export function getActiveIncidents() {
  const stmt = db.prepare(`
    SELECT * FROM incidents
    WHERE status != 'resolved' AND status != 'rejected'
    ORDER BY created_at DESC
  `);
  return stmt.all();
}

/**
 * Update incident status (e.g. verified, resolved, rejected)
 */
export function updateIncidentStatus(id, newStatus) {
  const stmt = db.prepare(`
    UPDATE incidents
    SET status = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
  `);
  const info = stmt.run(newStatus, id);
  if (info.changes === 0) return null;

  return db.prepare('SELECT * FROM incidents WHERE id = ?').get(id);
}

/**
 * Seed sample signal junctions in Belagavi if table is empty
 */
const countSignals = db.prepare('SELECT COUNT(*) as count FROM signal_junctions').get();
if (countSignals.count === 0) {
  const insertSignal = db.prepare(`
    INSERT INTO signal_junctions (junction_id, name, lat, lng, queue_north, queue_south, queue_east, queue_west, baseline_wait_sec, optimized_wait_sec)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);
  const initialSignals = [
    { id: 'JNC-14', name: 'Chennamma Circle Hub', lat: 15.8497, lng: 74.5089, qN: 38, qS: 12, qE: 44, qW: 18, base: 68.4, opt: 42.1 },
    { id: 'JNC-08', name: 'Bogarves Intersection', lat: 15.8572, lng: 74.5034, qN: 25, qS: 19, qE: 30, qW: 15, base: 58.0, opt: 36.5 },
    { id: 'JNC-22', name: 'CBT Bus Terminal Junction', lat: 15.8611, lng: 74.5123, qN: 42, qS: 35, qE: 28, qW: 20, base: 74.2, opt: 46.0 },
    { id: 'JNC-05', name: 'RPD College Cross', lat: 15.8340, lng: 74.5020, qN: 18, qS: 14, qE: 22, qW: 10, base: 45.0, opt: 29.8 },
    { id: 'JNC-19', name: 'KLE Hospital Main Gate', lat: 15.8902, lng: 74.5180, qN: 30, qS: 28, qE: 35, qW: 24, base: 62.0, opt: 38.4 }
  ];

  for (const s of initialSignals) {
    insertSignal.run(s.id, s.name, s.lat, s.lng, s.qN, s.qS, s.qE, s.qW, s.base, s.opt);
  }
}

export default db;
