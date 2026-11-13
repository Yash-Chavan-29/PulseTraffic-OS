import express from 'express';
import db, { 
  recordIncidentReport,
  saveOrUpdateIncident,
  getActiveIncidents, 
  getIncidentById,
  updateIncidentStatus,
  updateDuplicateRelationship,
  saveRoadClosureSimulation,
  deactivateRoadClosureSimulation,
  getActiveRoadClosureSimulations,
  getIncidentStatistics,
  calculateIncidentSeverity
} from '../db/database.js';
import { 
  registerIncidentOnGraph, 
  removeIncidentFromGraph,
  simulateRoadClosure,
  restoreRoadClosure,
  calculateDiversionRoute,
  analyzeNetworkImpact,
  getActiveSimulationsOnGraph,
  ROAD_NODES,
  ROAD_EDGES,
  runAStar
} from '../services/graphEngine.js';

const router = express.Router();

/**
 * Validation helper for incident inputs
 */
function validateIncidentInput(body) {
  const errors = [];
  const type = body.type || (body.disruptionType);
  const location = body.location || {};
  const lat = body.lat !== undefined ? body.lat : location.lat;
  const lng = body.lng !== undefined ? body.lng : location.lng;

  if (lat === undefined || lat === null || isNaN(parseFloat(lat))) {
    errors.push("Valid latitude is required (-90 to 90)");
  } else if (parseFloat(lat) < -90 || parseFloat(lat) > 90) {
    errors.push("Latitude must be between -90 and 90");
  }

  if (lng === undefined || lng === null || isNaN(parseFloat(lng))) {
    errors.push("Valid longitude is required (-180 to 180)");
  } else if (parseFloat(lng) < -180 || parseFloat(lng) > 180) {
    errors.push("Longitude must be between -180 and 180");
  }

  const validTypes = [
    'accident', 'vehicle_breakdown', 'breakdown', 'road_construction', 'construction',
    'road_closure', 'lane_blockage', 'flooding', 'traffic_obstruction', 'hazard', 'other'
  ];
  if (type && !validTypes.includes(String(type).toLowerCase())) {
    errors.push(`Disruption type must be one of: ${validTypes.slice(0, 8).join(', ')}`);
  }

  return {
    isValid: errors.length === 0,
    errors,
    sanitized: {
      lat: parseFloat(lat),
      lng: parseFloat(lng),
      type: type ? String(type).toLowerCase() : 'accident'
    }
  };
}

/**
 * GET /api/incidents/statistics
 * System-wide incident and network disruption KPIs
 */
router.get('/statistics', (req, res) => {
  try {
    const stats = getIncidentStatistics();
    const activeSims = getActiveSimulationsOnGraph();
    res.status(200).json({
      status: 200,
      data: {
        ...stats,
        activeSimulatedClosures: activeSims.length,
        networkEngineStatus: 'ONLINE'
      }
    });
  } catch (err) {
    res.status(500).json({ status: 500, error: err.message });
  }
});

/**
 * GET /api/incidents
 * Query verified incidents with filter and search capabilities
 */
router.get('/', (req, res) => {
  try {
    const { type, status, severityCategory, search } = req.query;
    const rawIncidents = getActiveIncidents({ type, status, severityCategory, search });

    const incidents = rawIncidents.map(inc => {
      let factors = [];
      try { factors = JSON.parse(inc.severity_factors || '[]'); } catch (e) {}

      return {
        id: inc.id,
        title: inc.title || `${inc.type.toUpperCase()} on ${inc.road_segment_id || 'Corridor'}`,
        type: inc.type,
        severity: inc.severity,
        severityCategory: inc.severity_category || (inc.severity >= 4 ? 'CRITICAL' : inc.severity === 3 ? 'HIGH' : inc.severity === 2 ? 'MEDIUM' : 'LOW'),
        severityScore: inc.severity_score || (inc.severity * 24),
        severityFactors: factors,
        responsePriority: inc.response_priority || (inc.severity >= 3 ? 'High Priority' : 'Standard'),
        lat: inc.lat,
        lng: inc.lng,
        roadSegmentId: inc.road_segment_id,
        affectedRoadName: inc.affected_road_name || inc.description || inc.road_segment_id,
        roadName: inc.description || inc.road_segment_id || "Active Traffic Event",
        description: inc.description,
        reportedBy: inc.reported_by,
        status: inc.status,
        confirmations: inc.confirmations || 1,
        isDuplicate: Boolean(inc.is_duplicate),
        parentIncidentId: inc.parent_incident_id,
        duplicateConfidence: inc.duplicate_confidence || 0,
        duplicateReason: inc.duplicate_reason,
        lanesBlocked: inc.lanes_blocked || 1,
        totalLanes: inc.total_lanes || 3,
        estimatedDurationMin: inc.estimated_duration_min || 45,
        delayImpactMin: Number((inc.severity * 2.8).toFixed(1)),
        capacityReductionPercent: Math.min(95, inc.severity * 22),
        timestamp: inc.created_at,
        updatedAt: inc.updated_at
      };
    });

    res.status(200).json({
      status: 200,
      count: incidents.length,
      data: incidents
    });
  } catch (err) {
    res.status(500).json({ status: 500, error: err.message });
  }
});

