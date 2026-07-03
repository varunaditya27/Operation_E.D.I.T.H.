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
* **Plaintext Flag:** `rvcectf{SH13LD_C0GN1T1V3_4UTH}`
* **Associated Data (AAD):** The unique ZKP session nonce generated in the WebSocket init message (`secrets.token_hex(8)`).

### 1.2 Key Derivation Function (KDF)
The key $K_{flag}$ is derived from the transaction parameters calculated during the ZKP WebSocket rounds:

$$\text{key\_material} = \text{hex}(s_0) \mathbin{\Vert} \text{hex}(s_1) \mathbin{\Vert} \text{hex}(s_2) \mathbin{\Vert} \text{hex}(s_3) \mathbin{\Vert} \text{hex}(y_{\text{round2}}) \mathbin{\Vert} \text{str}(\text{PoW\_nonce})$$

$$K_{flag} = \text{SHA256}(\text{key\_material})$$

* $s_j$: The secret ZKP credentials.
* $y_{\text{round2}}$: The live mathematical response value submitted by the client in Round 2.
* $\text{PoW\_nonce}$: The integer nonce found to satisfy the Proof-of-Work constraint.
* $\mathbin{\Vert}$: String concatenation of representations.

---

## 2. Infrastructure Architecture & Docker Deployment

The target environment is deployed using Docker Compose, isolating the web server and the database.

### 2.1 `docker-compose.yml` Configuration
```yaml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    expose:
      - "8000"
    environment:
      - MACHINE_GUID=7948eaa2-7dfd-417d-8fb4-f8b9e2a930e3
      - BUILD_EPOCH=1781259200
      - STATE_KEY=stark_audit_v5
      - DB_PATH=/app/data/edith.db
      - DH_SERVER_PRIVATE=57382103
      - FLAG=rvcectf{SH13LD_C0GN1T1V3_4UTH}
    volumes:
      - backend-data:/app/data
    restart: always

  reverse-proxy:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
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
* **`auth_sessions` table:**
  ```sql
  CREATE TABLE auth_sessions (
      session_token TEXT PRIMARY KEY,
      username TEXT NOT NULL,
      created_at INTEGER NOT NULL,
      expires_at INTEGER NOT NULL,
      dashboard_accessed BOOLEAN DEFAULT 0,
      pcap_released BOOLEAN DEFAULT 0,
      calibrated BOOLEAN DEFAULT 0,
      calibrate_attempts INTEGER DEFAULT 0
  );
  ```
* **`challenges` table:**
  ```sql
  CREATE TABLE challenges (
      challenge_id TEXT PRIMARY KEY,
      challenge TEXT NOT NULL,
      username TEXT NOT NULL,
      created_at INTEGER NOT NULL,
      used BOOLEAN DEFAULT 0
  );
  ```
* **`pcap_tokens` table:**
  ```sql
  CREATE TABLE pcap_tokens (
      token TEXT PRIMARY KEY,
      session_token TEXT NOT NULL,
      created_at INTEGER NOT NULL,
      used BOOLEAN DEFAULT 0
  );
  ```
* **`rate_limits` table:**
  ```sql
  CREATE TABLE rate_limits (
      ip TEXT PRIMARY KEY,
      request_count INTEGER DEFAULT 0,
      window_start INTEGER NOT NULL,
      blocked_until INTEGER DEFAULT 0
  );
  ```

---

## 3. Anti-Cheese & Security Control Policy

### 3.1 Web Request Rate-Limiter
* **Rule:** Max 30 connections per minute per IP for `/api/v1/auth/challenge`, `/api/v1/auth/verify`, and `/api/v1/admin/auth/ws`.
* **Penalty:** Exceeding this triggers an HTTP `429 Too Many Requests` state for a block of 3 minutes.
* **Calibration Limit:** Calibration attempts are limited to 6 requests per minute per session.

### 3.2 Adaptive Gating for PCAP Release
* The `HYDRA_CAPTURE.pcapng` file is withheld at the start of the event.
* **Gating Trigger:** The player must login successfully and access `/api/v1/dashboard`. This updates the session status in the database to release the PCAP.
* **Download Endpoint:** The player downloads the file from `GET /api/v1/artifacts/hydra-capture` using the `Authorization: Bearer <session_token>` header. The response returns the PCAP and sets the `X-PCAP-Token` header, which provides the `pcap_token` required for the WebSocket handshake.

---

## 4. Playtest Verification & Hardening Checklist

- [ ] **Calibration Margin Auditing:** Verify that the server-side parameter bounds checking rejects inputs outside the specified tolerances ($f \pm 0.03$, $\phi \pm 0.05$, $A \pm 0.03$, $k \pm 0.02$).
- [ ] **CAPTCHA Anti-OCR:** Verify that DejaVu/Liberation mono font symbols with shear factor ($\pm 0.1$), 2 curve lines, and 30 dots noise block standard Tesseract parsing while remaining human readable.
- [ ] **PCAP Decryption Pipeline:** Verify that using the client private exponent $b$ derived from `DH_CLIENT_SEED` successfully decrypts TCP Session 2 of `HYDRA_CAPTURE.pcapng` and reveals the correct ZKP modulus $N$ and public keys.
- [ ] **ZKP WebSocket Automation:** Test the connection using client scripts that connect to `/api/v1/admin/auth/ws` with `pcap_token`, `nonce`, and `flash_code` parameters and successfully pass the 2-round Fiat-Shamir handshake.
- [ ] **Flag Entropy Check:** Ensure the AES-GCM decryption key generates invalid byte segments when any of the mathematical ZKP outputs differ by even 1 bit.
