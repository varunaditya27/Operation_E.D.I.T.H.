# Flag Decryption & Deployment Operations — Technical Specification
### Document ID: SPEC-ACT5-OPSDEPLOY
### Status: Release/Production-Ready
### Target Implementation: Act V & Challenge Infrastructure

This document details the configuration for the containerized challenge infrastructure, Vercel edge rules, and the final GCM flag decryption logic.

---

## 1. Flag Encryption & Decryption Mathematics

The flag is not stored in plaintext on the server or in the client binary. It is encrypted on the server and decrypted on-the-fly by the player's client script upon successfully completing the WebSocket exchange.

### 1.1 Encryption Parameters
* **Algorithm:** AES-GCM (256-bit key size).
* **Plaintext Flag:** `FLAG{SHIELD_COGNITIVE_AUTHENTICATION_PASSED_77391}`
* **Associated Data (AAD):** The user's active session token string (e.g. `sess_02931a8bc4ef32da9`).

### 1.2 Key Derivation Function (KDF)
The key $K_{flag}$ is derived from the transaction parameters calculated during the ZKP WebSocket rounds:

$$K_{flag} = \text{SHA-256}\left(\sum_{i=1}^k s_i \mathbin{\Vert} y_{\text{live}} \mathbin{\Vert} \text{PoW\_nonce}\right)$$

* $s_i$: The secret ZKP credentials.
* $y_{\text{live}}$: The live mathematical response value submitted by the client.
* $\text{PoW\_nonce}$: The integer nonce found to satisfy the Proof-of-Work constraint.
* $\mathbin{\Vert}$: String concatenation of hex representations.

---

## 2. Infrastructure Architecture & Docker Deployment

The target environment is deployed using Docker Compose, isolating the web server and the database.

### 2.1 `docker-compose.yml` Configuration
```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    expose:
      - "8000"
    environment:
      - DATABASE_URL=sqlite:///app/data/edith.db
      - MACHINE_GUID=7948eaa2-7dfd-417d-8fb4-f8b9e2a930e3
      - BUILD_EPOCH=1781259200
      - STATE_KEY=stark_audit_v5
    volumes:
      - backend-data:/app/data
    restart: always

  reverse-proxy:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/certs:/etc/nginx/certs:ro
    depends_on:
      - backend
    restart: always

volumes:
  backend-data:
```

### 2.2 Database Schema (SQLite)
* **`issued_nonces` table:**
  ```sql
  CREATE TABLE issued_nonces (
      nonce TEXT PRIMARY KEY,
      created_at INTEGER NOT NULL,
      expires_at INTEGER NOT NULL,
      used BOOLEAN DEFAULT 0
  );
  ```
* **`wrc_sessions` table:**
  ```sql
  CREATE TABLE wrc_sessions (
      session_id TEXT PRIMARY KEY,
      blink_sequence TEXT NOT NULL,
      resolved BOOLEAN DEFAULT 0,
      timestamp INTEGER NOT NULL
  );
  ```

---

## 3. Anti-Cheese & Security Control Policy

### 3.1 Web Request Rate-Limiter
* **Rule:** Max 12 connections per minute per IP for `/api/v1/auth/verify` and `/api/v1/admin/auth/ws`.
* **Penalty:** Exceeding this triggers an HTTP `429 Too Many Requests` state for a block of 3 minutes.
* **Objective:** Prevents players from automating brute-force searches on the challenge-response signature or the ZKP inputs.

### 3.2 Adaptive Gating for PCAP Release
* The `HYDRA_CAPTURE.pcapng` file is withheld at the start of the event.
* **Gating Trigger:** The FastAPI backend monitors successful logins to `/api/v1/dashboard`. 
* Once a team records a successful entry, the server triggers a webhook to the CTF scoreboard API, which automatically releases the PCAP download link for that specific team.

---

## 4. Playtest Verification & Hardening Checklist

- [ ] **Wasm Isolation Check:** Run audit scripts to verify that local manipulation of the Javascript variables on the calibration web app does not bypass the Wasm verifier.
- [ ] **CAPTCHA Blur Factor:** Ensure the sinusoidal noise parameters on the CAPTCHA block Tesseract-OCR models (such as `tesseract --oem 1`) from parsing, but verify that humans can read the letters in < 0.5s.
- [ ] **Network RTT Margin:** Test the WS connection under simulated network latency (e.g. `tc qdisc add dev eth0 root netem delay 100ms`). Verify that RTT delay calculations dynamically adapt to prevent timeout state exceptions.
- [ ] **SBA Integrity:** Verify that LNK metadata is preserved when packaging `auth_backup.sba` inside the target distribution archive.
- [ ] **Flag Entropy Check:** Ensure the AES-GCM decryption key generates invalid byte segments when any of the mathematical ZKP outputs differ by even 1 bit.
