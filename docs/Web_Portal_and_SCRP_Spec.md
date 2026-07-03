# Stark Web Portal, SCRP & Calibration Gate — Technical Specification
### Document ID: SPEC-ACT2-WEBPORTAL
### Status: v6.0.0 Production Ready
### Last Updated: July 1, 2026
### Target Implementation: Act II (Authentication) & Act II.5 (Calibration Gate)

This document details the interface, mathematical calibration, and communication protocols for the **Stark Employee Portal** (Next.js) frontend and backend API, including the new Act II.5 Resonance Calibration Gate that gates access to Act III/IV.

---

## 1. Web Portal Interface Layout (Vercel)

The web interface is a Next.js single-page application hosted on Vercel. It consists of:
* **Terminal Interface:** An interactive text command panel simulating a SHIELD developer shell.
* **WRC Calibration Canvas:** An HTML5 canvas rendering the analog wave calibration signals.
* **Knob Control Panels:** A series of range sliders representing tuning knobs (Frequency, Phase, Amplitude, Skew).
* **Color Blink Indicator:** A small round status icon that flashes variable color sequences once resonance is hit.

---

## 2. Waveform Resonance Calibration (WRC) Mathematics

To access the portal, the client must tune a dynamic calibration wave ($W_{cal}$) to match a static reference wave ($W_{ref}$).

### 2.1 Wave Equations
The waves are calculated as a function of time-step coordinate $x \in [0, 2\pi]$:

$$\text{Ref Wave: } Y_{ref}(x) = A_{ref} \cdot \sin(f_{ref} \cdot x + \phi_{ref}) + k_{ref}$$

$$\text{Cal Wave: } Y_{cal}(x) = A_{user} \cdot \sin(f_{user} \cdot x + \phi_{user}) + k_{user}$$

* **Target Reference Constants (Server-Side):**
  * Target Frequency ($f_{ref}$): `0.82`
  * Target Phase ($\phi_{ref}$): `2.14`
  * Target Amplitude ($A_{ref}$): `0.91`
  * Target Skew ($k_{ref}$): `0.07`

### 2.2 Calibration Gate Verification
The calibration coefficients are verified directly by the backend endpoint `POST /api/v1/calibrate/submit`.
* **Resonance Condition:**
  * To successfully align the gate, the submitted parameters must fall within the following tolerances of the reference constants:
    * Frequency: $|f_{user} - 0.82| \le 0.03$
    * Phase: $|\phi_{user} - 2.14| \le 0.05$
    * Amplitude: $|A_{user} - 0.91| \le 0.03$
    * Skew: $|k_{user} - 0.07| \le 0.02$
  * Rate Limit: Max 6 calibration attempts per minute per session. On success, the backend updates the database to mark the session as calibrated, enabling access to the subsequent PCAP release and WebSocket endpoints.

---

## 3. Dynamic Visual Blink Code

Once resonance is achieved ($\text{MSE} < 0.05$), the verifier signals the canvas script to flash a color sequence.

### 3.1 Blink Protocol
* **Indicator:** A 15px radius circle drawn at the corner of the canvas.
* **Sequence Length:** 6 sequential pulses.
* **Possible Colors:** Red (`R`), Green (`G`), Blue (`B`), Yellow (`Y`).
* **Timing:** Each color is active for `400ms`, followed by a `200ms` dark interval.
* **The Look-up Grid:**
  The portal displays a static matrix mapping pairs of colors to characters:

  | | Red | Green | Blue | Yellow |
  | :--- | :---: | :---: | :---: | :---: |
  | **Red** | `S` | `A` | `9` | `M` |
  | **Green** | `K` | `1` | `T` | `E` |
  | **Blue** | `F` | `P` | `8` | `V` |
  | **Yellow** | `Z` | `U` | `Q` | `W` |

  * *Example:* A flash sequence of `Red -> Red -> Green -> Blue -> Yellow -> Red` is parsed in pairs:
    * Pair 1: `Red-Red` -> `S`
    * Pair 2: `Green-Blue` -> `T`
    * Pair 3: `Yellow-Red` -> `Z`
    * Result Code: `STZ`
* The generated code changes every 30 minutes (1800 seconds). The server validates that the submitted code was active during that exact timestamp window.

---

## 4. Stark Challenge-Response Protocol (SCRP)

Authentication uses challenge-response endpoints to prevent replaying credentials or token sniffing.

### 4.1 Initiate Challenge
* **Endpoint:** `GET /api/v1/auth/challenge`
* **Query Params:** `username` (string)
* **Response (JSON):**
  ```json
  {
    "challenge_id": "02a9b3d18c4e2a10",
    "challenge": "e82a39f01bc482390a421b92049e29a3",
    "salt": "stark_audit_v5",
    "timestamp": 1781259230,
    "blink_sequence": ["R", "R", "G", "B", "Y", "R"]
  }
  ```

### 4.2 Submit Verification
* **Endpoint:** `POST /api/v1/auth/verify`
* **Request Body (JSON):**
  ```json
  {
    "username": "mreyes",
    "response": "92f0bc8aef43029da12f98bc43d1aef4023da9f123ba6e7021da3b9cde183f98",
    "blink_code": "STZ",
    "challenge_id": "02a9b3d18c4e2a10",
    "timestamp": 1781259230
  }
  ```
* **Validation Logic:**
  1. The server checks that the submission timestamp is within $\pm 30$ minutes ($\pm 1800$ seconds) of the current server time.
  2. The server re-evaluates the challenge:
     $$\text{Expected\_Response} = \text{HMAC-SHA256}(\text{key}=\text{employee\_secret}, \text{msg}=\text{challenge} + \text{salt})$$
     where `salt` is the `STATE_KEY` (`stark_audit_v5`).
  3. The server checks that `blink_code` matches the color sequence generated for that timestamp.
  4. If correct, the server issues a session token:
     ```json
     {
       "status": "success",
       "session_token": "sess_02931a8bc4ef32da9",
       "expires_in": 1800
     }
     ```
