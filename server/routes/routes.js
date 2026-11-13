import express from 'express';
import { calculateMultiFactorRoutes } from '../services/graphEngine.js';
import { getCongestionHeatmap } from '../services/mlPredictor.js';

const router = express.Router();

// POST /api/routes/calculate
router.post('/calculate', (req, res) => {
  const { originNodeId = 1, destinationNodeId = 98, departureOffsetMinutes = 0 } = req.body;
  const result = calculateMultiFactorRoutes(originNodeId, destinationNodeId, departureOffsetMinutes);
  res.status(200).json({ status: 200, data: result });
});

// GET /api/predictions/heatmap
router.get('/heatmap', (req, res) => {
  const windowMinutes = parseInt(req.query.window || '30', 10);
  const data = getCongestionHeatmap(windowMinutes);
  res.status(200).json({ status: 200, data });
});

export default router;
