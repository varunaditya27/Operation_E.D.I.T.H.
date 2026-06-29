<div align="center">

# 🛡️ OPERATION E.D.I.T.H. 🛡️
### *Secure Tactical Fallback & Anti-AI CTF Challenge*

[![Stark Industries](https://img.shields.io/badge/Security-Stark%20Industries-red?style=for-the-badge&logo=shield)](https://github.com)
[![Docker](https://img.shields.io/badge/Docker-Containerized-blue?style=for-the-badge&logo=docker)](https://github.com)
[![Next.js](https://img.shields.io/badge/Next.js-HUD%20Portal-cyan?style=for-the-badge&logo=nextdotjs)](https://github.com)

---

</div>

## 📖 Project Overview

**Operation E.D.I.T.H.** (Even Dead, I'm The Hero) is a meticulously engineered, multi-act Capture the Flag (CTF) security challenge modeled after the S.H.I.E.L.D. and Stark Industries tactical backup architectures. 

The challenge enforces strict **Anti-AI/Anti-Scraping constraints** (including clipboard poisoners, flexbox order scrambling, and visual CAPTCHA gates) paired with strict execution timing firewalls. Solvers are forced to analyze custom binary encodings, verify timing channels, solve zero-knowledge mathematical proofs, and write automated scripts to bypass security latencies.

---

## 🎮 The Challenge Flow

The challenge consists of five interconnected acts, illustrated in the system topology below:

```mermaid
graph TD
    subgraph Client Space
        A1["Act I: FridayVM Assembly"]
        A2["Act II: Next.js Portal & WRC Calibration"]
        A3["Act III: network PCAP analysis"]
        A4["Act IV: WebSocket ZKP & PoW Client"]
        A5["Act V: AES-GCM Flag Decryptor"]
    end

    subgraph Container Grid (Port 80)
        Proxy["Nginx Reverse Proxy & Rate Limiter"]
        Back["FastAPI Auth Gateway"]
        DB[("SQLite Session DB")]
    end

    A1 -->|Extract Employee Secret| A2
    A2 -->|Calibrate Wave & Solve SCRP| Proxy
    Proxy -->|Validate & Record Session| Back
    Back -->|Persist state| DB
    DB -->|Unlock PCAP Gating| A3
    A3 -->|Recover Weak DH keys| A4
    A4 -->|WebSocket Fiat-Shamir & PoW| Proxy
    Proxy -->|Upgrade Connection| Back
    Back -->|Return GCM Cryptographic Keys| A5
    A5 -->|Solve Monday/Tuesday/Wednesday/Friday keys| Flag["Decrypted Flag"]
```

---

## 📂 Repository Structure

This repository is organized into distinct functional subprojects:

```
.
├── backend/            # FastAPI REST and WebSocket Auth Gateways
├── frontend/           # Next.js Stark Employee HUD portal
├── nginx/              # Reverse-proxy, rate limiter, and WS Upgrade rules
├── challenge_assets/   # Compiled player files (SBA, FridayVM bytecode, PCAP capture)
├── scripts/            # Build utilities, math verifications, and integration tests
├── docs/               # Technical specs & single source of truth details
└── docker-compose.yml  # System-wide multi-container orchestration
```

---

## 🚀 Getting Started

Ensure you have **Docker** and **Docker Compose** installed.

### 1. Build and Run the Container Stack
Build and launch the complete environment (Nginx proxy, backend api, and frontend static assets):
```bash
docker compose up --build -d
```

### 2. Verify System Health
Query the public health check exposed through the reverse proxy:
```bash
curl http://localhost/health
```
Expected output:
```
OK
```

### 3. Open the Stark Portal
Open your web browser and navigate to:
```
http://localhost/
```

---

## 🛠️ Verification Testing
A complete end-to-end automation verification script is available. Run it locally to simulate a successful client exploit pipeline:
```bash
python3 scripts/integration_test.py
```

---

<div align="center">

---
⚠️ **CLASSIFIED MATERIAL — S.H.I.E.L.D. PROTOCOL LEVEL 8** ⚠️
*Unauthorized duplication or reverse-engineering is punishable under Stark Industries Security Code Sec. 34A.*

</div>