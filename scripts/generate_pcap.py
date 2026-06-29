"""
Operation E.D.I.T.H. v5 — HYDRA PCAP Generator
Document Ref: SPEC-ACT3-PCAPGLITCH

Generates a synthetic pcapng file containing:
  1. A Diffie-Hellman key exchange with a weak client-side LCG seed
  2. An encrypted HTTP session showing HYDRA's old admin attempt
  3. The expired nonce and full Director-tier JWT claim structure

The PCAP stream is encrypted with AES-256-CBC using a key derived
from the weak DH shared secret.
"""
import hashlib
import struct
import time
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.app.config import (
    DH_PRIME, DH_GENERATOR, DH_SERVER_PUBLIC, DH_SERVER_PRIVATE,
    DH_CLIENT_SEED, NETBIOS_ID, HOST_KEY, BUILD_EPOCH,
    ZKP_N, ZKP_PUBLIC_KEYS, ZKP_K,
)
from backend.app.crypto import lcg_sequence

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


def generate_pcapng(output_path: str):
    """Generate the HYDRA capture pcapng file."""

    # ── Derive client private key using weak LCG ──
    lcg_vals = lcg_sequence(DH_CLIENT_SEED, 2)
    client_private = (lcg_vals[0] << 32) | lcg_vals[1]
    client_public = pow(DH_GENERATOR, client_private, DH_PRIME)

    # ── Compute shared DH secret ──
    shared_secret = pow(DH_SERVER_PUBLIC, client_private, DH_PRIME)
    aes_key = hashlib.sha256(shared_secret.to_bytes(64, 'big')).digest()

    # ── Build the plaintext HTTP session data ──
    # This represents what HYDRA's old session looked like
    hydra_session = {
        "packets": [
            {
                "type": "dh_client_hello",
                "client_public": hex(client_public),
                "host": "edith-build-04.stark.internal",
                "netbios_id": NETBIOS_ID,
                "timestamp": BUILD_EPOCH - 3600,  # 1 hour before
            },
            {
                "type": "dh_server_hello",
                "server_public": hex(DH_SERVER_PUBLIC),
                "prime": hex(DH_PRIME),
                "generator": DH_GENERATOR,
            },
            {
                "type": "http_request",
                "method": "GET",
                "path": "/api/v1/session/init",
                "host": "edith-build-04.stark.internal",
            },
            {
                "type": "http_response",
                "status": 200,
                "body": {
                    "nonce": "expired_hydra_nonce_a3f8c291",
                    "expires_in": 90,
                },
            },
            {
                "type": "http_request",
                "method": "GET",
                "path": "/api/v1/admin/dashboard",
                "host": "edith-build-04.stark.internal",
                "authorization": "Bearer HYDRA_EXPIRED_TOKEN",
                "token_claims": {
                    "role": "director",
                    "shield_clearance": 3,
                    "nonce": "expired_hydra_nonce_a3f8c291",
                    "nonce_sig": "dead_signature_00",
                },
                "note": "This is the full Director-tier claim schema",
            },
            {
                "type": "http_response",
                "status": 403,
                "body": {"error": "Session nonce expired or already used."},
            },
            {
                "type": "zkp_params_observed",
                "note": "ZKP parameters observed during HYDRA's session",
                "N": hex(ZKP_N),
                "public_keys_v": [hex(v) for v in ZKP_PUBLIC_KEYS],
                "k": ZKP_K,
            },
        ],
    }

    session_json = json.dumps(hydra_session, indent=2).encode()

    # ── Encrypt the session data ──
    iv = os.urandom(16)

    if HAS_CRYPTO:
        # Pad plaintext to block size
        padder = padding.PKCS7(128).padder()
        padded = padder.update(session_json) + padder.finalize()

        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()
    else:
        # Fallback: simple XOR for environments without cryptography
        ciphertext = bytes(b ^ aes_key[i % len(aes_key)] for i, b in enumerate(session_json))

    # ── Build a minimal pcapng-like binary structure ──
    # Section Header Block (SHB)
    shb = bytearray()
    shb.extend(b"\x0A\x0D\x0D\x0A")  # Block Type
    shb_body = bytearray()
    shb_body.extend(struct.pack("<I", 0x1A2B3C4D))  # Byte Order Magic
    shb_body.extend(struct.pack("<HH", 1, 0))  # Version
    shb_body.extend(struct.pack("<q", -1))  # Section Length (unspecified)
    shb_block_len = 12 + len(shb_body) + 4
    shb.extend(struct.pack("<I", shb_block_len))
    shb.extend(shb_body)
    shb.extend(struct.pack("<I", shb_block_len))

    # Interface Description Block (IDB)
    idb = bytearray()
    idb.extend(struct.pack("<I", 1))  # Block Type
    idb_body = bytearray()
    idb_body.extend(struct.pack("<HH", 1, 0))  # Link Type: Raw IP, Reserved
    idb_body.extend(struct.pack("<I", 65535))  # Snap Length
    idb_block_len = 12 + len(idb_body) + 4
    idb.extend(struct.pack("<I", idb_block_len))
    idb.extend(idb_body)
    idb.extend(struct.pack("<I", idb_block_len))

    # Enhanced Packet Block (EPB) containing our encrypted data
    epb = bytearray()
    epb.extend(struct.pack("<I", 6))  # Block Type
    packet_data = iv + ciphertext  # IV prepended
    # Pad packet data to 4-byte boundary
    pad_len = (4 - (len(packet_data) % 4)) % 4
    padded_packet = packet_data + b"\x00" * pad_len

    epb_body = bytearray()
    epb_body.extend(struct.pack("<I", 0))  # Interface ID
    ts = int(time.time() * 1_000_000)
    epb_body.extend(struct.pack("<II", ts >> 32, ts & 0xFFFFFFFF))  # Timestamp
    epb_body.extend(struct.pack("<II", len(packet_data), len(packet_data)))  # Lengths
    epb_body.extend(padded_packet)

    epb_block_len = 12 + len(epb_body) + 4
    epb.extend(struct.pack("<I", epb_block_len))
    epb.extend(epb_body)
    epb.extend(struct.pack("<I", epb_block_len))

    # ── Write the pcapng file ──
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(shb)
        f.write(idb)
        f.write(epb)

    print(f"[+] HYDRA PCAP written to: {output_path}")
    print(f"    DH Client Seed: {hex(DH_CLIENT_SEED)}")
    print(f"    Client Private Key: {hex(client_private)}")
    print(f"    AES Key: {aes_key.hex()}")
    print(f"    IV: {iv.hex()}")
    print(f"    Encrypted payload: {len(ciphertext)} bytes")


def main():
    output = os.path.join(
        os.path.dirname(__file__), "..", "backend", "assets", "HYDRA_CAPTURE.pcapng"
    )
    generate_pcapng(output)


if __name__ == "__main__":
    main()
