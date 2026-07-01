"""
Operation E.D.I.T.H. v5 — Cryptographic Primitives
Document Refs: SPEC-ACT0-SBA §4.2, SPEC-ACT1-FRIDAYVM §2.2, SPEC-ACT4-ZKPWS §1.2

Implements:
  - Stark-RC4 (modified RC4 with XOR'd PRGA step)
  - Custom RLE compression/decompression
  - FridayVM LCG and opcode shuffle
  - SCRP challenge-response HMAC
  - Fiat-Shamir ZKP verification math
  - AES-GCM flag encryption
"""
import hashlib
import hmac as _hmac
import secrets
import struct
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# ═══════════════════════════════════════════
# Stark-RC4 (SPEC-ACT0-SBA §4.2)
# ═══════════════════════════════════════════

def stark_rc4(data: bytes, key: bytes) -> bytes:
    """Modified RC4 cipher. XOR on the PRGA j-index with key bytes."""
    # KSA
    S = list(range(256))
    j = 0
    for i in range(256):
        j = (j + S[i] + key[i % len(key)]) % 256
        S[i], S[j] = S[j], S[i]

    # PRGA (modified: j XOR'd with key byte per iteration)
    i = 0
    j = 0
    out = bytearray()
    for idx in range(len(data)):
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        j = (j ^ key[idx % len(key)]) % 256  # Modification
        S[i], S[j] = S[j], S[i]
        t = (S[i] + S[j]) % 256
        out.append(data[idx] ^ S[t])
    return bytes(out)


# ═══════════════════════════════════════════
# Custom RLE Compression (SPEC-ACT0-SBA §3.1)
# Escape marker: 0xBC
# ═══════════════════════════════════════════

RLE_ESCAPE = 0xBC

def rle_compress(data: bytes) -> bytes:
    """Compress data using custom RLE protocol."""
    out = bytearray()
    i = 0
    while i < len(data):
        byte = data[i]
        # Count consecutive identical bytes
        run_len = 1
        while i + run_len < len(data) and data[i + run_len] == byte and run_len < 255:
            run_len += 1

        if run_len >= 4:
            # Encode as escape sequence: 0xBC [length] [byte]
            out.append(RLE_ESCAPE)
            out.append(run_len)
            out.append(byte)
            i += run_len
        else:
            # Write individual bytes
            for _ in range(run_len):
                if byte == RLE_ESCAPE:
                    out.append(RLE_ESCAPE)
                    out.append(0x00)
                else:
                    out.append(byte)
            i += run_len
    return bytes(out)


def rle_decompress(data: bytes) -> bytes:
    """Decompress data using custom RLE protocol."""
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == RLE_ESCAPE:
            if i + 1 >= len(data):
                raise ValueError("Truncated RLE escape sequence")
            length = data[i + 1]
            if length == 0x00:
                # Escaped literal 0xBC
                out.append(RLE_ESCAPE)
                i += 2
            else:
                if i + 2 >= len(data):
                    raise ValueError("Truncated RLE run sequence")
                byte = data[i + 2]
                out.extend([byte] * length)
                i += 3
        else:
            out.append(data[i])
            i += 1
    return bytes(out)


# ═══════════════════════════════════════════
# LCG and Opcode Shuffle (SPEC-ACT1-FRIDAYVM §2.2)
# Non-standard 64-bit LCG (PCG64 variant, not glibc)
# ═══════════════════════════════════════════

LCG_A = 6364136223846793005
LCG_C = 1442695040888963407
LCG_M = 2**64

def lcg_next(state: int) -> int:
    """Single LCG step with 64-bit arithmetic."""
    return (LCG_A * state + LCG_C) % LCG_M


def lcg_sequence(seed: int, count: int) -> list[int]:
    """Generate count LCG values from seed."""
    out = []
    state = seed
    for _ in range(count):
        state = lcg_next(state)
        out.append(state)
    return out


def generate_opcode_map(seed: int) -> dict[int, int]:
    """Fisher-Yates shuffle of opcode indices using LCG.
    Returns mapping: raw_opcode_byte -> instruction_id."""
    base_ops = list(range(32))
    state = seed
    for i in range(len(base_ops) - 1, 0, -1):
        state = lcg_next(state)
        j = state % (i + 1)
        base_ops[i], base_ops[j] = base_ops[j], base_ops[i]
    return {i: base_ops[i] for i in range(32)}


# ═══════════════════════════════════════════
# SCRP Challenge-Response (SPEC-ACT2-WEBPORTAL §4)
# ═══════════════════════════════════════════

def generate_challenge() -> str:
    """Generate a 16-byte hex challenge token."""
    return secrets.token_hex(16)


