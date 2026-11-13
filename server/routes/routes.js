import express from 'express';
import { calculateMultiFactorRoutes } from '../services/graphEngine.js';
import { getCongestionHeatmap } from '../services/mlPredictor.js';

const router = express.Router();

// POST /api/routes/calculate
router.post('/calculate', async (req, res) => {
  try {
    const { 
      originNodeId, 
      destinationNodeId, 
      origin, 
      destination, 
      departureOffsetMinutes = 0 
    } = req.body;

    const fromParam = origin || originNodeId || 1;
    const toParam = destination || destinationNodeId || 98;

    const result = await calculateMultiFactorRoutes(fromParam, toParam, departureOffsetMinutes);
    res.status(200).json({ status: 200, data: result });
  } catch (error) {
    console.error("Routing error:", error);
    res.status(500).json({ status: 500, message: "Internal routing computation error", error: error.message });
  }
});

// GET /api/predictions/heatmap
router.get('/heatmap', (req, res) => {
  const windowMinutes = parseInt(req.query.window || '30', 10);
  const data = getCongestionHeatmap(windowMinutes);
  res.status(200).json({ status: 200, data });
});

export default router;
