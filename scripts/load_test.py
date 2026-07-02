#!/usr/bin/env python3
"""
Load testing for Operation E.D.I.T.H. — 100 concurrent users
Simulates the full workflow: login → dashboard → ZKP → flag
"""

import asyncio
import aiohttp
import websockets
import json
import hashlib
import hmac
import time
import random
import statistics
from typing import Optional

# Configuration
BASE_URL = "http://localhost:8000"
WS_BASE = "ws://localhost:8000"
NUM_USERS = 100
THINK_TIME = 0.1  # Reduced for load testing

# From config
MACHINE_GUID = "7948eaa2-7dfd-417d-8fb4-f8b9e2a930e3"
BUILD_EPOCH = 1781259200
SHIFT_OFFSET = 427
EMPLOYEE_SECRET_HEX = "88efe0e88666e91ec78202f720de4b74"

# Timing metrics
metrics = {
    "challenge_times": [],
    "verify_times": [],
    "dashboard_times": [],
    "zkp_times": [],
    "errors": [],
    "successes": 0,
}


async def get_challenge(session: aiohttp.ClientSession) -> dict:
    """Fetch SCRP challenge."""
    start = time.time()
    try:
        async with session.get(f"{BASE_URL}/api/v1/auth/challenge?username=mreyes") as resp:
            if resp.status == 200:
                data = await resp.json()
                elapsed = time.time() - start
                metrics["challenge_times"].append(elapsed)
                return data
            else:
                metrics["errors"].append(f"challenge returned {resp.status}")
                return None
    except Exception as e:
        metrics["errors"].append(f"challenge error: {e}")
        return None


async def compute_hmac_and_blink(challenge: dict) -> tuple:
    """Compute HMAC and blink code."""
    employee_secret = bytes.fromhex(EMPLOYEE_SECRET_HEX)
    salt = challenge["salt"]
    timestamp = challenge["timestamp"]

    # Compute HMAC-SHA256
    msg = (challenge["challenge"] + salt).encode()
    hmac_result = hmac.new(employee_secret, msg, hashlib.sha256).hexdigest()

    # Compute blink code from timestamp
    window = timestamp // 1800
    seed_str = f"{salt}:{window}"
    h = hashlib.sha256(seed_str.encode()).digest()

    BLINK_COLORS = ["R", "G", "B", "Y"]
    BLINK_GRID = {
        ("R", "R"): "S", ("R", "G"): "A", ("R", "B"): "9", ("R", "Y"): "M",
        ("G", "R"): "K", ("G", "G"): "1", ("G", "B"): "T", ("G", "Y"): "E",
        ("B", "R"): "F", ("B", "G"): "P", ("B", "B"): "8", ("B", "Y"): "V",
        ("Y", "R"): "Z", ("Y", "G"): "U", ("Y", "B"): "Q", ("Y", "Y"): "W",
    }

    sequence = [BLINK_COLORS[h[i] % 4] for i in range(6)]
    code = ""
    for i in range(0, 6, 2):
        pair = (sequence[i], sequence[i + 1])
        code += BLINK_GRID.get(pair, "?")

    return hmac_result, code[:3]


async def verify_auth(
    session: aiohttp.ClientSession, challenge: dict, hmac_result: str, blink_code: str
) -> Optional[str]:
    """Verify authentication and get session token."""
    start = time.time()
    try:
        async with session.post(
            f"{BASE_URL}/api/v1/auth/verify",
            json={
                "username": "mreyes",
                "response": hmac_result,
                "blink_code": blink_code,
                "challenge_id": challenge["challenge_id"],
                "timestamp": challenge["timestamp"],
            },
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                elapsed = time.time() - start
                metrics["verify_times"].append(elapsed)
                return data.get("session_token")
            else:
                metrics["errors"].append(f"verify returned {resp.status}")
                return None
    except Exception as e:
        metrics["errors"].append(f"verify error: {e}")
        return None


async def get_dashboard(session: aiohttp.ClientSession, token: str) -> bool:
    """Access dashboard."""
    start = time.time()
    try:
        async with session.get(
            f"{BASE_URL}/api/v1/dashboard", headers={"Authorization": f"Bearer {token}"}
        ) as resp:
            if resp.status == 200:
                elapsed = time.time() - start
                metrics["dashboard_times"].append(elapsed)
                return True
            else:
                metrics["errors"].append(f"dashboard returned {resp.status}")
                return False
    except Exception as e:
        metrics["errors"].append(f"dashboard error: {e}")
        return False


async def test_zkp_connection(token: str) -> bool:
    """Test WebSocket ZKP connection."""
    start = time.time()
    try:
        # Get nonce first
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BASE_URL}/api/v1/session/init",
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                if resp.status != 200:
                    metrics["errors"].append("session/init failed")
                    return False
                session_data = await resp.json()
                nonce = session_data.get("nonce")
                flash_sequence = session_data.get("flash_sequence", [])

        # Try to connect to WebSocket
        if not nonce or not flash_sequence:
            metrics["errors"].append("invalid nonce or flash sequence")
            return False

        # Derive flash code
        BLINK_GRID = {
            ("R", "R"): "S", ("R", "G"): "A", ("R", "B"): "9", ("R", "Y"): "M",
            ("G", "R"): "K", ("G", "G"): "1", ("G", "B"): "T", ("G", "Y"): "E",
            ("B", "R"): "F", ("B", "G"): "P", ("B", "B"): "8", ("B", "Y"): "V",
            ("Y", "R"): "Z", ("Y", "G"): "U", ("Y", "B"): "Q", ("Y", "Y"): "W",
        }
        code = ""
        for i in range(0, min(len(flash_sequence), 4), 2):
            if i + 1 < len(flash_sequence):
                pair = (flash_sequence[i], flash_sequence[i + 1])
                code += BLINK_GRID.get(pair, "?")

        # Attempt WebSocket connection (don't actually complete handshake)
        ws_url = f"{WS_BASE}/api/v1/admin/auth/ws?pcap_token=dummy&nonce={nonce}&flash_code={code}"
        try:
            async with websockets.connect(ws_url, timeout=2) as ws:
                # Just verify we can connect and receive server_init
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                data = json.loads(msg)
                if data.get("event") == "server_init":
                    elapsed = time.time() - start
                    metrics["zkp_times"].append(elapsed)
                    return True
                else:
                    metrics["errors"].append("invalid server_init")
                    return False
        except asyncio.TimeoutError:
            metrics["errors"].append("WebSocket timeout")
            return False
        except websockets.exceptions.WebSocketException as e:
            # Expected since we don't have valid pcap_token
            metrics["errors"].append(f"WebSocket error: {str(e)[:50]}")
            return False

    except Exception as e:
        metrics["errors"].append(f"zkp connection error: {e}")
        return False


