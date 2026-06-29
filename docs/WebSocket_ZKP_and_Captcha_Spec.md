# WebSocket ZKP & Captcha Protocol — Technical Specification
### Document ID: SPEC-ACT4-ZKPWS
### Status: Release/Production-Ready
### Target Implementation: Act IV Climax

This document specifies the communication contract, mathematical equations, and verification schemas for the interactive WebSocket endpoint at `/api/v1/admin/auth/ws`.

---

## 1. Zero-Knowledge Proof (Fiat-Shamir Scheme) Math

To verify the user's Director-tier clearance without transmitting the underlying secret keys, the server conducts a multi-round Fiat-Shamir identification handshake.

### 1.1 Parameters
* **Modulus ($N$):** A 1024-bit integer, generated as $N = P \times Q$ where $P$ and $Q$ are private primes.
  $$N = \text{0x8f2d8a...}$$
* **SHIELD Public Keys ($v_1, v_2, \dots, v_k \pmod N$):** Placed in the server configuration and recovered by the solver from the decrypted PCAP in Act III. $k = 4$.
* **Client Credentials ($s_1, s_2, \dots, s_k \pmod N$):** Secret keys derived from the `employee_secret` (Act I).

### 1.2 Protocol Step-by-Step
1. **Commitment:** The client chooses a random integer $r \in [1, N-1]$, computes $x$:
   $$x = r^2 \pmod N$$
   The client sends $x$ to the server.
2. **Challenge:** The server generates a random binary challenge vector:
   $$e = (e_1, e_2, e_3, e_4) \in \{0, 1\}^4$$
   The server sends $e$ to the client.
3. **Response:** The client computes $y$:
   $$y = r \prod_{j=1}^4 s_j^{e_j} \pmod N$$
   The client sends $y$ to the server.
4. **Verification:** The server verifies that:
   $$y^2 \equiv x \prod_{j=1}^4 v_j^{e_j} \pmod N$$
   If this holds, the proof is mathematically valid.

---

## 2. Dynamic Visual CAPTCHA Specification

To block automated scripts running independently of the user, the server binds the connection initialization to a low-latency CAPTCHA.

### 2.1 CAPTCHA Image Generation (Server-Side)
* **Dimensions:** 150x50 pixels.
* **Content:** 4 random characters (alphanumeric, excluding ambiguous symbols like `0, O, 1, l, I`).
* **Distortion Filters:**
  * **Shear:** Random horizontal shearing factor between $-0.3$ and $0.3$.
  * **Line Noise:** 5 random bezier curves drawn across the text canvas.
  * **Wave Distortion:** Sinusoidal wave warping applied to the final image matrix:
    $$x' = x + 4 \cdot \sin(y / 6), \quad y' = y + 2 \cdot \cos(x / 4)$$
* **OCR Resistance:** The font used is a custom-rendered hand-drawn SVG path font, which prevents standard OCR systems (like Tesseract) from parsing the letters, but remains easily read by human eyes.

---

## 3. WebSocket Message Schemas (JSON)

All WebSocket communication uses JSON payloads. The timeout for receiving each response is **1000ms** (1.0 second) from the time the server transmits the challenge.

### 3.1 Server Init (Challenge 1)
Sent by the server immediately upon connection open:
```json
{
  "event": "server_init",
  "nonce": "9af8c2810ab2e391",
  "captcha_image": "data:image/png;base64,iVBORw0KGgoAAAAN..."
}
```

### 3.2 Client Response (Commitment)
Must be sent by the client in under 1000ms:
```json
{
  "event": "client_commit",
  "captcha_input": "K8X2",
  "x": "0x4f2a3e89bc..."
}
```

### 3.3 Server Challenge (Challenge 2)
Sent by the server after verifying the CAPTCHA and commitment structure:
```json
{
  "event": "server_challenge",
  "e": [1, 0, 1, 1]
}
```

### 3.4 Client Response (ZKP Response)
Must be sent by the client in under 1000ms:
```json
{
  "event": "client_respond",
  "y": "0x7a3f8901bc..."
}
```

### 3.5 Server PoW Challenge (Challenge 3)
Sent by the server on successful ZKP verification:
```json
{
  "event": "server_pow",
  "salt": "pow_salt_883921",
  "prefix": "00000"
}
```

### 3.6 Client PoW Response
Must be sent by the client in under 1000ms:
```json
{
  "event": "client_pow_solve",
  "pow": 4839201
}
```

---

## 4. Timeout and Failure Handling

* **Timeout Exceeded:** If the server does not receive the expected JSON packet within 1000ms, the WebSocket is closed with code `4008` ("Clearance Timeout Exceeded").
* **Mismatched States:** Any invalid ZKP match or incorrect CAPTCHA terminates the connection with code `4003` ("Unauthorized Cryptographic Claims").
