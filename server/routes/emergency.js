import express from 'express';

const router = express.Router();

// POST /api/emergency/corridor
router.post('/corridor', (req, res) => {
  const { vehicleType = "ambulance", priorityLevel = 1, originNode = 14, hospitalDestinationNode = 88 } = req.body;

  const normalTime = 22.4;
  const corridorTime = 9.8;
  const savedMin = Number((normalTime - corridorTime).toFixed(1));
  const savedPercent = Number(((savedMin / normalTime) * 100).toFixed(1));

  res.status(200).json({
    status: 200,
    data: {
      corridorId: `EMG-CORR-${Math.floor(10 + Math.random() * 90)}`,
      status: "GREEN_WAVE_ACTIVE",
      normalTravelTimeMin: normalTime,
      emergencyCorridorTimeMin: corridorTime,
      timeSavedMin: savedMin,
      timeSavedPercent: savedPercent,
      preemptedJunctions: [
        { id: "JNC-14", name: "Tech Park Gateway", preemptInSec: 0, status: "LOCKED_GREEN" },
        { id: "JNC-22", name: "HAL Airport Road", preemptInSec: 90, status: "QUEUED_PREEMPTION" },
        { id: "JNC-38", name: "Trinity Circle Hospital Gate", preemptInSec: 210, status: "QUEUED_PREEMPTION" }
      ]
    }
  });
});

export default router;
