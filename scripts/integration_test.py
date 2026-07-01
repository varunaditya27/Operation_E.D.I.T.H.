"""
Operation E.D.I.T.H. v5 — End-to-End Integration Test
Tests the complete authentication flow from Act II through Act V.
"""
import asyncio
import hashlib
import hmac
import json
import secrets
import time
import sys
import os

import requests
import websockets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.app.config import (
    EMPLOYEE_SECRET, STATE_KEY, ZKP_N, ZKP_SECRETS,
    ZKP_PUBLIC_KEYS, ZKP_K, POW_PREFIX,
)
from backend.app.crypto import compute_scrp_response, blink_sequence_to_code, generate_blink_sequence

BASE_URL = "http://localhost"
WS_URL = "ws://localhost"


def test_act2_scrp_auth():
    """Test Act II: SCRP Challenge-Response Authentication."""
    print("[Act II] Testing SCRP Authentication Flow...")

    # Step 1: Get challenge
    resp = requests.get(f"{BASE_URL}/api/v1/auth/challenge", params={"username": "mreyes"})
    assert resp.status_code == 200, f"Challenge request failed: {resp.status_code}"
    data = resp.json()
    challenge = data["challenge"]
    challenge_id = data["challenge_id"]
    salt = data["salt"]
    timestamp = data["timestamp"]
    print(f"  [+] Challenge: {challenge}")
    print(f"  [+] Challenge ID: {challenge_id}")

    # Step 2: Compute HMAC response
    response = compute_scrp_response(EMPLOYEE_SECRET, challenge, salt)
    print(f"  [+] HMAC Response: {response}")

    # Step 3: Generate blink code for this timestamp
    seq = generate_blink_sequence(timestamp, STATE_KEY)
    blink_code = blink_sequence_to_code(seq)
    print(f"  [+] Blink sequence: {seq} -> code: {blink_code}")

    # Step 4: Verify
    resp = requests.post(f"{BASE_URL}/api/v1/auth/verify", json={
        "username": "mreyes",
        "response": response,
        "blink_code": blink_code,
        "challenge_id": challenge_id,
        "timestamp": timestamp,
    })
    assert resp.status_code == 200, f"Verify failed: {resp.status_code} - {resp.text}"
    verify_data = resp.json()
    session_token = verify_data["session_token"]
    print(f"  [+] Session Token: {session_token}")
    print("  [+] Act II SCRP Auth: PASSED")
    return session_token


def test_employee_dashboard(session_token: str):
    """Test Act II: Employee Dashboard Access."""
    print("\n[Act II] Testing Employee Dashboard...")

    resp = requests.get(
        f"{BASE_URL}/api/v1/dashboard",
        headers={"Authorization": f"Bearer {session_token}"}
    )
    assert resp.status_code == 200, f"Dashboard failed: {resp.status_code}"
    data = resp.json()
    assert data["clearance"] == "EMPLOYEE"
    print(f"  [+] Dashboard message: {data['message']}")
    print(f"  [+] Notice: {data['notice']}")
    print("  [+] Employee Dashboard: PASSED")


def test_admin_dashboard_403(session_token: str):
    """Test Act II: Admin Dashboard should return 403."""
    print("\n[Act II] Testing Admin Dashboard (False Summit)...")

    resp = requests.get(
        f"{BASE_URL}/api/v1/admin/dashboard",
        headers={"Authorization": f"Bearer {session_token}"}
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
    data = resp.json()
    assert "Director-level" in data["error"]
    print(f"  [+] Error: {data['error']}")
    print("  [+] False Summit 403: PASSED")


async def test_act4_zkp_websocket():
    """Test Act IV: WebSocket ZKP + CAPTCHA + PoW."""
    print("\n[Act IV] Testing WebSocket ZKP Authentication...")

    async with websockets.connect(f"{WS_URL}/api/v1/admin/auth/ws") as ws:
        # Step 1: Receive server_init
        msg = json.loads(await ws.recv())
        assert msg["event"] == "server_init"
        nonce = msg["nonce"]
        captcha_image = msg["captcha_image"]
        zkp_params = msg["zkp_params"]
        print(f"  [+] Nonce: {nonce}")
        print(f"  [+] CAPTCHA type: {captcha_image[:20]}...")
        print(f"  [+] ZKP N: {zkp_params['N'][:20]}...")

        # For testing, use the debug field included by the server
        # In the real challenge, the human reads the distorted image
        captcha_text = msg.get("captcha_debug", "")
        if not captcha_text:
            captcha_text = "TEST"
        print(f"  [+] CAPTCHA text (debug): {captcha_text}")

        # Step 2: Send commitment
        N = int(zkp_params["N"], 16)
        r = secrets.randbelow(N - 1) + 1
        x = pow(r, 2, N)

        await ws.send(json.dumps({
            "event": "client_commit",
            "captcha_input": captcha_text,
            "x": hex(x),
        }))

        # Step 3: Receive challenge
        msg = json.loads(await ws.recv())
        assert msg["event"] == "server_challenge", f"Expected server_challenge, got {msg['event']}"
        e = msg["e"]
        print(f"  [+] Challenge vector e: {e}")

        # Step 4: Compute and send response
        y = r
        for j, ej in enumerate(e):
            if ej == 1:
                y = (y * ZKP_SECRETS[j]) % N

        await ws.send(json.dumps({
            "event": "client_respond",
            "y": hex(y),
        }))

        # Step 5: Receive PoW challenge
        msg = json.loads(await ws.recv())
        assert msg["event"] == "server_pow", f"Expected server_pow, got {msg['event']}"
        pow_salt = msg["salt"]
        prefix = msg["prefix"]
        print(f"  [+] PoW salt: {pow_salt}, prefix: {prefix}")

        # Step 6: Solve PoW
        counter = 0
        pow_salt_bytes = pow_salt.encode()
        sha256 = hashlib.sha256
        while True:
            candidate = pow_salt_bytes + str(counter).encode()
            h = sha256(candidate).digest()
            # Fast check for '00000' (first 2 bytes are 0, next byte is < 16)
            if h[0] == 0 and h[1] == 0 and h[2] < 16:
                break
            counter += 1
        print(f"  [+] PoW solved: nonce={counter}")

        await ws.send(json.dumps({
            "event": "client_pow_solve",
            "pow": counter,
        }))

        # Step 7: Receive flag
        msg = json.loads(await ws.recv())
        assert msg["event"] == "directors_log", f"Expected directors_log, got {msg['event']}"
        print(f"  [+] Director's Log header: {msg['header']}")
        print(f"  [+] Filed for: {msg['filed_for']}")
        print(f"  [+] Message: {msg['message'][:80]}...")
        print(f"  [+] Encrypted flag received: {list(msg['encrypted_flag'].keys())}")
        print("  [+] Act IV WebSocket ZKP: PASSED")

        return msg


def main():
    print("=" * 60)
    print("  Operation E.D.I.T.H. v5 — End-to-End Integration Test")
    print("=" * 60)
    print()

    # Act II: SCRP Auth
    session_token = test_act2_scrp_auth()

    # Act II: Employee Dashboard
    test_employee_dashboard(session_token)

    # Act II: Admin Dashboard (false summit)
    test_admin_dashboard_403(session_token)

    # Act IV: WebSocket ZKP
    result = asyncio.run(test_act4_zkp_websocket())

    print()
    print("=" * 60)
    print("  ALL INTEGRATION TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
