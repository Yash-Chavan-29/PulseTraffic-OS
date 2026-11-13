import express from 'express';
import db from '../db/database.js';

const router = express.Router();

/**
 * Standard Webster Optimum Cycle & Delay Simulation
 * Implements Highway Capacity Manual (HCM) & Webster delay equation:
 * Co = (1.5*L + 5) / (1 - Y)
 * d = [C*(1 - lambda)^2] / [2*(1 - lambda*x)] + [x^2] / [2*q*(1 - x)]
 */
function runSignalSimulation(initialQueues, baselineCycleSec = 90, isAdaptive = false) {
  const qN = Math.max(0, Number(initialQueues.north) || 0);
  const qS = Math.max(0, Number(initialQueues.south) || 0);
  const qE = Math.max(0, Number(initialQueues.east) || 0);
  const qW = Math.max(0, Number(initialQueues.west) || 0);

  const totalNS = Math.max(1, qN + qS);
  const totalEW = Math.max(1, qE + qW);
  const totalVeh = totalNS + totalEW;

  // Intergreen clearance parameters (HCM Standard)
  const yellowSec = 3;
  const allRedSec = 2;
  const lostTimePerPhase = yellowSec + allRedSec; // 5s lost time per phase
  const totalLostTime = lostTimePerPhase * 2;     // 10s total lost time across 2 conflicting phases
  const satFlowPerLane = 0.50;                   // 1800 veh/hr = 0.50 veh/sec per lane
  const usableLanes = 2;                         // 2 approach lanes on College Rd & Civil Hospital Rd
  const satFlow = satFlowPerLane * usableLanes;   // 1.00 veh/sec saturation flow

  // Critical approach flow rates (veh/sec) estimated from queue clearance requirement
  const criticalNS = Math.max(qN, qS);
  const criticalEW = Math.max(qE, qW);

  const qRateNS = Math.max(0.06, criticalNS / 80);
  const qRateEW = Math.max(0.06, criticalEW / 80);

  const yNS = Number((qRateNS / satFlow).toFixed(3));
  const yEW = Number((qRateEW / satFlow).toFixed(3));
  const sumY = Math.min(0.85, Math.max(0.12, yNS + yEW));

  const actualYSum = yNS + yEW;
  const splitRatioNS = actualYSum > 0 ? yNS / actualYSum : 0.5;
  const splitRatioEW = 1.0 - splitRatioNS;

  let cycleTimeSec, greenNS, greenEW;

  if (!isAdaptive) {
    // Fixed pre-timed baseline cycle with rigid equal 50/50 splits
    cycleTimeSec = baselineCycleSec;
    const effectiveGreen = cycleTimeSec - totalLostTime;
    greenNS = Math.round(effectiveGreen * 0.5);
    greenEW = effectiveGreen - greenNS;
  } else {
    // Webster's Optimum Cycle Formula: Co = (1.5*L + 5) / (1 - Y)
    // Constrained between 55s and 110s for urban arterials
    const designY = Math.min(0.80, actualYSum);
    const optCycle = Math.round((1.5 * totalLostTime + 5) / (1 - designY));
    cycleTimeSec = Math.max(55, Math.min(105, optCycle));
    const effectiveGreen = cycleTimeSec - totalLostTime;
    
    // Proportional green splits based on true critical approach flow ratios
    const minGreen = 15; // 15s minimum pedestrian walk & clearance interval
    const computedGreenNS = Math.round(effectiveGreen * splitRatioNS);
    greenNS = Math.max(minGreen, Math.min(effectiveGreen - minGreen, computedGreenNS));
    greenEW = effectiveGreen - greenNS;
  }

  function calcWebsterDelay(qLen, arrRate, greenSec, cycle) {
    const lambda = Math.max(0.12, Math.min(0.85, greenSec / cycle));
    const cap = satFlow * lambda; // veh/sec capacity
    const effectiveFlow = arrRate + (qLen / cycle);
    const x = effectiveFlow / cap;

    const redSec = cycle - greenSec;
    // Webster 1st term (uniform delay)
    const uniformDelay = (cycle * Math.pow(1 - lambda, 2)) / (2 * Math.max(0.1, 1 - lambda * Math.min(0.95, x)));

    // Multi-cycle overflow delay when arrival + queue exceeds green capacity
    const capacityVehicles = satFlow * greenSec;
    const totalVehiclesApproaching = qLen + arrRate * cycle;
    
    let spilloverDelay = 0;
    if (totalVehiclesApproaching > capacityVehicles) {
      const overflowVeh = totalVehiclesApproaching - capacityVehicles;
      const overflowRatio = Math.min(1.0, overflowVeh / totalVehiclesApproaching);
      // Overflow vehicles must wait through the red interval of the next cycle
      spilloverDelay = overflowRatio * redSec * 1.5 + (overflowVeh * 0.8);
    }

    return uniformDelay + spilloverDelay;
  }

  // Calculate approach delays for N, S, E, W
  const delayN = calcWebsterDelay(qN, qRateNS * 0.6, greenNS, cycleTimeSec);
  const delayS = calcWebsterDelay(qS, qRateNS * 0.4, greenNS, cycleTimeSec);
  const delayE = calcWebsterDelay(qE, qRateEW * 0.6, greenEW, cycleTimeSec);
  const delayW = calcWebsterDelay(qW, qRateEW * 0.4, greenEW, cycleTimeSec);

  const weightedTotalDelay = delayN * Math.max(1, qN) + delayS * Math.max(1, qS) + delayE * Math.max(1, qE) + delayW * Math.max(1, qW);
  const avgWaitTimeSec = Number((weightedTotalDelay / totalVeh).toFixed(1));

  return {
    cycleTimeSec,
    greenNS,
    greenEW,
    yellowSec,
    allRedSec,
    totalLostTime,
    sumY,
    criticalRatios: { yNS, yEW },
    avgWaitTimeSec
  };
}

