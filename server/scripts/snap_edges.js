/**
 * PulseTraffic OS - Road Network Geometry Snapper
 * Queries OSRM for exact street-level coordinates for all 31 Belagavi road segments.
 * Outputs server/data/edge_geometry.json mapping edge IDs to [lat, lng] coordinate arrays and real lengthKm.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { ROAD_NODES, ROAD_EDGES } from '../services/graphEngine.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function snapAllEdges() {
  console.log("Snapping Belagavi road network to real OSRM street geometries...");
  const edgeGeometry = {};
  const forwardEdges = ROAD_EDGES.filter(e => !e.id.endsWith('_R'));

  for (let i = 0; i < forwardEdges.length; i++) {
    const edge = forwardEdges[i];
    const fromNode = ROAD_NODES[edge.from];
    const toNode = ROAD_NODES[edge.to];

    if (!fromNode || !toNode) continue;

    console.log(`[${i + 1}/${forwardEdges.length}] Snapping ${edge.id}: ${fromNode.name} -> ${toNode.name}...`);

    let coordinates = [];
    let snappedDistKm = edge.lengthKm;

    try {
      const url = `http://router.project-osrm.org/route/v1/driving/${fromNode.lng},${fromNode.lat};${toNode.lng},${toNode.lat}?overview=full&geometries=geojson`;
      const res = await fetch(url, { headers: { 'User-Agent': 'PulseTrafficOS/1.0' } });
      if (res.ok) {
        const data = await res.json();
        if (data.routes && data.routes.length > 0) {
          const r = data.routes[0];
          snappedDistKm = Number((r.distance / 1000).toFixed(2));
          // Convert [lng, lat] to [lat, lng] for Leaflet
          coordinates = r.geometry.coordinates.map(c => [c[1], c[0]]);
        }
      }
    } catch (err) {
      console.warn(`Fallback to straight line for ${edge.id}:`, err.message);
    }

    if (coordinates.length === 0) {
      coordinates = [[fromNode.lat, fromNode.lng], [toNode.lat, toNode.lng]];
    }

    edgeGeometry[edge.id] = {
      from: edge.from,
      to: edge.to,
      name: edge.name,
      lengthKm: snappedDistKm,
      coordinates
    };

    // Return edge geometry is reversed coordinates
    edgeGeometry[`${edge.id}_R`] = {
      from: edge.to,
      to: edge.from,
      name: `${edge.name} (Return)`,
      lengthKm: snappedDistKm,
      coordinates: [...coordinates].reverse()
    };

    // Polite delay for public OSRM
    await sleep(250);
  }

  const outPath = path.join(__dirname, '..', 'data', 'edge_geometry.json');
  fs.writeFileSync(outPath, JSON.stringify(edgeGeometry, null, 2));
  console.log(`Successfully snapped all edges! Output written to: ${outPath}`);
}

snapAllEdges();
