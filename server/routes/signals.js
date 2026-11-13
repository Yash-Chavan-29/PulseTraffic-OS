import express from 'express';

const router = express.Router();

// POST /api/signals/optimize
router.post('/optimize', (req, res) => {
  const { junctionId = "JNC-14", currentQueueLengths = { north: 38, south: 12, east: 44, west: 18 } } = req.body;

  const totalNorthSouth = (currentQueueLengths.north || 20) + (currentQueueLengths.south || 20);
  const totalEastWest = (currentQueueLengths.east || 20) + (currentQueueLengths.west || 20);
  const totalVehicles = totalNorthSouth + totalEastWest;

  // Cycle time = 120s
  const cycleTime = 120;
  const nsSplit = Math.round((totalNorthSouth / totalVehicles) * cycleTime);
  const ewSplit = cycleTime - nsSplit;

  // Wait time comparison
  const baselineWait = 68.4;
  const optimizedWait = Number((baselineWait * (1 - (Math.abs(nsSplit - ewSplit) / (cycleTime * 1.5)))).toFixed(1));
  const reductionPercent = Number((((baselineWait - optimizedWait) / baselineWait) * 100).toFixed(1));

  res.status(200).json({
    status: 200,
    data: {
      junctionId,
      junctionName: "Hebbal Flyover Junction",
      baselineFixedTiming: {
        greenTimeSec: { northSouth: 45, eastWest: 45 },
        avgWaitTimeSec: baselineWait
      },
      optimizedAdaptiveTiming: {
        greenTimeSec: {
          north: Math.round(nsSplit * 0.6),
          south: Math.round(nsSplit * 0.4),
          east: Math.round(ewSplit * 0.65),
          west: Math.round(ewSplit * 0.35)
        },
        avgWaitTimeSec: optimizedWait
      },
      waitTimeReductionPercent: reductionPercent,
      queueClearanceEfficiency: "Optimal (Level of Service B)"
    }
  });
});

export default router;
