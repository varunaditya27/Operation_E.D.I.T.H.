<div align="center">

# ⚙️ S.H.I.E.L.D. AUTH GATEWAY BACKEND ⚙️
### *FastAPI Cryptographic Verification Engine*

[![Python](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Framework-emerald?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![SQLite](https://img.shields.io/badge/SQLite-Database-blue?style=for-the-badge&logo=sqlite)](https://www.sqlite.org)

---

</div>

## 🛡️ Core Services

The backend subsystem is built on **FastAPI** and **SQLite**, exposing the main APIs and live WebSocket protocols to process challenge requests and release encrypted flags.

### 1. Symmetric Challenge-Response Protocol (SCRP)
- **Challenge Issuance (`GET /api/v1/auth/challenge`)**: Returns a dynamic timestamped challenge payload, a salt value, and a unique transaction token.
- **Verification (`POST /api/v1/auth/verify`)**: Validates symmetrical HMAC-SHA256 tokens using the FridayVM employee secret, matched with a transient 3-character visual blink code calculated from 10-second timestamp rotations.

### 2. Isolated PCAP Gateway
- **Artifact Gating (`GET /api/v1/artifacts/hydra-capture`)**: Releases the network PCAP captures to logged-in employees, enforcing session limits and DB persistence mapping.

### 3. ZKP WebSocket Gateway (`/api/v1/admin/auth/ws`)
- Coordinates the 3-step administrative validation flow.
- Enforces strict **1-second timeouts** between messages to restrict human latency.

---

## 🔒 WebSocket Protocol Flow

The multi-round authentication steps for administrative validation are detailed below:

```mermaid
sequenceDiagram
    autonumber
    actor Client as Solver Script
    participant Server as FastAPI ZKP Gateway

    Client->>Server: Connect to ws://localhost/api/v1/admin/auth/ws
    Server->>Client: Send "server_init" (Nonce, CAPTCHA Base64, Modulus N, Keys v)
    Note over Client: Compute x = r² mod N (under 1.0s limit)
    Client->>Server: Send "client_commit" (CAPTCHA input, commitment x)
    Server->>Client: Send "server_challenge" (Binary vector e)
    Note over Client: Compute y = r * Π (s_j)^e_j mod N (under 1.0s limit)
    Client->>Server: Send "client_respond" (response y)
    Server->>Client: Send "server_pow" (PoW salt, prefix target)
    Note over Client: Search for nonce: SHA256(salt + nonce) starting with prefix
    Client->>Server: Send "client_pow_solve" (solved nonce)
    Server->>Client: Send "directors_log" (Decrypted flag JSON)
```

---

## 📁 Folder Structure

```
backend/
├── app/
│   ├── main.py        # Core FastAPI App & WebSocket handler
│   ├── crypto.py      # HMAC, Blink Code, and ZKP math implementations
│   └── config.py      # Static keys, modulus values, and secrets
├── requirements.txt   # Backend python dependencies
└── Dockerfile         # Deployment setup
```

---

## 🛠️ Local Development

### 1. Installation
Install requirements inside a virtual environment:
```bash
pip install -r requirements.txt
```

### 2. Run Local Development Server
Launch using uvicorn:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

---

<div align="center">

---
⚙️ **STARK INDUSTRIES FALLBACK SYSTEMS DIVISION** ⚙️
*Security clearance verification requires active key syncing at all times.*

</div>