async def user_workflow(user_id: int):
    """Simulate one user's complete workflow."""
    connector = aiohttp.TCPConnector(limit=100)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Step 1: Get challenge
        challenge = await get_challenge(session)
        if not challenge:
            return False
        await asyncio.sleep(THINK_TIME)

        # Step 2: Compute HMAC and blink code
        hmac_result, blink_code = await compute_hmac_and_blink(challenge)
        await asyncio.sleep(THINK_TIME)

        # Step 3: Verify auth
        token = await verify_auth(session, challenge, hmac_result, blink_code)
        if not token:
            return False
        await asyncio.sleep(THINK_TIME)

        # Step 4: Get dashboard
        if not await get_dashboard(session, token):
            return False
        await asyncio.sleep(THINK_TIME)

        # Step 5: Test ZKP connection (simplified)
        if await test_zkp_connection(token):
            metrics["successes"] += 1
            return True
        return False


async def run_load_test():
    """Run load test with 100 concurrent users."""
    print("=" * 70)
    print("  LOAD TEST — Operation E.D.I.T.H. (100 Concurrent Users)")
    print("=" * 70)
    print(f"\n[*] Starting {NUM_USERS} concurrent user simulations...")
    print(f"[*] Base URL: {BASE_URL}")

    start_time = time.time()

    # Run all users concurrently
    tasks = [user_workflow(i) for i in range(NUM_USERS)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    elapsed = time.time() - start_time

    # Print results
    print("\n" + "=" * 70)
    print("  RESULTS")
    print("=" * 70)

    successful = sum(1 for r in results if r is True)
    failed = NUM_USERS - successful

    print(f"\n✅ Successful: {successful}/{NUM_USERS}")
    print(f"❌ Failed: {failed}/{NUM_USERS}")
    print(f"⏱️  Total Time: {elapsed:.2f}s")
    print(f"📊 Throughput: {NUM_USERS/elapsed:.2f} users/second")

    # Print metrics
    if metrics["challenge_times"]:
        print(f"\n📈 Challenge API:")
        print(f"  Mean: {statistics.mean(metrics['challenge_times']):.3f}s")
        print(f"  p95:  {sorted(metrics['challenge_times'])[int(len(metrics['challenge_times'])*0.95)]:.3f}s")

    if metrics["verify_times"]:
        print(f"\n📈 Verify API:")
        print(f"  Mean: {statistics.mean(metrics['verify_times']):.3f}s")
        print(f"  p95:  {sorted(metrics['verify_times'])[int(len(metrics['verify_times'])*0.95)]:.3f}s")

    if metrics["dashboard_times"]:
        print(f"\n📈 Dashboard API:")
        print(f"  Mean: {statistics.mean(metrics['dashboard_times']):.3f}s")
        print(f"  p95:  {sorted(metrics['dashboard_times'])[int(len(metrics['dashboard_times'])*0.95)]:.3f}s")

    if metrics["errors"]:
        print(f"\n⚠️  Errors ({len(metrics['errors'])}):")
        error_counts = {}
        for error in metrics["errors"]:
            error_counts[error] = error_counts.get(error, 0) + 1

        for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  [{count}x] {error}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(run_load_test())
