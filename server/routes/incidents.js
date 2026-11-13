import express from 'express';
import { registerIncidentOnGraph } from '../services/graphEngine.js';

const router = express.Router();

let activeIncidents = [
  {
    id: "INC-8891",
    type: "accident",
    severity: 3,
    lat: 13.0358,
    lng: 77.5682,
    roadName: "Hebbal Flyover Expressway Ramp",
    delayImpactMin: 9.2,
    capacityReductionPercent: 65,
    timestamp: new Date().toISOString()
  },
  {
    id: "INC-8874",
    type: "roadblock",
    severity: 2,
    lat: 12.9850,
    lng: 77.6020,
    roadName: "Metro Pillar 14 Construction",
    delayImpactMin: 4.5,
    capacityReductionPercent: 30,
    timestamp: new Date(Date.now() - 3600000).toISOString()
  }
];

// GET /api/incidents/active
router.get('/active', (req, res) => {
  res.status(200).json({ status: 200, data: activeIncidents });
});

// POST /api/incidents/report
router.post('/report', (req, res) => {
  const { type = "accident", severity = 3, location = {}, description = "", reportedBy = "Citizen" } = req.body;

  // Deduplication Engine: Check within 150 meters (0.0015 deg lat/lng) & 30 minutes
  const now = Date.now();
  const isDuplicate = activeIncidents.some(inc => {
    if (!location.lat || !inc.lat) return false;
    const dLat = Math.abs(inc.lat - location.lat);
    const dLng = Math.abs(inc.lng - location.lng);
    const timeDiffMin = (now - new Date(inc.timestamp).getTime()) / 60000;
    return dLat < 0.002 && dLng < 0.002 && inc.type === type && timeDiffMin < 30;
  });

  const newIncidentId = `INC-${Math.floor(1000 + Math.random() * 9000)}`;
  const delayAdded = Number((severity * 3.1).toFixed(1));

  const incidentRecord = {
    incidentId: newIncidentId,
    isDuplicate,
    clusterIncidentId: isDuplicate ? activeIncidents[0].id : null,
    estimatedClearanceTimeMin: severity * 15,
    networkImpact: {
      affectedRoads: [location.roadSegmentId || "Hebbal Expressway North", "Ring Road Connector"],
      capacityReductionPercent: severity * 22,
      diversionRecommended: severity >= 2,
      diversionRouteId: "BYPASS-RING-01",
      timePenaltyAddedMinutes: delayAdded
    }
  };

  if (!isDuplicate) {
    const newInc = {
      id: newIncidentId,
      type,
      severity,
      lat: location.lat || 13.0358,
      lng: location.lng || 77.5682,
      roadName: description || "Reported Roadway Incident",
      delayImpactMin: delayAdded,
      capacityReductionPercent: severity * 22,
      timestamp: new Date().toISOString()
    };
    activeIncidents.unshift(newInc);
    registerIncidentOnGraph(newInc);

    // Emit live WebSocket notification if io is available
    if (req.app.get('io')) {
      req.app.get('io').emit('incident:new', newInc);
    }
  }

  res.status(201).json({ status: 201, data: incidentRecord });
});

export default router;
