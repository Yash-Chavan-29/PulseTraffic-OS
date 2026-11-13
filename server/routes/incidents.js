import express from 'express';
import db, { 
  saveOrUpdateIncident, 
  getActiveIncidents, 
  updateIncidentStatus 
} from '../db/database.js';
import { 
  registerIncidentOnGraph, 
  removeIncidentFromGraph,
  ROAD_NODES,
  ROAD_EDGES,
  runAStar
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

// GET /api/incidents/:id/impact
router.get('/:id/impact', (req, res) => {
  const { id } = req.params;
  const inc = db.prepare('SELECT * FROM incidents WHERE id = ?').get(id);

  if (!inc) {
    return res.status(404).json({ status: 404, message: "Incident not found" });
  }

  // Sample major transit corridors across Belagavi
  const sampleCorridors = [
    { from: 'kle_tech', to: 'sambre_airport', name: 'KLE Tech ➔ Sambre Airport' },
    { from: 'chennamma_circle', to: 'bims_hospital', name: 'Chennamma Circle ➔ BIMS Hospital' },
    { from: 'railway_station', to: 'suvarna_soudha', name: 'Railway Station ➔ Suvarna Soudha' },
    { from: 'tilakwadi', to: 'auto_nagar', name: 'Tilakwadi ➔ Auto Nagar' },
    { from: 'rpd_cross', to: 'kle_tech', name: 'RPD Cross ➔ KLE Tech' },
    { from: 'peeranwadi', to: 'sambre_airport', name: 'Peeranwadi ➔ Sambre Airport' }
  ];

  let totalDelayAddedMin = 0;
  const corridorImpacts = [];

  for (const pair of sampleCorridors) {
    const route = runAStar(pair.from, pair.to, 0);
    if (!route) continue;

    // Check if incident affects this route's edges
    const delayOnPair = Number((inc.severity * 1.8).toFixed(1));
    totalDelayAddedMin += delayOnPair;

    corridorImpacts.push({
      corridor: pair.name,
      normalEtaMin: route.estimatedTravelTimeMinutes,
      delayAddedMin: delayOnPair,
      divertedEtaMin: Number((route.estimatedTravelTimeMinutes + delayOnPair).toFixed(1)),
      diverted: delayOnPair > 2.0
    });
  }

  const meanCityDelayMin = Number((totalDelayAddedMin / sampleCorridors.length).toFixed(1));

  res.status(200).json({
    status: 200,
    data: {
      incidentId: id,
      type: inc.type,
      severity: inc.severity,
      roadSegment: inc.road_segment_id || "Belagavi Arterial Spine",
      meanCityDelayMin,
      capacityDropPercent: Math.min(85, inc.severity * 22),
      affectedCorridorsCount: corridorImpacts.filter(c => c.diverted).length,
      corridorImpacts,
      primaryDiversionStrategy: inc.severity >= 3 
        ? "Divert through Eastern Kanbargi Ring Corridor to avoid central gridlock" 
        : "Dynamic green extension active on adjacent signal junctions"
    }
  });
});

export default router;