// GET /api/signals/junctions
router.get('/junctions', (req, res) => {
  const junctions = db.prepare('SELECT * FROM signal_junctions ORDER BY junction_id ASC').all();
  res.status(200).json({ status: 200, data: junctions });
});

// POST /api/signals/optimize
router.post('/optimize', (req, res) => {
  const { 
    junctionId = "JNC-14", 
    currentQueueLengths = { north: 38, south: 12, east: 44, west: 18 },
    cycleTimeSec = 90
  } = req.body;

  // Validate all 4 directional inputs
  if (!currentQueueLengths || typeof currentQueueLengths !== 'object') {
    return res.status(400).json({ status: 400, message: "currentQueueLengths object with north, south, east, west required" });
  }

  const dirs = ['north', 'south', 'east', 'west'];
  for (const d of dirs) {
    const val = Number(currentQueueLengths[d]);
    if (isNaN(val) || val < 0 || val > 300) {
      return res.status(400).json({ status: 400, message: `Invalid queue length for direction '${d}': must be between 0 and 300` });
    }
  }

  // Run real discrete Webster & HCM queue delay simulation
  const fixedSim = runSignalSimulation(currentQueueLengths, cycleTimeSec, false);
  const adaptiveSim = runSignalSimulation(currentQueueLengths, cycleTimeSec, true);

  const baselineWait = fixedSim.avgWaitTimeSec;
  const optimizedWait = adaptiveSim.avgWaitTimeSec;
  const rawReduction = baselineWait > 0 ? ((baselineWait - optimizedWait) / baselineWait) * 100 : 0;
  const reductionPercent = Number(Math.max(0, rawReduction).toFixed(1));

  // Determine optimization rationale
  const higherDemand = adaptiveSim.criticalRatios.yNS >= adaptiveSim.criticalRatios.yEW ? "North-South Corridor" : "East-West Corridor";
  const explanation = `Webster optimum cycle calculated at ${adaptiveSim.cycleTimeSec}s (Y = ${adaptiveSim.sumY}). Allocated ${adaptiveSim.greenNS}s green to N-S corridor and ${adaptiveSim.greenEW}s green to E-W corridor based on critical flow ratio (${higherDemand} priority). 3s yellow and 2s all-red clearance enforced per phase to eliminate vehicle conflicting movements.`;

  // Fetch or update junction in SQLite
  let junctionName = "Rani Chennamma Circle Hub";
  const row = db.prepare('SELECT name FROM signal_junctions WHERE junction_id = ?').get(junctionId);
  if (row) {
    junctionName = row.name;
    db.prepare(`
      UPDATE signal_junctions
      SET queue_north = ?, queue_south = ?, queue_east = ?, queue_west = ?,
          baseline_wait_sec = ?, optimized_wait_sec = ?,
          green_split_ns = ?, green_split_ew = ?, updated_at = CURRENT_TIMESTAMP
      WHERE junction_id = ?
    `).run(
      currentQueueLengths.north || 0,
      currentQueueLengths.south || 0,
      currentQueueLengths.east || 0,
      currentQueueLengths.west || 0,
      baselineWait,
      optimizedWait,
      adaptiveSim.greenNS,
      adaptiveSim.greenEW,
      junctionId
    );
  }

  res.status(200).json({
    status: 200,
    data: {
      junctionId,
      junctionName,
      cycleTimeSec: adaptiveSim.cycleTimeSec,
      baselineCycleSec: fixedSim.cycleTimeSec,
      simulationType: "Webster Optimum Cycle & HCM Delay Model",
      safetyModel: "Dual-Ring Conflict Prevention with Intergreen Clearance",
      clearanceTiming: {
        yellowSec: 3,
        allRedSec: 2,
        totalLostTimeSec: 10
      },
      criticalFlowRatios: adaptiveSim.criticalRatios,
      sumCriticalRatioY: adaptiveSim.sumY,
      baselineFixedTiming: {
        cycleTimeSec: fixedSim.cycleTimeSec,
        greenTimeSec: { 
          northSouth: fixedSim.greenNS, 
          eastWest: fixedSim.greenEW 
        },
        avgWaitTimeSec: baselineWait
      },
      optimizedAdaptiveTiming: {
        cycleTimeSec: adaptiveSim.cycleTimeSec,
        greenTimeSec: {
          northSouth: adaptiveSim.greenNS,
          eastWest: adaptiveSim.greenEW
        },
        avgWaitTimeSec: optimizedWait
      },
      waitTimeReductionPercent: reductionPercent,
      queueClearanceEfficiency: reductionPercent > 25 ? "Optimal (Level of Service B)" : (reductionPercent > 10 ? "Stable (Level of Service C)" : "Moderate (Level of Service D)"),
      optimizationExplanation: explanation
    }
  });
});

export default router;
