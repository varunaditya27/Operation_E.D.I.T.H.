# WebSocket ZKP & Captcha Protocol — Technical Specification
### Document ID: SPEC-ACT4-ZKPWS
### Status: Release/Production-Ready
### Target Implementation: Act IV Climax

This document specifies the communication contract, mathematical equations, and verification schemas for the interactive WebSocket endpoint at `/api/v1/admin/auth/ws`.

---

## 1. Zero-Knowledge Proof (Fiat-Shamir Scheme) Math

To verify the user's Director-tier clearance without transmitting the underlying secret keys, the server conducts a multi-round Fiat-Shamir identification handshake.

### 1.1 Parameters
* **Modulus ($N$):** A 1024-bit integer, generated as $N = P \times Q$ where $P$ and $Q$ are private safe primes.
  $$N = \text{0xdeeb845187e14d9b4b0e5bfb200b3967bc310b7a70a1a5b6c7ea6e7e48b94ab7b8c71b7b7a13d7e7e5b22b10b00b00b00b00b00b00b00b00b00b00b00b00ba8b1}$$
* **SHIELD Public Keys ($v_1, v_2, \dots, v_k \pmod N$):** Recovered by the solver from the decrypted PCAP in Act III. $k = 4$.
* **Client Credentials ($s_1, s_2, \dots, s_k \pmod N$):** Secret keys derived from the `employee_secret` (Act I).

### 1.2 Connection Requirements
To open the WebSocket connection at `/api/v1/admin/auth/ws`, the client must supply three query parameters:
1. `pcap_token`: PCAP access validation token.
2. `nonce`: Session validation token.
3. `flash_code`: A 2-character hexadecimal code transcribed from the 4-color flash sequence on the portal page using the look-up color grid.

### 1.3 Protocol Step-by-Step (2 Rounds)
For each of the **two** consecutive validation rounds:
1. **Commitment:** The client chooses a random integer $r \in [1, N-1]$, computes $x$:
   $$x = r^2 \pmod N$$
   The client sends $x$ to the server in a `client_commit` event.
2. **Challenge:** The server generates a random binary challenge vector:
   $$e = (e_1, e_2, e_3, e_4) \in \{0, 1\}^4$$
   The server sends $e$ to the client in a `server_challenge` event.
3. **Response:** The client computes $y$:
   $$y = r \prod_{j=1}^4 s_j^{e_j} \pmod N$$
   The client sends $y$ to the server in a `client_respond` event.
4. **Verification:** The server verifies that:
   $$y^2 \equiv x \prod_{j=1}^4 v_j^{e_j} \pmod N$$
   If this holds, the round is mathematically valid. The client must repeat this sequence twice. CAPTCHA input is verified during the Round 1 commitment phase only.

---

## 2. Dynamic Visual CAPTCHA Specification

To block automated scripts running independently of the user, the server binds the connection initialization to a low-latency CAPTCHA.

### 2.1 CAPTCHA Image Generation (Server-Side)
* **Dimensions:** 150x50 pixels.
* **Content:** 4 random characters from a custom charset (`ABCDEFGHJKMNPQRSTUVWXYZ23456789`), excluding ambiguous symbols.
* **Distortion Filters:**
  * **Shear:** Random horizontal shearing factor between $-0.1$ and $0.1$.
  * **Line Noise:** 2 random line paths drawn across the text canvas.
  * **Wave Distortion:** Sinusoidal wave warping applied to the image:
    $$x' = x + 1 \cdot \sin(y / 8), \quad y' = y + 1 \cdot \cos(x / 6)$$
* **OCR Resistance:** Standard system fonts (like DejaVuSansMono or LiberationMono) are printed with randomized offsets, shear, line, and dot noise to defeat default Tesseract configurations.

---

## 3. WebSocket Message Schemas (JSON)

All WebSocket communication uses JSON payloads. The timeout for receiving responses is controlled by the server (default `config.POW_TIMEOUT_MS = 30000` or 30 seconds). The first two commitment/response rounds are allowed `1.5 * timeout` (45 seconds) to accommodate network latency, while the final Proof-of-Work solve is capped at 30 seconds.

### 3.1 Server Init
Sent by the server immediately upon connection open:
```json
{
  "event": "server_init",
  "nonce": "9af8c2810ab2e391",
  "captcha_image": "data:image/png;base64,iVBORw0KGgoAAA...",
  "zkp_params": {
    "N": "0xdeeb845187e14d9b4b0e5bfb200b396...",
    "v": ["0x...", "0x...", "0x...", "0x..."],
    "k": 4
  }
}
```

### 3.2 Client Round 1 Commitment
Must be sent by the client within the 45-second timeout window:
```json
{
  "event": "client_commit",
  "captcha_input": "K8X2",
  "x": "0x4f2a3e89bc..."
}
```

### 3.3 Server Round 1 Challenge
```json
{
  "event": "server_challenge",
  "round": 1,
  "e": [1, 0, 1, 1]
}
```

### 3.4 Client Round 1 Response
```json
{
  "event": "client_respond",
  "y": "0x7a3f8901bc..."
}
```

### 3.5 Client Round 2 Commitment
Must be sent by the client within 45 seconds (note that captcha_input is no longer required in round 2):
```json
{
  "event": "client_commit",
  "x": "0x9c42b8e3a2..."
}
```

### 3.6 Server Round 2 Challenge
```json
{
  "event": "server_challenge",
  "round": 2,
  "e": [0, 1, 1, 0]
}
```

### 3.7 Client Round 2 Response
```json
{
  "event": "client_respond",
  "y": "0x5d9e84d2ac..."
}
```

### 3.8 Server PoW Challenge
Sent on successful completion of both ZKP verification rounds:
```json
{
  "event": "server_pow",
  "salt": "pow_salt_883921",
  "prefix": "000000"
}
```

### 3.9 Client PoW Response
Must be sent by the client in under 30 seconds:
```json
{
  "event": "client_pow_solve",
  "pow": 4839201
}
```

---

## 4. Timeout and Failure Handling

* **Timeout Exceeded:** If the server does not receive the expected JSON packet within the timeout window (45s for commitments/responses, 30s for PoW), the WebSocket is closed with code `4008` ("Clearance Timeout Exceeded").
* **Mismatched States:** Any invalid ZKP match or incorrect CAPTCHA terminates the connection with code `4003` ("Unauthorized Cryptographic Claims" or "CAPTCHA verification failed").
