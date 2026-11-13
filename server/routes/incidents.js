import express from 'express';
import { 
  saveOrUpdateIncident, 
  getActiveIncidents, 
  updateIncidentStatus 
} from '../db/database.js';
import { 
  registerIncidentOnGraph, 
  removeIncidentFromGraph,
  ROAD_NODES 
} from '../services/graphEngine.js';

const router = express.Router();

// GET /api/incidents/active
router.get('/active', (req, res) => {
  const incidents = getActiveIncidents().map(inc => ({
    id: inc.id,
    type: inc.type,
    severity: inc.severity,
    lat: inc.lat,
    lng: inc.lng,
    roadName: inc.description || inc.road_segment_id || "Active Traffic Event",
    status: inc.status,
    confirmations: inc.confirmations,
    delayImpactMin: Number((inc.severity * 2.8).toFixed(1)),
    capacityReductionPercent: Math.min(85, inc.severity * 22),
    timestamp: inc.created_at
  }));

  res.status(200).json({ status: 200, data: incidents });
});

// POST /api/incidents/report
router.post('/report', (req, res) => {
  const { 
    type = "accident", 
    severity = 3, 
    location = {}, 
    description = "", 
    reportedBy = "Citizen" 
  } = req.body;

  const lat = location.lat || 15.8497;
  const lng = location.lng || 74.5089;
  const incidentId = `INC-${Math.floor(1000 + Math.random() * 9000)}`;

  const result = saveOrUpdateIncident({
    id: incidentId,
    type,
    severity,
    lat,
    lng,
    roadSegmentId: location.roadSegmentId || "BEL-CORRIDOR-01",
    description: description || "Reported road obstruction",
    reportedBy
  });

  const incidentPayload = {
    id: result.incidentId,
    type,
    severity,
    lat,
    lng,
    roadName: description || "Reported Traffic Incident",
    status: result.status,
    confirmations: result.confirmations,
    delayImpactMin: Number((severity * 3.1).toFixed(1)),
    capacityReductionPercent: Math.min(85, severity * 22),
    timestamp: new Date().toISOString()
  };

  // Register incident on the graph engine
  registerIncidentOnGraph(incidentPayload);

  const io = req.app.get('io');
  if (io) {
    io.emit('incident:new', incidentPayload);
    io.emit('reroute:triggered', {
      reason: `Incident reported at (${lat.toFixed(4)}, ${lng.toFixed(4)})`,
      incidentId: result.incidentId
    });
  }

  res.status(201).json({
    status: 201,
    data: {
      incidentId: result.incidentId,
      isDuplicate: result.deduplicated,
      clusterIncidentId: result.clusterIncidentId,
      confirmations: result.confirmations,
      status: result.status,
      estimatedClearanceTimeMin: severity * 15,
      networkImpact: {
        affectedRoads: [location.roadSegmentId || "Chennamma-PB Road Arterial"],
        capacityReductionPercent: Math.min(85, severity * 22),
        diversionRecommended: severity >= 2,
        diversionRouteId: "BYPASS-BEL-01",
        timePenaltyAddedMinutes: Number((severity * 3.1).toFixed(1))
      }
    }
  });
});

// PATCH /api/incidents/:id/status
router.patch('/:id/status', (req, res) => {
  const { id } = req.params;
  const { status } = req.body; // 'verified', 'resolved', 'rejected'

  if (!['verified', 'resolved', 'rejected', 'unverified'].includes(status)) {
    return res.status(400).json({ status: 400, message: "Invalid status value" });
  }

  const updated = updateIncidentStatus(id, status);
  if (!updated) {
    return res.status(404).json({ status: 404, message: "Incident not found" });
  }

  if (status === 'resolved' || status === 'rejected') {
    removeIncidentFromGraph(id);
  }

  const io = req.app.get('io');
  if (io) {
    io.emit('incident:status', { id, status });
    if (status === 'resolved') {
      io.emit('reroute:triggered', {
        reason: `Incident ${id} cleared`,
        incidentId: id
      });
    }
  }

  res.status(200).json({
    status: 200,
    message: `Incident ${id} updated to ${status}`,
    data: updated
  });
});

export default router;