/**
 * GET /api/incidents/active (Backward compatibility alias)
 */
router.get('/active', (req, res) => {
  try {
    const rawIncidents = getActiveIncidents();
    const incidents = rawIncidents.map(inc => ({
      id: inc.id,
      type: inc.type,
      severity: inc.severity,
      severityCategory: inc.severity_category || 'HIGH',
      lat: inc.lat,
      lng: inc.lng,
      roadName: inc.description || inc.road_segment_id || "Active Traffic Event",
      status: inc.status,
      confirmations: inc.confirmations || 1,
      delayImpactMin: Number((inc.severity * 2.8).toFixed(1)),
      capacityReductionPercent: Math.min(85, inc.severity * 22),
      timestamp: inc.created_at
    }));

    res.status(200).json({ status: 200, data: incidents });
  } catch (err) {
    res.status(500).json({ status: 500, error: err.message });
  }
});

/**
 * POST /api/incidents
 * Full incident reporting with validation, intelligent deduplication, and severity calculation
 */
router.post('/', (req, res) => {
  const validation = validateIncidentInput(req.body);
  if (!validation.isValid) {
    return res.status(400).json({
      status: 400,
      error: "Validation Failed",
      messages: validation.errors
    });
  }

  const {
    title = '',
    description = '',
    roadSegmentId = 'BEL-CORRIDOR-01',
    affectedRoadName = 'Belagavi City Arterial',
    lanesBlocked = 1,
    totalLanes = 3,
    estimatedDurationMin = 45,
    reportedBy = 'Citizen',
    roadType = 'arterial',
    isEmergencyCorridor = false
  } = req.body;

  const { lat, lng, type } = validation.sanitized;

  try {
    const result = recordIncidentReport({
      title: title || `${type.toUpperCase()} on ${affectedRoadName}`,
      type,
      description: description || title || 'Reported road disruption',
      lat,
      lng,
      roadSegmentId,
      affectedRoadName,
      lanesBlocked: parseInt(lanesBlocked) || 1,
      totalLanes: parseInt(totalLanes) || 3,
      estimatedDurationMin: parseInt(estimatedDurationMin) || 45,
      reportedBy,
      roadType,
      isEmergencyCorridor: Boolean(isEmergencyCorridor)
    });

    const incidentPayload = {
      id: result.incidentId,
      reportId: result.reportId,
      type,
      severity: result.severity,
      severityCategory: result.severityCategory,
      severityScore: result.severityScore,
      severityFactors: result.severityFactors,
      responsePriority: result.responsePriority,
      recommendedAction: result.recommendedAction,
      lat: result.lat,
      lng: result.lng,
      roadSegmentId: result.roadSegmentId,
      affectedRoadName: result.affectedRoadName,
      roadName: result.description || "Reported Traffic Incident",
      status: result.status,
      confirmations: result.confirmations,
      isDuplicate: result.isDuplicate,
      parentIncidentId: result.parentIncidentId,
      duplicateConfidence: result.duplicateConfidence,
      duplicateReasons: result.duplicateReasons,
      delayImpactMin: Number((result.severity * 2.8).toFixed(1)),
      capacityReductionPercent: Math.min(90, result.severity * 22),
      timestamp: new Date().toISOString()
    };

    // Register on the active graph
    registerIncidentOnGraph(incidentPayload);

    // Real-time Socket.IO broadcasts
    const io = req.app.get('io');
    if (io) {
      if (result.isDuplicate) {
        io.emit('incident:duplicate', incidentPayload);
      } else {
        io.emit('incident:new', incidentPayload);
      }
      io.emit('reroute:triggered', {
        reason: `Incident reported at (${lat.toFixed(4)}, ${lng.toFixed(4)})`,
        incidentId: result.incidentId
      });
    }

    res.status(201).json({
      status: 201,
      message: result.isDuplicate 
        ? "Potential duplicate report identified and linked to existing cluster" 
        : "New incident registered and broadcast successfully",
      data: {
        incidentId: result.incidentId,
        reportId: result.reportId,
        isDuplicate: result.isDuplicate,
        duplicateConfidence: result.duplicateConfidence,
        duplicateReasons: result.duplicateReasons,
        parentIncidentId: result.parentIncidentId,
        confirmations: result.confirmations,
        status: result.status,
        severity: result.severity,
        severityCategory: result.severityCategory,
        severityScore: result.severityScore,
        severityFactors: result.severityFactors,
        responsePriority: result.responsePriority,
        recommendedAction: result.recommendedAction,
        estimatedClearanceTimeMin: result.estimatedDurationMin || 45,
        networkImpact: {
          affectedRoads: [roadSegmentId, affectedRoadName],
          capacityReductionPercent: Math.min(90, result.severity * 22),
          diversionRecommended: result.severity >= 3,
          diversionRouteId: "BYPASS-BEL-01",
          timePenaltyAddedMinutes: Number((result.severity * 2.8).toFixed(1))
        }
      }
    });
  } catch (err) {
    res.status(500).json({ status: 500, error: err.message });
  }
});

