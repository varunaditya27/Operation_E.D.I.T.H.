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
The waves are calculated as a function of horizontal pixel coordinate $x \in [0, 600]$:

$$\text{Ref Wave: } Y_{ref}(x) = Y_{mid} + A_{ref} \cdot \sin\left(\frac{2\pi \cdot f_{ref} \cdot x}{L} + \phi_{ref}\right) + k_{ref} \cdot x$$

$$\text{Cal Wave: } Y_{cal}(x) = Y_{mid} + (A_{ref} \cdot A_{user}) \cdot \sin\left(\frac{2\pi \cdot (f_{ref} \cdot f_{user}) \cdot x}{L} + \phi_{user}\right) + k_{user} \cdot x$$

* **Constants:**
  * Canvas Width: `600` px
  * Center Y ($Y_{mid}$): `150` px
  * Reference Amplitude ($A_{ref}$): `50` px
  * Reference Frequency ($f_{ref}$): `0.05` (spatial scale)
  * Modulus Length ($L$): `600`
* **Target Slider States:**
  * $f_{user}$ = `1.00`
  * $\phi_{user}$ = `0.00`
  * $A_{user}$ = `1.00`
  * $k_{user}$ = `0.00`

### 2.2 WebAssembly Resonance Engine (`wrc_verifier.wasm`)
The verification calculations are executed in a compiled WebAssembly module to prevent solvers from editing local Javascript values using the browser console.
* **Wasm Exports:**
  * `void set_user_inputs(float f, float p, float a, float k)`
  * `float calculate_resonance_diff()`
* **Resonance Condition:**
  * The difference is calculated as the mean squared error (MSE) of $Y_{cal}(x) - Y_{ref}(x)$ sampled at 60 points along the x-axis:
    $$\text{MSE} = \frac{1}{60} \sum_{i=1}^{60} \left(Y_{cal}(10 \cdot i) - Y_{ref}(10 \cdot i)\right)^2$$
  * Resonance is achieved when $\text{MSE} < 0.05$.

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
* The generated code changes every 10 seconds. The server validates that the submitted code was active during that exact timestamp window.

---

## 4. Stark Challenge-Response Protocol (SCRP)

Authentication uses challenge-response endpoints to prevent replaying credentials or token sniffing.

### 4.1 Initiate Challenge
* **Endpoint:** `GET /api/v1/auth/challenge`
* **Query Params:** `username` (string)
* **Response (JSON):**
  ```json
  {
    "challenge": "e82a39f01bc482390a421b92049e29a3",
    "salt": "stark_audit_v5",
    "timestamp": 1781259230
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
    "timestamp": 1781259230
  }
  ```
* **Validation Logic:**
  1. The server checks that the submission timestamp is within $\pm 10$ seconds of the current time.
  2. The server re-evaluates the challenge:
     $$\text{Expected\_Response} = \text{HMAC-SHA256}(\text{key}=\text{employee\_secret}, \text{msg}=\text{challenge} + \text{salt})$$
  3. The server checks that `blink_code` matches the color sequence generated for that timestamp.
  4. If correct, the server issues a session token:
     ```json
     {
       "status": "success",
       "session_token": "sess_02931a8bc4ef32da9",
       "expires_in": 90
     }
     ```
