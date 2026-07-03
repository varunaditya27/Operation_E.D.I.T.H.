# Operation E.D.I.T.H. v5.0.0 — Technical Specifications & Implementation Guide
**Status:** ✅ Production Ready | Finalized | All Critical Bugs Fixed

This directory contains the comprehensive, end-to-end technical specifications for **Operation E.D.I.T.H. v5.0.0** — a sophisticated multi-act CTF challenge with perceptual gates, cryptographic verification layers, and strict anti-AI/anti-scraping constraints.

---

## 1. Specification Directory Map

| Specification Document | Code | Act | Description & Scope |
| :--- | :---: | :---: | :--- |
| [SBA File Format Spec](file:///home/varunaditya/Projects/Operation_E.D.I.T.H./docs/SBA_File_Format_Spec.md) | `SPEC-ACT0-SBA` | **Act 0** | Header structures, custom Run-Length Encoding (RLE) algorithms, and the modified RC4 encryption engine. |
| [FridayVM Spec](file:///home/varunaditya/Projects/Operation_E.D.I.T.H./docs/FridayVM_Specification.md) | `SPEC-ACT1-FRIDAYVM` | **Act I** | Virtual Machine registers, instruction set (ISA), dynamic PCG64 LCG-based opcode shuffler, self-modifying execution block, and decryption keys. |
| [Web Portal & SCRP Spec](file:///home/varunaditya/Projects/Operation_E.D.I.T.H./docs/Web_Portal_and_SCRP_Spec.md) | `SPEC-ACT2-WEBPORTAL` | **Act II** | Next.js/Vercel frontend design, Waveform Resonance Calibration (WRC) parameters, server-side calibration tolerances, and SCRP API payloads. |
| [PCAP Crypto Spec](file:///home/varunaditya/Projects/Operation_E.D.I.T.H./docs/PCAP_Crypto_and_Timing_Glitch_Spec.md) | `SPEC-ACT3-PCAPGLITCH` | **Act III** | Diffie-Hellman parameters, LCG-based private exponent extraction from Act 0 constants, stream decryption, and active session analysis. |
| [WebSocket ZKP & Captcha Spec](file:///home/varunaditya/Projects/Operation_E.D.I.T.H./docs/WebSocket_ZKP_and_Captcha_Spec.md) | `SPEC-ACT4-ZKPWS` | **Act IV** | Fiat-Shamir Zero-Knowledge Proof protocol, distorted visual CAPTCHA generation filters, WebSocket message schemas, and configurable timeouts. |
| [Flag & Deployment Spec](file:///home/varunaditya/Projects/Operation_E.D.I.T.H./docs/Flag_Decryption_and_Deployment_Spec.md) | `SPEC-ACT5-OPSDEPLOY` | **Act V** | GCM flag encryption KDF mathematics, docker-compose configuration, SQLite schemas, rate-limiting, and playtest checklists. |

---

## 2. Mathematical Coherence Verification

A Python verification suite has been created to test the core logic of all acts end-to-end:
* **Script Location:** [math_verification.py](file:///home/varunaditya/Projects/Operation_E.D.I.T.H./scripts/math_verification.py)
* **Execution Command:**
  ```bash
  python3 scripts/math_verification.py
  ```
* **Scope Tested:**
  * Modified RC4 encryption and decryption cycle.
  * SHA256 PCG64 LCG seed generation and FridayVM opcode shuffling.
  * Matrix multiplication check for decoy password validation (yielding solved characters: `34A`).
  * Diffie-Hellman key derivation from NetBIOS name, Host Key, and Epoch values using 64-bit LCG state concatenation.
  * Fiat-Shamir ZKP modular congruence checks using the real challenge modulus and secrets.