/**
 * POST /api/incidents/report (Backward compatibility alias)
 */
router.post('/report', (req, res) => {
  // Re-routes through primary POST /api/incidents
  return router.handle(Object.assign(req, { url: '/' }), res);
});

/**
 * GET /api/incidents/:id
 * Retrieve single incident details with complete audit trail & linked reports
 */
router.get('/:id', (req, res) => {
  try {
    const { id } = req.params;
    const incident = getIncidentById(id);

    if (!incident) {
      return res.status(404).json({ status: 404, message: `Incident ${id} not found` });
    }

    res.status(200).json({ status: 200, data: incident });
  } catch (err) {
    res.status(500).json({ status: 500, error: err.message });
  }
});

/**
 * PATCH /api/incidents/:id/status
 * Administrative status update (unverified, verified, resolved, rejected)
 */
router.patch('/:id/status', (req, res) => {
  const { id } = req.params;
  const { status, changedBy = 'Admin', notes = '' } = req.body;

  const validStatuses = ['unverified', 'verified', 'resolved', 'rejected'];
  if (!validStatuses.includes(status)) {
    return res.status(400).json({
      status: 400,
      message: `Invalid status. Must be one of: ${validStatuses.join(', ')}`
    });
  }

  try {
    const updated = updateIncidentStatus(id, status, changedBy, notes);
    if (!updated) {
      return res.status(404).json({ status: 404, message: "Incident not found" });
    }

    if (status === 'resolved' || status === 'rejected') {
      removeIncidentFromGraph(id);
    }

    const io = req.app.get('io');
    if (io) {
      io.emit('incident:status', { id, status, changedBy, notes });
      io.emit('reroute:triggered', {
        reason: `Incident ${id} status updated to ${status}`,
        incidentId: id
      });
    }

    res.status(200).json({
      status: 200,
      message: `Incident ${id} updated to ${status}`,
      data: updated
    });
  } catch (err) {
    res.status(500).json({ status: 500, error: err.message });
  }
});

/**
 * PATCH /api/incidents/:id/duplicate
 * Administrative confirmation or rejection of duplicate link
 */
router.patch('/:id/duplicate', (req, res) => {
  const { id } = req.params;
  const { action = 'confirm', parentId } = req.body; // 'confirm' or 'reject'

  try {
    const updated = updateDuplicateRelationship(id, {
      isDuplicate: action === 'confirm',
      parentId,
      action
    });

    if (!updated) {
      return res.status(404).json({ status: 404, message: "Incident not found" });
    }

    const io = req.app.get('io');
    if (io) {
      io.emit('incident:update', { id, action, isDuplicate: action === 'confirm' });
    }

    res.status(200).json({
      status: 200,
      message: `Duplicate status for ${id} ${action}ed successfully`,
      data: updated
    });
  } catch (err) {
    res.status(500).json({ status: 500, error: err.message });
  }
});

/**
 * GET /api/incidents/:id/impact
 * Graph-based road network impact and corridor disruption analysis
 */
router.get('/:id/impact', (req, res) => {
  try {
    const { id } = req.params;
    const inc = db.prepare('SELECT * FROM incidents WHERE id = ?').get(id);

    if (!inc) {
      return res.status(404).json({ status: 404, message: "Incident not found" });
    }

    const impact = analyzeNetworkImpact({
      roadSegmentId: inc.road_segment_id || 'E01',
      severity: inc.severity || 3,
      closed: inc.closure_type === 'full_closure'
    });

    res.status(200).json({
      status: 200,
      data: {
        incidentId: id,
        type: inc.type,
        severity: inc.severity,
        severityCategory: inc.severity_category || 'HIGH',
        roadSegment: inc.road_segment_id,
        ...impact
      }
    });
  } catch (err) {
    res.status(500).json({ status: 500, error: err.message });
  }
});

