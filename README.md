# PulseTraffic - City Traffic Management & Route Optimization System
> **Hackathon Track:** Domain 1 — Full Stack Web Development (PS 01)

PulseTraffic is a high-performance smart city traffic operating system featuring dynamic graph routing (A* & Dijkstra), AI-based congestion forecasting, dynamic road incident impact analysis, adaptive traffic signal optimization, and emergency vehicle green-wave priority corridors.

---

## 👥 Team Roles & Responsibilities

| Role | Name | Focus Area |
| :--- | :--- | :--- |
| **Lead Developer** | **Yash** | Core architecture, WebSocket streams, Graph Engine, AI integration |
| **UI/UX & Pitch Lead** | **Sanjana** | React + Tailwind components, interactive dashboard, 5-slide pitch deck |
| **QA & Mock Data Engineer** | **Samarth** | Thunder Client API testing, test payloads, endpoint latency |
| **Domain Research & Jury Defense** | **Manikanta** | Traffic telemetry simulator, jury Q&A defense, benchmark statistics |

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Node.js**: v20+ LTS
- **npm**: v10+

### 2. API Contract
Before developing new endpoints or UI components, consult:
- [`contract.json`](./contract.json) — Canonical data schema for all 5 mandatory features.
- [`mock_data.json`](./mock_data.json) — Thunder Client / Postman ready-to-test scenarios.

### 3. Ports
- **Frontend (`/client`)**: `http://localhost:5173`
- **Backend (`/server`)**: `http://localhost:5000`
