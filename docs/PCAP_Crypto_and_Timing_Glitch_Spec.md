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
Instead of secure random selection, the client's private exponent $b$ is derived using the 64-bit PCG64 Linear Congruential Generator (LCG) seeded with parameters recovered in Act 0:
* **Inputs:**
  * NetBIOS ID: `REYES-LAPTOP`
  * Host Key: `STARK-FALLBACK-KEY-2026` (from Act 0 blueprint alignment)
  * build_epoch: `1781259200`
* **Derivation Math:**
  $$\text{Seed} = \text{SHA256}(\text{NetBIOS\_ID} + \text{Host\_Key} + \text{str}(\text{build\_epoch}))[:8] \text{ as a big-endian 64-bit integer}$$
  * Concat string: `"REYES-LAPTOPSTARK-FALLBACK-KEY-20261781259200"`
  * Seed: `0xdfdcd867b3e5ee24`
* **Private Key Generator:**
  Using the seed, the first two 64-bit outputs of the LCG ($X_1, X_2$) are generated:
  $$X_{n+1} = (6364136223846793005 \cdot X_n + 1442695040888963407) \pmod{2^{64}}$$
  * $X_1 = \text{LCG}(Seed)$
  * $X_2 = \text{LCG}(X_1)$
  * The client's private exponent $b$ (96-bit) is formed by:
    $$b = (X_1 \ll 32) \lor X_2$$
  * Private key $b$ value: `0x3ac01bd2feeb7fafcd0a7ff6`

### 1.3 Key Derivation & Stream Decryption
Once the player computes $b$, they derive the shared secret $K$:
$$K = A^b \pmod p$$
* **Symmetric Key:**
  $$\text{AES\_Key} = \text{SHA256}(K.\text{to\_bytes}(64, \text{'big'}))$$
* **Cipher Mode:** AES-256-CBC with an initialization vector (IV) prepended to the ciphertext block (first 16 bytes of the TCP payload).

---

## 2. PCAP Session Analysis & Parameter Extraction

The packet capture `HYDRA_CAPTURE.pcapng` contains several TCP stream sessions recording communications between a client and the auth server. The participant must isolate the active authenticated session and extract ZKP parameters.

### 2.1 Network Session Structure
* **Session 1 (Decoy):** Initialization fails, no authentication occurs.
* **Session 2 (Active Session - REYES-LAPTOP):**
  * Uses the client seed derived from `REYES-LAPTOP` NetBIOS ID.
  * Decrypting this session's payload exposes the actual 1024-bit ZKP modulus $N = P \times Q$ and the 4 public key values $v_j$ required for Act IV authentication.
* **Session 3 (Decoy):** Inactive/empty handshake.
* **Session 4 (Decoy/Honeypot):**
  * Contains a decoy ZKP modulus $N_{decoy}$ and public keys.
  * Attempts to use these parameters in the WebSocket ZKP stage will result in instant authorization failure.

### 2.2 Decryption & Extraction Script (Python)
```python
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# Shared secret K from DH key exchange
K_bytes = K.to_bytes(64, 'big')
aes_key = hashlib.sha256(K_bytes).digest()

def decrypt_payload(payload: bytes, key: bytes) -> bytes:
    iv = payload[:16]
    ciphertext = payload[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()
```