/**
 * GET /api/incidents/:id/diversions
 * Automated alternative route calculation avoiding incident or closed road
 */
router.get('/:id/diversions', (req, res) => {
  try {
    const { id } = req.params;
    const { origin = 'kle_tech', destination = 'sambre_airport' } = req.query;

    const inc = db.prepare('SELECT * FROM incidents WHERE id = ?').get(id);
    if (!inc) {
      return res.status(404).json({ status: 404, message: "Incident not found" });
    }

    const diversion = calculateDiversionRoute(origin, destination, 0);

    res.status(200).json({
      status: 200,
      data: {
        incidentId: id,
        ...diversion
      }
    });
  } catch (err) {
    res.status(500).json({ status: 500, error: err.message });
  }
});

/**
 * POST /api/incidents/simulate-closure or POST /api/incidents/:id/simulate-closure
 * Interactive Road Closure & Partial Blockage Simulator (Reversible)
 */
const handleSimulateClosure = (req, res) => {
  const {
    roadSegmentId = req.params.id || 'E01',
    closureType = 'full_closure', // 'full_closure' or 'partial_blockage'
    blockedLanes = 2,
    totalLanes = 3,
    capacityReductionPercent = 100,
    durationMin = 60,
    notes = 'Administrative simulation'
  } = req.body;

  try {
    const simResult = simulateRoadClosure({
      roadSegmentId,
      closureType,
      blockedLanes: parseInt(blockedLanes) || 2,
      totalLanes: parseInt(totalLanes) || 3,
      capacityReductionPercent: parseInt(capacityReductionPercent) || 100,
      durationMin: parseInt(durationMin) || 60
    });

    // Save simulation record
    saveRoadClosureSimulation({
      roadSegmentId,
      incidentId: req.params.id || null,
      closureType,
      blockedLanes: parseInt(blockedLanes) || 2,
      totalLanes: parseInt(totalLanes) || 3,
      capacityReductionPercent: parseInt(capacityReductionPercent) || 100,
      estimatedDurationMin: parseInt(durationMin) || 60,
      notes
    });

    // Calculate network diversion recommendation
    const sampleDiversion = calculateDiversionRoute('kle_tech', 'sambre_airport', 0);

    // Socket.IO broadcast
    const io = req.app.get('io');
    if (io) {
      io.emit('network:closure', {
        roadSegmentId,
        closureType,
        blockedLanes,
        totalLanes,
        simResult
      });
      io.emit('reroute:triggered', {
        reason: `Road closure active on ${roadSegmentId}`,
        roadSegmentId
      });
    }

    res.status(200).json({
      status: 200,
      message: `Road ${roadSegmentId} ${closureType === 'full_closure' ? 'closed completely' : 'partially blocked'} in graph simulator`,
      data: {
        ...simResult,
        recommendedDiversion: sampleDiversion
      }
    });
  } catch (err) {
    res.status(500).json({ status: 500, error: err.message });
  }
};

router.post('/simulate-closure', handleSimulateClosure);
router.post('/:id/simulate-closure', handleSimulateClosure);

/**
 * POST /api/incidents/restore-road or POST /api/incidents/:id/restore-road
 * Restore road back to normal baseline capacity (Reverses simulation)
 */
const handleRestoreRoad = (req, res) => {
  const roadSegmentId = req.body.roadSegmentId || req.params.id || 'all';

  try {
    const restoreResult = restoreRoadClosure(roadSegmentId);
    deactivateRoadClosureSimulation(roadSegmentId);

    const io = req.app.get('io');
    if (io) {
      io.emit('network:restore', {
        roadSegmentId,
        restoreResult
      });
      io.emit('reroute:triggered', {
        reason: `Road ${roadSegmentId} restored to normal capacity`,
        roadSegmentId
      });
    }

    res.status(200).json({
      status: 200,
      message: `Road ${roadSegmentId} successfully restored to baseline network capacity`,
      data: restoreResult
    });
  } catch (err) {
    res.status(500).json({ status: 500, error: err.message });
  }
};

router.post('/restore-road', handleRestoreRoad);
router.post('/:id/restore-road', handleRestoreRoad);

/**
 * GET /api/incidents/simulations/active
 * View currently active simulated disruptions
 */
router.get('/simulations/active', (req, res) => {
  try {
    const activeOnGraph = getActiveSimulationsOnGraph();
    const activeInDB = getActiveRoadClosureSimulations();

    res.status(200).json({
      status: 200,
      data: {
        activeGraphSimulations: activeOnGraph,
        activeDatabaseSimulations: activeInDB
      }
    });
  } catch (err) {
    res.status(500).json({ status: 500, error: err.message });
  }
});

export default router;