def compute_scrp_response(employee_secret: bytes, challenge: str, salt: str) -> str:
    """Compute HMAC-SHA256 response for SCRP.
    response = HMAC-SHA256(key=employee_secret, msg=challenge+salt)
    """
    msg = (challenge + salt).encode()
    return _hmac.new(employee_secret, msg, hashlib.sha256).hexdigest()


# ═══════════════════════════════════════════
# Blink Code Generation (SPEC-ACT2-WEBPORTAL §3.1)
# ═══════════════════════════════════════════

def generate_blink_sequence(timestamp: int, state_key: str) -> list[str]:
    """Generate a deterministic 6-color blink sequence for a given time window.
    Window is timestamp // BLINK_ROTATE_INTERVAL (30min buckets).
    """
    from . import config
    window = timestamp // config.BLINK_ROTATE_INTERVAL
    seed_bytes = f"{state_key}:{window}".encode()
    h = hashlib.sha256(seed_bytes).digest()
    seq = []
    for i in range(config.BLINK_SEQUENCE_LEN):
        idx = h[i] % len(config.BLINK_COLORS)
        seq.append(config.BLINK_COLORS[idx])
    return seq


def blink_sequence_to_code(seq: list[str]) -> str:
    """Convert a 6-color sequence into a 3-character code via the grid."""
    from . import config
    code = ""
    for i in range(0, len(seq), 2):
        pair = (seq[i], seq[i + 1])
        code += config.BLINK_GRID[pair]
    return code


def derive_flash_sequence_from_nonce(nonce: str) -> list[str]:
    """Derive a 4-color flash sequence from nonce (Act IV transcription gate).
    Completely nonce-based (no time dependency) to avoid race conditions.
    Returns 4 colors = 2 pairs = 2 hex digits (for director flash code).
    """
    from . import config
    h = hashlib.sha256(nonce.encode()).digest()
    seq = []
    for i in range(4):  # 4 colors for 2 hex pairs
        seq.append(config.BLINK_COLORS[h[i] % len(config.BLINK_COLORS)])
    return seq


def flash_sequence_to_code(seq: list[str]) -> str:
    """Convert a 4-color flash sequence (2 pairs) into a 2-hex code via the grid."""
    from . import config
    code = ""
    for i in range(0, min(4, len(seq)), 2):
        if i + 1 < len(seq):
            pair = (seq[i], seq[i + 1])
            if pair in config.BLINK_GRID:
                code += config.BLINK_GRID[pair]
    return code


# ═══════════════════════════════════════════
# Fiat-Shamir ZKP Verification (SPEC-ACT4-ZKPWS §1.2)
# ═══════════════════════════════════════════

def verify_zkp_response(x: int, y: int, e: list[int],
                        v: list[int], N: int) -> bool:
    """Verify that y^2 ≡ x * prod(v_j^e_j) (mod N)."""
    y_squared = pow(y, 2, N)
    check = x
    for j, ej in enumerate(e):
        if ej == 1:
            check = (check * v[j]) % N
    return y_squared == check


# ═══════════════════════════════════════════
# Proof-of-Work (SPEC-ACT4-ZKPWS §3.5)
# ═══════════════════════════════════════════

def generate_pow_salt() -> str:
    """Generate a random PoW salt."""
    return f"pow_salt_{secrets.token_hex(6)}"


def verify_pow(salt: str, prefix: str, nonce: int) -> bool:
    """Verify that SHA256(salt + str(nonce)) starts with prefix."""
    candidate = f"{salt}{nonce}".encode()
    h = hashlib.sha256(candidate).hexdigest()
    return h.startswith(prefix)


# ═══════════════════════════════════════════
# AES-GCM Flag Encryption (SPEC-ACT5-OPSDEPLOY §1)
# ═══════════════════════════════════════════

def encrypt_flag(flag: str, key_material: str, aad: str) -> dict:
    """Encrypt the flag using AES-GCM.
    key = SHA256(key_material)
    Returns dict with nonce, ciphertext, tag (all hex).
    """
    key = hashlib.sha256(key_material.encode()).digest()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, flag.encode(), aad.encode())
    return {
        "nonce": nonce.hex(),
        "ciphertext": ct.hex(),
    }


def decrypt_flag(encrypted: dict, key_material: str, aad: str) -> str:
    """Decrypt the flag using AES-GCM."""
    key = hashlib.sha256(key_material.encode()).digest()
    aesgcm = AESGCM(key)
    nonce = bytes.fromhex(encrypted["nonce"])
    ct = bytes.fromhex(encrypted["ciphertext"])
    return aesgcm.decrypt(nonce, ct, aad.encode()).decode()
