import express from 'express';
import http from 'http';
import { Server as SocketIOServer } from 'socket.io';
import cors from 'cors';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';
import { spawn } from 'child_process';

import routesRouter from './routes/routes.js';
import incidentsRouter from './routes/incidents.js';
import signalsRouter from './routes/signals.js';
import emergencyRouter from './routes/emergency.js';
import db from './db/database.js';
import { hydrateGraphFromDB, ROAD_EDGES } from './services/graphEngine.js';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const server = http.createServer(app);
const io = new SocketIOServer(server, {
  cors: {
    origin: '*',
    methods: ['GET', 'POST']
  }
});

app.set('io', io);

const PORT = process.env.PORT || 5000;
const PYTHON_PORT = process.env.TRAFFIC_API_PORT || 8000;

// Reverse proxy helper to Python FastAPI engine
const proxyToFastAPI = (req, res) => {
  const fullPath = req.originalUrl || req.url;
  const targetUrl = new URL(fullPath, `http://127.0.0.1:${PYTHON_PORT}`);
  const options = {
    hostname: '127.0.0.1',
    port: PYTHON_PORT,
    path: targetUrl.pathname + targetUrl.search,
    method: req.method,
    headers: {
      ...req.headers,
      host: `127.0.0.1:${PYTHON_PORT}`
    }
  };

  const proxyReq = http.request(options, (proxyRes) => {
    res.writeHead(proxyRes.statusCode, proxyRes.headers);
    proxyRes.pipe(res, { end: true });
  });

  proxyReq.on('error', (err) => {
    console.warn(`[Proxy Warning] FastAPI engine on :${PYTHON_PORT} unreachable (${err.message})`);
    if (!res.headersSent) {
      res.status(502).json({ error: 'Traffic Engine Proxy Error', message: err.message });
    }
  });

  req.pipe(proxyReq, { end: true });
};

// Route FastAPI endpoints directly through port 5000
app.use('/api/traffic', proxyToFastAPI);
app.use('/docs', proxyToFastAPI);
app.use('/openapi.json', proxyToFastAPI);

// Middleware
app.use(cors());
app.use(express.json());

// Serve static frontend files from /public
app.use(express.static(path.join(__dirname, '../public')));

// Request logging
app.use((req, res, next) => {
  if (!req.url.startsWith('/favicon') && !req.url.startsWith('/road_routes') && !req.url.startsWith('/api/traffic/video_feed')) {
    console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
  }
  next();
});

// Config endpoint (provides public Mapbox token securely from .env)
app.get('/api/config', (req, res) => {
  res.status(200).json({
    status: 200,
    mapboxToken: process.env.MAPBOX_TOKEN || ''
  });
});

// Admin Authentication endpoint
app.post('/api/admin/login', (req, res) => {
  const { username, password } = req.body || {};
  const validUser = process.env.ADMIN_USER || 'admin';
  const validPass = process.env.ADMIN_PASS || 'admin123';

  if (username === validUser && password === validPass) {
    const token = 'admin_session_' + Buffer.from(`${username}:${Date.now()}`).toString('base64');
    return res.status(200).json({
      status: 200,
      message: 'Admin authentication successful',
      token,
      user: { username, role: 'traffic_controller' }
    });
  } else {
    return res.status(401).json({
      status: 401,
      error: 'Invalid administrator credentials'
    });
  }
});

// API Routes
app.use('/api/routes', routesRouter);
app.use('/api/predictions', routesRouter);
app.use('/api/incidents', incidentsRouter);
app.use('/api/signals', signalsRouter);
app.use('/api/emergency', emergencyRouter);

// Health check
app.get('/api/health', (req, res) => {
  res.status(200).json({
    status: 'ONLINE',
    system: 'PulseTraffic OS BPR Core Engine',
    timestamp: new Date().toISOString()
  });
});

// Real-time WebSocket connection
io.on('connection', (socket) => {
  console.log(`[Socket.io] Client connected: ${socket.id}`);

  // Broadcast traffic updates every 4 seconds
  const interval = setInterval(() => {
    socket.emit('telemetry_tick', {
      timestamp: new Date().toISOString(),
      networkLoad: Number((0.45 + Math.random() * 0.2).toFixed(2)),
      activeVehicles: Math.floor(1240 + Math.random() * 100),
      avgSpeedKmh: Number((38 + Math.random() * 8).toFixed(1))
    });
  }, 4000);

  socket.on('disconnect', () => {
    clearInterval(interval);
  });
});

// One-click Demo Reset Endpoint
app.post('/api/demo/reset', (req, res) => {
  try {
    db.prepare('DELETE FROM incidents').run();
    try { db.prepare('DELETE FROM incident_reports').run(); } catch (e) {}
    try { db.prepare('DELETE FROM road_closure_simulations').run(); } catch (e) {}

    const insertInc = db.prepare(`
      INSERT INTO incidents (
        id, type, severity, lat, lng, road_segment_id, description, reported_by,
        status, confirmations, created_at, updated_at, title, severity_category,
        severity_score, lanes_blocked, total_lanes, affected_road_name
      ) VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?,
        ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?,
        ?, ?, ?, ?
      )
    `);
    insertInc.run(
      'INC-8891', 'accident', 3, 15.8497, 74.5089, 'E01',
      'Multi-car collision near Rani Chennamma Circle', 'Traffic Patrol-1',
      'verified', 'Accident at Rani Chennamma Circle', 'HIGH', 72, 2, 3, 'College Road Arterial'
    );
    insertInc.run(
      'INC-8874', 'roadblock', 2, 15.8720, 74.5190, 'E04',
      'Underpass drainage maintenance', 'PWD Belagavi',
      'verified', 'Maintenance on PB Road Spine', 'MEDIUM', 45, 1, 3, 'PB Road Northern Spine'
    );

    for (const e of ROAD_EDGES) {
      e.activeIncidents = [];
      e.closed = false;
      e.isSimulated = false;
      e.closureType = 'none';
      e.capacityReductionPercent = 0;
    }
    hydrateGraphFromDB();

    io.emit('incident:new', { id: 'INC-8891', type: 'accident', severity: 3, roadName: 'Multi-car collision near Rani Chennamma Circle' });
    io.emit('network:restore', { roadSegmentId: 'all' });
    io.emit('reroute:triggered', { reason: 'Demo reset' });

    res.status(200).json({ status: 200, message: "Demo data reset successfully to clean benchmark state." });
  } catch (err) {
    res.status(500).json({ status: 500, error: err.message });
  }
});

process.on('uncaughtException', (err) => {
  console.error('[Uncaught Exception]', err);
});
process.on('unhandledRejection', (reason, promise) => {
  console.error('[Unhandled Rejection]', reason);
});

server.listen(PORT, () => {
  console.log(`\n=================================================`);
  console.log(`🚦 PulseTraffic OS Server listening on port ${PORT}`);
  console.log(`🌐 Live Frontend: http://localhost:${PORT}/`);
  console.log(`📡 WebSocket Engine active via Socket.IO`);
  console.log(`📋 API Health: http://localhost:${PORT}/api/health`);
  console.log(`=================================================\n`);
});

export { app, server, io };
