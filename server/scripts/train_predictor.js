/**
 * PulseTraffic ML Training Pipeline: Congestion Index Regressor
 * Generates 30-day realistic urban sensor observations (Belagavi telemetry profile).
 * Performs 80/20 train/test holdout split and fits multi-feature Ridge Regressor.
 * Saves model weights and real evaluation metrics (MAE, RMSE, R²) to server/data/traffic_model.json.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Synthetic 30-Day Urban Traffic Profile Generator
function generateDataset() {
  const records = [];
  const roadClasses = ['highway', 'arterial', 'downtown'];
  const weathers = ['clear', 'rain', 'fog'];

  // Base diurnal pattern (0-23)
  const hourlyCurve = [
    0.10, 0.08, 0.06, 0.05, 0.08, 0.18,
    0.42, 0.74, 0.88, 0.82, 0.62, 0.52,
    0.48, 0.46, 0.50, 0.58, 0.72, 0.90,
    0.86, 0.74, 0.55, 0.38, 0.24, 0.14
  ];

  const totalDays = 30;
  for (let day = 0; day < totalDays; day++) {
    const isWeekend = (day % 7 === 5 || day % 7 === 6) ? 1 : 0;

    for (let hour = 0; hour < 24; hour++) {
      for (const roadClass of roadClasses) {
        // Random weather distribution (80% clear, 15% rain, 5% fog)
        const randWeather = Math.random();
        const weather = randWeather < 0.8 ? 'clear' : (randWeather < 0.95 ? 'rain' : 'fog');

        // Incident occurrence probability (~4% per road segment hour)
        const hasIncident = Math.random() < 0.04 ? 1 : 0;
        const incidentSeverity = hasIncident ? Math.floor(1 + Math.random() * 4) : 0;

        // Ground truth generation with noise
        let base = hourlyCurve[hour];
        if (isWeekend) base *= 0.75;

        let classFactor = 1.0;
        if (roadClass === 'highway') classFactor = 0.82;
        if (roadClass === 'downtown') classFactor = 1.30;
        if (roadClass === 'arterial') classFactor = 1.10;

        let weatherFactor = weather === 'rain' ? 0.18 : (weather === 'fog' ? 0.10 : 0.0);
        let incidentFactor = incidentSeverity * 0.12;

        const noise = (Math.random() - 0.5) * 0.06;
        const targetCongestion = Math.min(1.0, Math.max(0.05, (base * classFactor) + weatherFactor + incidentFactor + noise));

        records.push({
          hour,
          isWeekend,
          isRushHour: ((hour >= 8 && hour <= 11) || (hour >= 17 && hour <= 20)) ? 1 : 0,
          roadClass,
          weather,
          incidentSeverity,
          targetCongestion
        });
      }
    }
  }
  return records;
}

// Convert record to feature vector
function extractFeatures(r) {
  const rad = (r.hour / 24) * 2 * Math.PI;
  return [
    1.0, // bias
    Math.sin(rad),
    Math.cos(rad),
    r.isWeekend,
    r.isRushHour,
    r.roadClass === 'highway' ? 1 : 0,
    r.roadClass === 'downtown' ? 1 : 0,
    r.weather === 'rain' ? 1 : 0,
    r.weather === 'fog' ? 1 : 0,
    r.incidentSeverity
  ];
}

// Matrix operations for Ridge Regression: beta = (X^T X + lambda * I)^-1 X^T y
function trainRidgeRegression(X, y, lambda = 0.05) {
  const p = X[0].length;
  const n = X.length;

  // Compute X^T * X
  const XtX = Array.from({ length: p }, () => new Float64Array(p));
  for (let i = 0; i < n; i++) {
    const row = X[i];
    for (let j = 0; j < p; j++) {
      for (let k = 0; k < p; k++) {
        XtX[j][k] += row[j] * row[k];
      }
    }
  }

  // Add L2 Ridge Regularization (lambda * I)
  for (let j = 1; j < p; j++) {
    XtX[j][j] += lambda;
  }

  // Compute X^T * y
  const Xty = new Float64Array(p);
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < p; j++) {
      Xty[j] += X[i][j] * y[i];
    }
  }

  // Gaussian elimination solver for XtX * beta = Xty
  const A = XtX.map(row => Array.from(row));
  const b = Array.from(Xty);

  for (let i = 0; i < p; i++) {
    let maxRow = i;
    for (let k = i + 1; k < p; k++) {
      if (Math.abs(A[k][i]) > Math.abs(A[maxRow][i])) maxRow = k;
    }
    [A[i], A[maxRow]] = [A[maxRow], A[i]];
    [b[i], b[maxRow]] = [b[maxRow], b[i]];

    for (let k = i + 1; k < p; k++) {
      const c = A[k][i] / A[i][i];
      for (let j = i; j < p; j++) {
        A[k][j] -= c * A[i][j];
      }
      b[k] -= c * b[i];
    }
  }

  const beta = new Array(p).fill(0);
  for (let i = p - 1; i >= 0; i--) {
    let sum = b[i];
    for (let j = i + 1; j < p; j++) {
      sum -= A[i][j] * beta[j];
    }
    beta[i] = sum / A[i][i];
  }

  return beta;
}

// Run Training & Validation
function main() {
  console.log("Generating 30-day urban telemetry dataset...");
  const data = generateDataset();
  console.log(`Generated ${data.length} telemetry samples.`);

  // 80/20 train/test split
  const shuffled = data.sort(() => Math.random() - 0.5);
  const splitIdx = Math.floor(shuffled.length * 0.8);
  const trainSet = shuffled.slice(0, splitIdx);
  const testSet = shuffled.slice(splitIdx);

  const X_train = trainSet.map(extractFeatures);
  const y_train = trainSet.map(r => r.targetCongestion);

  const X_test = testSet.map(extractFeatures);
  const y_test = testSet.map(r => r.targetCongestion);

  console.log("Fitting Ridge Regressor weights...");
  const weights = trainRidgeRegression(X_train, y_train);

  // Evaluate on Test Set
  let sumAbsError = 0;
  let sumSqError = 0;
  let totalMeanY = y_test.reduce((a, b) => a + b, 0) / y_test.length;
  let totalVarY = 0;

  for (let i = 0; i < testSet.length; i++) {
    const x = X_test[i];
    const actual = y_test[i];
    let pred = 0;
    for (let j = 0; j < weights.length; j++) pred += x[j] * weights[j];
    pred = Math.max(0.05, Math.min(1.0, pred));

    const err = actual - pred;
    sumAbsError += Math.abs(err);
    sumSqError += err * err;
    totalVarY += (actual - totalMeanY) * (actual - totalMeanY);
  }

  const mae = Number((sumAbsError / testSet.length).toFixed(4));
  const rmse = Number((Math.sqrt(sumSqError / testSet.length)).toFixed(4));
  const r2 = Number((1 - (sumSqError / totalVarY)).toFixed(4));

  console.log(`Model Trained Successfully!`);
  console.log(`Holdout Test Metrics (N=${testSet.length}):`);
  console.log(`  - MAE:  ${mae}`);
  console.log(`  - RMSE: ${rmse}`);
  console.log(`  - R^2:  ${r2}`);

  const modelOutput = {
    trainedAt: new Date().toISOString(),
    dataset: "30-Day Simulated Belagavi Sensor Stream",
    samplesCount: data.length,
    trainCount: trainSet.length,
    testCount: testSet.length,
    features: [
      "bias", "sin_hour", "cos_hour", "is_weekend", "is_rush_hour",
      "road_highway", "road_downtown", "weather_rain", "weather_fog", "incident_severity"
    ],
    weights: weights.map(w => Number(w.toFixed(5))),
    metrics: {
      mae,
      rmse,
      r2
    }
  };

  const outputPath = path.join(__dirname, '..', 'data', 'traffic_model.json');
  fs.writeFileSync(outputPath, JSON.stringify(modelOutput, null, 2));
  console.log(`Model artifact saved to: ${outputPath}`);
}

main();
