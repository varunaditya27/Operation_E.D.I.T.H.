"""
Operation E.D.I.T.H. v5 — HYDRA PCAP Generator
Document Ref: SPEC-ACT3-PCAPGLITCH

Generates a synthetic pcapng file containing:
  1. Session 1 (Decoy): A failed DHCP/DH exchange on REYES-DESKTOP.
  2. Session 2 (Active): The real session containing client-side LCG seed,
     weak DH exchange, ZKP parameters, and Director-level claims.
  3. Session 3 (Decoy): An aborted system trace from HYDRA-SNIFFER.

The PCAP packets contain the AES-256-CBC encrypted session data.
"""
import hashlib
import struct
import time
import json
import os
import sys
import binascii

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.app.config import (
    DH_PRIME, DH_GENERATOR, DH_SERVER_PUBLIC, DH_SERVER_PRIVATE,
    DH_CLIENT_SEED, NETBIOS_ID, HOST_KEY, BUILD_EPOCH,
    ZKP_N, ZKP_PUBLIC_KEYS, ZKP_K, EMPLOYEE_SECRET,
)
from backend.app.crypto import lcg_sequence

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


def encrypt_payload(aes_key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    """Helper to encrypt plaintext using AES-256-CBC."""
    if HAS_CRYPTO:
        padder = padding.PKCS7(128).padder()
        padded = padder.update(plaintext) + padder.finalize()
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        return encryptor.update(padded) + encryptor.finalize()
    else:
        # Fallback: simple XOR if cryptography is missing
        return bytes(b ^ aes_key[i % len(aes_key)] for i, b in enumerate(plaintext))


def build_epb_block(iv: bytes, ciphertext: bytes, timestamp_us: int) -> bytes:
    """Build a pcapng Enhanced Packet Block (EPB)."""
    packet_data = iv + ciphertext
    pad_len = (4 - (len(packet_data) % 4)) % 4
    padded_packet = packet_data + b"\x00" * pad_len

    epb_body = bytearray()
    epb_body.extend(struct.pack("<I", 0))  # Interface ID
    epb_body.extend(struct.pack("<II", timestamp_us >> 32, timestamp_us & 0xFFFFFFFF))  # Timestamp
    epb_body.extend(struct.pack("<II", len(packet_data), len(packet_data)))  # Captured & Original Length
    epb_body.extend(padded_packet)

    # pcapng block: Type(4) + Length(4) + Body(N) + Length(4)
    epb_block_len = 4 + 4 + len(epb_body) + 4
    epb = bytearray()
    epb.extend(struct.pack("<I", 6))  # Block Type (6 = EPB)
    epb.extend(struct.pack("<I", epb_block_len))
    epb.extend(epb_body)
    epb.extend(struct.pack("<I", epb_block_len))
    return bytes(epb)


def generate_pcapng(output_path: str):
    """Generate the multi-session HYDRA capture pcapng file."""

    # ══════════════════════════════════════════════════════════
    # SESSION 1: DECOY (REYES-DESKTOP)
    # ══════════════════════════════════════════════════════════
    decoy_seed1 = binascii.crc32(b"REYES-DESKTOP") ^ BUILD_EPOCH
    decoy_lcg1 = lcg_sequence(decoy_seed1, 2)
    decoy_private1 = (decoy_lcg1[0] << 32) | decoy_lcg1[1]
    decoy_public1 = pow(DH_GENERATOR, decoy_private1, DH_PRIME)
    decoy_shared1 = pow(DH_SERVER_PUBLIC, decoy_private1, DH_PRIME)
    decoy_key1 = hashlib.sha256(decoy_shared1.to_bytes(64, 'big')).digest()

    session1_data = {
        "packets": [
            {
                "type": "dh_client_hello",
                "client_public": hex(decoy_public1),
                "host": "edith-build-04.stark.internal",
                "netbios_id": "REYES-DESKTOP",
                "timestamp": BUILD_EPOCH - 7200,  # 2 hours before
            },
            {
                "type": "http_response",
                "status": 401,
                "body": {"error": "Access Denied: MAC validation mismatch. Host: REYES-DESKTOP."}
            }
        ]
    }
    json1 = json.dumps(session1_data, indent=2).encode()
    iv1 = os.urandom(16)
    cipher1 = encrypt_payload(decoy_key1, iv1, json1)

    # ══════════════════════════════════════════════════════════
    # SESSION 2: ACTIVE (REYES-LAPTOP) - Real challenge path
    # ══════════════════════════════════════════════════════════
    lcg_vals = lcg_sequence(DH_CLIENT_SEED, 2)
    client_private = (lcg_vals[0] << 32) | lcg_vals[1]
    client_public = pow(DH_GENERATOR, client_private, DH_PRIME)
    shared_secret = pow(DH_SERVER_PUBLIC, client_private, DH_PRIME)
    aes_key = hashlib.sha256(shared_secret.to_bytes(64, 'big')).digest()

    session2_data = {
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
    json2 = json.dumps(session2_data, indent=2).encode()
    iv2 = os.urandom(16)
    cipher2 = encrypt_payload(aes_key, iv2, json2)

    # ══════════════════════════════════════════════════════════
    # SESSION 3: DECOY (HYDRA-SNIFFER)
    # ══════════════════════════════════════════════════════════
    decoy_seed3 = 987654321
    decoy_lcg3 = lcg_sequence(decoy_seed3, 2)
    decoy_private3 = (decoy_lcg3[0] << 32) | decoy_lcg3[1]
    decoy_public3 = pow(DH_GENERATOR, decoy_private3, DH_PRIME)
    decoy_shared3 = pow(DH_SERVER_PUBLIC, decoy_private3, DH_PRIME)
    decoy_key3 = hashlib.sha256(decoy_shared3.to_bytes(64, 'big')).digest()

    session3_data = {
        "packets": [
            {
                "type": "sniff_report",
                "source": "HYDRA-SNIFFER",
                "msg": "Intercepting traffic. WARNING: cryptographic signature verification failed.",
                "timestamp": BUILD_EPOCH - 1800,  # 30 mins before
            }
        ]
    }
    json3 = json.dumps(session3_data, indent=2).encode()
    iv3 = os.urandom(16)
    cipher3 = encrypt_payload(decoy_key3, iv3, json3)

    # ══════════════════════════════════════════════════════════
    # SESSION 4: DECOY (REYES-WORKSTATION) - Wrong ZKP parameters
    # Phase D.5: 4th decoy packet with invalid ZKP N value
    # ══════════════════════════════════════════════════════════
    decoy_seed4 = binascii.crc32(b"REYES-WORKSTATION") ^ BUILD_EPOCH
    decoy_lcg4 = lcg_sequence(decoy_seed4, 2)
    decoy_private4 = (decoy_lcg4[0] << 32) | decoy_lcg4[1]
    decoy_public4 = pow(DH_GENERATOR, decoy_private4, DH_PRIME)
    decoy_shared4 = pow(DH_SERVER_PUBLIC, decoy_private4, DH_PRIME)
    decoy_key4 = hashlib.sha256(decoy_shared4.to_bytes(64, 'big')).digest()

    # Wrong ZKP parameters (different N, different public keys) - solver trap
    wrong_p = 0xFFEEDEADBEEFCAFEBABEFACEDEADC0DEDEADBEEFCAFEBABEDEADBEEFCAFEBABE1
    wrong_q = 0xDEADCAFEBABEFACEDEADC0DEDEADBEEFCAFEBABEDEADBEEFCAFEBABEFACED0D7
    wrong_zkp_n = wrong_p * wrong_q
    wrong_zkp_secrets = [
        int.from_bytes(hashlib.sha256(EMPLOYEE_SECRET + i.to_bytes(1, 'big')).digest()[:8], 'big') % wrong_zkp_n
        for i in range(ZKP_K)
    ]
    wrong_zkp_public = [pow(s, 2, wrong_zkp_n) for s in wrong_zkp_secrets]

    session4_data = {
        "packets": [
            {
                "type": "dh_client_hello",
                "client_public": hex(decoy_public4),
                "host": "edith-build-04.stark.internal",
                "netbios_id": "REYES-WORKSTATION",
                "timestamp": BUILD_EPOCH - 900,  # 15 mins before
            },
            {
                "type": "zkp_params_observed_alternate",
                "note": "Alternate ZKP parameters (decoy — modulus is composite of different primes)",
                "N": hex(wrong_zkp_n),
                "public_keys_v": [hex(v) for v in wrong_zkp_public],
                "k": ZKP_K,
                "alert": "WARNING: If you use these ZKP parameters, factorization will fail.",
            },
            {
                "type": "http_response",
                "status": 403,
                "body": {"error": "ZKP verification failed"},
            }
        ]
    }
    json4 = json.dumps(session4_data, indent=2).encode()
    iv4 = os.urandom(16)
    cipher4 = encrypt_payload(decoy_key4, iv4, json4)

    # ══════════════════════════════════════════════════════════
    # PCAPNG Structure Builder
    # ══════════════════════════════════════════════════════════
    # Section Header Block (SHB)
    # pcapng SHB: Magic(4) + Length(4) + Body(N) + Length(4)
    shb = bytearray()
    shb.extend(b"\x0A\x0D\x0D\x0A")  # Magic (not counted in block length)
    shb_body = bytearray()
    shb_body.extend(struct.pack("<I", 0x1A2B3C4D))  # Byte Order
    shb_body.extend(struct.pack("<HH", 1, 0))  # Version
    shb_body.extend(struct.pack("<q", -1))  # Section Length
    shb_block_len = 4 + 4 + len(shb_body) + 4  # Length field + Body + Length field (repeated)
    shb.extend(struct.pack("<I", shb_block_len))
    shb.extend(shb_body)
    shb.extend(struct.pack("<I", shb_block_len))

    # Interface Description Block (IDB)
    idb = bytearray()
    idb.extend(struct.pack("<I", 1))  # Block Type = 1 (Interface Description Block)
    idb_body = bytearray()
    idb_body.extend(struct.pack("<HH", 1, 0))  # Link Type (Raw IP), Reserved
    idb_body.extend(struct.pack("<I", 65535))  # Snap len
    # pcapng block: Type(4) + Length(4) + Body(N) + Length(4)
    idb_block_len = 4 + 4 + len(idb_body) + 4  # Total block size
    idb = bytearray()  # Rebuild correctly
    idb.extend(struct.pack("<I", 1))  # Block Type
    idb.extend(struct.pack("<I", idb_block_len))  # Block Length
    idb.extend(idb_body)
    idb.extend(struct.pack("<I", idb_block_len))  # Block Length (repeated)

    # Build individual EPB packets
    now_us = int(time.time() * 1_000_000)
    epb1 = build_epb_block(iv1, cipher1, now_us - 7200 * 1000000)
    epb2 = build_epb_block(iv2, cipher2, now_us - 3600 * 1000000)
    epb3 = build_epb_block(iv3, cipher3, now_us - 1800 * 1000000)
    epb4 = build_epb_block(iv4, cipher4, now_us - 900 * 1000000)  # 4th decoy (Phase D.5)

    # ── Write the pcapng file ──
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(shb)
        f.write(idb)
        f.write(epb1)
        f.write(epb2)
        f.write(epb3)
        f.write(epb4)  # 4th decoy with wrong ZKP parameters

    print(f"[+] HYDRA PCAP written to: {output_path}")
    print(f"    Active Client Private Key: {hex(client_private)}")
    print(f"    Active AES Key: {aes_key.hex()}")
    print(f"    Active IV: {iv2.hex()}")
    print(f"    Packets generated: 4 sessions (decoy1, active2, decoy3, decoy4-wrong-zkp)")


def main():
    output = os.path.join(
        os.path.dirname(__file__), "..", "backend", "assets", "HYDRA_CAPTURE.pcapng"
    )
    generate_pcapng(output)


if __name__ == "__main__":
    main()
