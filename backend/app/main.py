"""
Operation E.D.I.T.H. v5 — FastAPI Backend Application
Document Refs: All SPEC documents

Complete API implementation covering:
  - Act II: SCRP challenge-response auth, employee dashboard
  - Act III: PCAP release gating, hydra-clock
  - Act IV: WebSocket ZKP + CAPTCHA + PoW
  - Act V: Flag encryption and delivery
"""
import asyncio
import json
import time
import secrets
import hashlib
import os
import numpy as np

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from . import config
from . import crypto
from . import database
from .captcha import generate_captcha

app = FastAPI(
    title="Stark Employee Portal — SHIELD Auth Gateway",
    version="5.0.0",
    docs_url=None,  # Disable Swagger UI in production
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    database.init_db()
    # Pre-encrypt the flag for this server instance
    app.state.hydra_boot_time = int(time.time())


# ══════════════════════════════════════════════════════════
# Utility: Rate limiting middleware
# ══════════════════════════════════════════════════════════

def _get_client_ip(request: Request) -> str:
    # Use X-Real-IP (set by nginx real_ip directives), fall back to direct socket IP
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def _check_rate(request: Request):
    ip = _get_client_ip(request)
    if not database.check_rate_limit(ip, config.RATE_LIMIT_MAX):
        raise HTTPException(status_code=429, detail="Too Many Requests. Try again in 3 minutes.")


# ══════════════════════════════════════════════════════════
# Act I Endpoint: Login (permanently disabled, lore)
# ══════════════════════════════════════════════════════════

@app.post("/api/v1/auth/login")
async def auth_login():
    """Always 401 — production auth permanently disabled."""
    return JSONResponse(
        status_code=401,
        content={"error": "Nice try, HYDRA."}
    )


# ══════════════════════════════════════════════════════════
# Act I Endpoint: Debug token (red herring, 404)
# ══════════════════════════════════════════════════════════

@app.get("/internal/debug/token")
async def debug_token():
    """404 — exists only because strings finds it in the binary."""
    return JSONResponse(status_code=404, content={"error": "Not Found"})


# ══════════════════════════════════════════════════════════
# Act II: SCRP Authentication (SPEC-ACT2-WEBPORTAL §4)
# ══════════════════════════════════════════════════════════

@app.get("/api/v1/auth/challenge")
async def get_challenge(request: Request, username: str = "mreyes"):
    """Issue a SCRP challenge."""
    _check_rate(request)
    challenge = crypto.generate_challenge()
    challenge_id = secrets.token_hex(8)
    ts = int(time.time())

    database.store_challenge(challenge_id, challenge, username)

    return {
        "challenge_id": challenge_id,
        "challenge": challenge,
        "salt": config.STATE_KEY,
        "timestamp": ts,
    }


@app.post("/api/v1/auth/verify")
async def verify_auth(request: Request):
    """Verify SCRP response + blink code."""
    _check_rate(request)
    body = await request.json()

    username = body.get("username", "")
    response = body.get("response", "")
    blink_code = body.get("blink_code", "")
    challenge_id = body.get("challenge_id", "")
    timestamp = body.get("timestamp", 0)

    # Validate timestamp is within ±10 seconds
    now = int(time.time())
    if abs(now - timestamp) > 10:
        return JSONResponse(status_code=403, content={"error": "Challenge expired."})

    # Retrieve and consume challenge
    stored = database.get_and_consume_challenge(challenge_id)
    if not stored:
        return JSONResponse(status_code=403, content={"error": "Invalid or expired challenge."})

    # Verify HMAC response
    expected = crypto.compute_scrp_response(
        config.EMPLOYEE_SECRET, stored["challenge"], config.STATE_KEY
    )
    if response != expected:
        return JSONResponse(
            status_code=403,
            content={"error": "Unauthorized SHIELD personnel."}
        )

    # Verify blink code for this timestamp window
    seq = crypto.generate_blink_sequence(timestamp, config.STATE_KEY)
    expected_code = crypto.blink_sequence_to_code(seq)
    if blink_code != expected_code:
        return JSONResponse(
            status_code=403,
            content={"error": "Calibration sequence mismatch."}
        )

    # Issue session token
    session_token = f"sess_{secrets.token_hex(12)}"
    database.create_session(session_token, username, ttl=90)

    return {
        "status": "success",
        "session_token": session_token,
        "expires_in": 90,
    }


# ══════════════════════════════════════════════════════════
# Act II: Employee Dashboard
# ══════════════════════════════════════════════════════════

@app.get("/api/v1/dashboard")
async def employee_dashboard(request: Request):
    """Employee-tier dashboard. Requires valid session token."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(status_code=403, content={"error": "Unauthorized SHIELD personnel."})

    token = auth[7:]
    session = database.validate_session(token)
    if not session:
        return JSONResponse(status_code=403, content={"error": "Session expired or invalid."})

    # Mark dashboard accessed → triggers PCAP release
    database.mark_dashboard_accessed(token)

    return {
        "status": "authenticated",
        "clearance": "EMPLOYEE",
        "username": session["username"],
        "message": "Welcome to the Stark Industries Employee Portal.",
        "portal_status": "FALLBACK MODE ACTIVE",
        "notice": "Director-level clearance is NOT covered by this fallback.",
    }


# ══════════════════════════════════════════════════════════
# Act II.5: Resonance Gate / Calibration (SPEC-ACT2-WEBPORTAL §12)
# ══════════════════════════════════════════════════════════

@app.get("/api/v1/calibrate/target")
async def calibrate_target(request: Request):
    """Return pre-sampled coordinate pairs for the Reference Wave (target).
    Target values (freq, phase, amp, skew) are NEVER transmitted — only coordinates.
    Requires valid Act II session token.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(status_code=403, content={"error": "Unauthorized SHIELD personnel."})

    token = auth[7:]
    session = database.validate_session(token)
    if not session:
        return JSONResponse(status_code=403, content={"error": "Session expired or invalid."})

    # Generate 300 pre-sampled points for the target waveform
    # Using only the published parameters (never expose freq/phase/amp/skew numerically)
    points = []
    x_vals = np.linspace(0, 2 * np.pi, 300)
    for x in x_vals:
        y = (config.RESONANCE_AMP *
             np.sin(config.RESONANCE_FREQ * x + config.RESONANCE_PHASE) +
             config.RESONANCE_SKEW)
        points.append({"x": float(x), "y": float(y)})

    return {
        "target": points,
        "canvas_width": 800,
        "canvas_height": 400,
        "x_range": [0, 2 * np.pi],
        "y_range": [-1.5, 1.5],
    }


@app.post("/api/v1/calibrate/submit")
async def calibrate_submit(request: Request):
    """Accept user's tuned (freq, phase, amp, skew) and verify against target.
    Returns ONLY pass/fail — NO gradient, NO distance, NO direction hint.
    Rate-limited to 6 attempts per minute per session.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(status_code=403, content={"error": "Unauthorized SHIELD personnel."})

    token = auth[7:]
    session = database.validate_session(token)
    if not session:
        return JSONResponse(status_code=403, content={"error": "Session expired or invalid."})

    # Rate limiting: 6 attempts per minute
    attempts = session.get("calibrate_attempts", 0)
    if attempts >= config.CALIBRATE_RATE_LIMIT_MAX:
        return JSONResponse(
            status_code=429,
            content={"error": "Calibration attempt limit exceeded. Try again in 1 minute."}
        )

    body = await request.json()
    user_freq = body.get("freq", None)
    user_phase = body.get("phase", None)
    user_amp = body.get("amp", None)
    user_skew = body.get("skew", None)

    if None in [user_freq, user_phase, user_amp, user_skew]:
        return JSONResponse(status_code=400, content={"error": "Missing calibration parameters"})

    # Increment attempt counter
    database.increment_calibrate_attempts(token)

    # Check tolerance (binary pass/fail only)
    freq_pass = abs(user_freq - config.RESONANCE_FREQ) <= config.RESONANCE_TOLERANCE["freq"]
    phase_pass = abs(user_phase - config.RESONANCE_PHASE) <= config.RESONANCE_TOLERANCE["phase"]
    amp_pass = abs(user_amp - config.RESONANCE_AMP) <= config.RESONANCE_TOLERANCE["amp"]
    skew_pass = abs(user_skew - config.RESONANCE_SKEW) <= config.RESONANCE_TOLERANCE["skew"]

    passed = freq_pass and phase_pass and amp_pass and skew_pass

    if passed:
        database.mark_calibrated(token)
        return {"pass": True, "message": "Resonance calibration successful. Proceed to Director authentication."}
    else:
        return {"pass": False, "message": "Calibration parameters do not match. Adjust and try again."}


@app.post("/api/v1/session/init")
async def session_init(request: Request):
    """Initialize Director-tier session.
    Requires:
    1. Valid Act II session token
    2. Calibration gate passed (calibrated=1)
    Returns nonce for Act IV WebSocket challenge + flash_sequence_token.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(status_code=403, content={"error": "Unauthorized SHIELD personnel."})

    token = auth[7:]
    session = database.validate_session(token)
    if not session:
        return JSONResponse(status_code=403, content={"error": "Session expired or invalid."})

    # Check calibration gate
    if not database.is_calibrated(token):
        return JSONResponse(
            status_code=403,
            content={"error": "Live calibration required. — SHIELD"}
        )

    # Issue nonce for Act IV
    nonce = secrets.token_hex(8)
    database.create_nonce(nonce, ttl=300)  # 5 minute window

    # Derive flash sequence from nonce
    flash_seq = crypto.generate_blink_sequence(int(time.time()), nonce)
    flash_code = crypto.blink_sequence_to_code(flash_seq)

    return {
        "status": "ready",
        "nonce": nonce,
        "flash_sequence": flash_seq,  # 5-color sequence for visual display
        "flash_code": flash_code,
        "message": "Director authentication window now open. 5 minute limit.",
    }


# ══════════════════════════════════════════════════════════
# Act II: Admin Dashboard (false summit — 403)
# ══════════════════════════════════════════════════════════

@app.get("/api/v1/admin/dashboard")
async def admin_dashboard(request: Request):
    """Director-tier dashboard. Always 403 via HTTP — must use WebSocket."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(status_code=403, content={"error": "Unauthorized SHIELD personnel."})

    token = auth[7:]
    session = database.validate_session(token)
    if not session:
        return JSONResponse(status_code=403, content={"error": "Session expired or invalid."})

    return JSONResponse(
        status_code=403,
        content={"error": "Director-level cryptographic proof required. — SHIELD"}
    )


# ══════════════════════════════════════════════════════════
# Act III: PCAP Release Gating (SPEC-ACT5-OPSDEPLOY §3.2)
# ══════════════════════════════════════════════════════════

@app.get("/api/v1/artifacts/hydra-capture")
async def get_hydra_capture(request: Request):
    """Serve the HYDRA pcap only after dashboard access."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(status_code=403, content={"error": "Authentication required."})

    token = auth[7:]
    if not database.is_pcap_released(token):
        return JSONResponse(
            status_code=403,
            content={"error": "Artifact not yet available. Complete prior objectives first."}
        )

    pcap_path = os.path.join(os.path.dirname(__file__), "..", "assets", "HYDRA_CAPTURE.pcapng")
    if not os.path.exists(pcap_path):
        return JSONResponse(status_code=404, content={"error": "Artifact not found on server."})

    return FileResponse(pcap_path, filename="HYDRA_CAPTURE.pcapng")


# ══════════════════════════════════════════════════════════
# Act III: HYDRA Clock (atmospheric, SPEC-ACT5-OPSDEPLOY)
# ══════════════════════════════════════════════════════════

@app.get("/api/v1/meta/hydra-clock")
async def hydra_clock():
    """Returns time until next HYDRA re-key tick (10-minute cycle, boot-relative)."""
    elapsed = int(time.time()) - app.state.hydra_boot_time
    cycle = 600  # 10 minutes
    next_tick = cycle - (elapsed % cycle)
    return {"next_tick_in": next_tick, "cycle_seconds": cycle}


# ══════════════════════════════════════════════════════════
# Utility: Ping (for RTT measurement, Act III timing glitch)
# ══════════════════════════════════════════════════════════

@app.get("/api/v1/auth/ping")
async def auth_ping():
    """Simple ping endpoint for RTT measurement."""
    return {"pong": True, "timestamp": int(time.time() * 1000)}


# ══════════════════════════════════════════════════════════
# Act IV: WebSocket ZKP + CAPTCHA + PoW (SPEC-ACT4-ZKPWS)
# ══════════════════════════════════════════════════════════

@app.websocket("/api/v1/admin/auth/ws")
async def admin_auth_ws(websocket: WebSocket):
    """Interactive ZKP authentication WebSocket.

    Protocol flow (SPEC-ACT4-ZKPWS §3):
    1. Server sends: server_init (nonce + captcha)
    2. Client sends: client_commit (captcha_input + x)      [1s timeout]
    3. Server sends: server_challenge (e vector)
    4. Client sends: client_respond (y)                      [1s timeout]
    5. Server sends: server_pow (salt + prefix)
    6. Client sends: client_pow_solve (pow nonce)            [1s timeout]
    7. Server sends: success + encrypted flag
    """
    await websocket.accept()

    timeout = config.POW_TIMEOUT_MS / 1000.0  # 1.0 second

    try:
        # ─── Step 1: Server Init ───
        nonce = secrets.token_hex(8)
        captcha_text, captcha_image = generate_captcha()

        # Store nonce
        database.create_nonce(nonce, ttl=90)

        await websocket.send_json({
            "event": "server_init",
            "nonce": nonce,
            "captcha_image": captcha_image,
            "zkp_params": {
                "N": hex(config.ZKP_N),
                "v": [hex(v) for v in config.ZKP_PUBLIC_KEYS],
                "k": config.ZKP_K,
            },
        })

        # ─── Step 2: Client Commitment [1s timeout] ───
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
        except asyncio.TimeoutError:
            await websocket.close(code=4008, reason="Clearance Timeout Exceeded")
            return

        commit_data = json.loads(raw)
        if commit_data.get("event") != "client_commit":
            await websocket.close(code=4003, reason="Unauthorized Cryptographic Claims")
            return

        # Verify CAPTCHA
        if commit_data.get("captcha_input", "").upper() != captcha_text.upper():
            await websocket.close(code=4003, reason="CAPTCHA verification failed")
            return

        # Parse commitment x
        try:
            x = int(commit_data["x"], 16)
        except (ValueError, KeyError):
            await websocket.close(code=4003, reason="Invalid commitment value")
            return

        # ─── Step 3: Server Challenge ───
        e = [secrets.randbelow(2) for _ in range(config.ZKP_K)]

        await websocket.send_json({
            "event": "server_challenge",
            "e": e,
        })

        # ─── Step 4: Client Response [1s timeout] ───
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
        except asyncio.TimeoutError:
            await websocket.close(code=4008, reason="Clearance Timeout Exceeded")
            return

        respond_data = json.loads(raw)
        if respond_data.get("event") != "client_respond":
            await websocket.close(code=4003, reason="Unauthorized Cryptographic Claims")
            return

        try:
            y = int(respond_data["y"], 16)
        except (ValueError, KeyError):
            await websocket.close(code=4003, reason="Invalid response value")
            return

        # Verify ZKP: y^2 ≡ x * prod(v_j^e_j) (mod N)
        if not crypto.verify_zkp_response(x, y, e, config.ZKP_PUBLIC_KEYS, config.ZKP_N):
            await websocket.close(code=4003, reason="ZKP verification failed")
            return

        # ─── Step 5: Proof-of-Work ───
        pow_salt = crypto.generate_pow_salt()

        await websocket.send_json({
            "event": "server_pow",
            "salt": pow_salt,
            "prefix": config.POW_PREFIX,
        })

        # ─── Step 6: Client PoW Solution [1s timeout] ───
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
        except asyncio.TimeoutError:
            await websocket.close(code=4008, reason="Clearance Timeout Exceeded")
            return

        pow_data = json.loads(raw)
        if pow_data.get("event") != "client_pow_solve":
            await websocket.close(code=4003, reason="Unauthorized Cryptographic Claims")
            return

        pow_nonce = pow_data.get("pow", -1)
        if not crypto.verify_pow(pow_salt, config.POW_PREFIX, pow_nonce):
            await websocket.close(code=4003, reason="Proof-of-Work verification failed")
            return

        # Consume the nonce
        if not database.validate_and_consume_nonce(nonce):
            await websocket.close(code=4003, reason="Session nonce expired or already used.")
            return

        # ─── Step 7: Success — Encrypt and deliver flag ───
        # Build key material from ZKP transaction
        # K_flag = SHA256(concat of s_i hex + y hex + pow_nonce)
        key_parts = "".join(hex(s) for s in config.ZKP_SECRETS)
        key_parts += hex(y) + str(pow_nonce)
        key_material = key_parts

        encrypted_flag = crypto.encrypt_flag(
            config.FLAG_PLAINTEXT,
            key_material,
            aad=nonce,  # use nonce as AAD
        )

        # Build the Director's Log
        directors_log = {
            "event": "directors_log",
            "header": "SHIELD INTERNAL — DIRECTOR'S LOG",
            "filed_for": "Director Hale",
            "subject": "Employee Portal incident, follow-up",
            "clearance_level": 3,
            "session_nonce": nonce,
            "closed": int(time.time()),
            "message": (
                "The fallback was real. HYDRA found it weeks ago and never finished "
                "the job. You did.\n\n"
                "Production auth restoration is still pending committee review. "
                "Don't expect a quiet six weeks next time either."
            ),
            "encrypted_flag": encrypted_flag,
            "key_material_hint": (
                "K_flag = SHA256(concat(hex(s_i) for i in range(k)) + hex(y_live) + str(pow_nonce))"
            ),
        }

        await websocket.send_json(directors_log)
        await websocket.close(code=1000, reason="Authentication complete")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.close(code=4003, reason=f"Internal error: {str(e)[:50]}")
        except Exception:
            pass


# ══════════════════════════════════════════════════════════
# Meta: Server info for debugging
# ══════════════════════════════════════════════════════════

@app.get("/api/v1/meta/info")
async def server_info():
    """Public server metadata."""
    return {
        "server": "Stark Employee Portal — SHIELD Auth Gateway",
        "version": "5.0.0",
        "status": "FALLBACK MODE",
        "auth_mode": "SCRP v5 + ZKP Director Clearance",
    }


# ══════════════════════════════════════════════════════════
# Serve Next.js Static Export
# ══════════════════════════════════════════════════════════
from fastapi.staticfiles import StaticFiles

static_dir = "/app/frontend_dist"
if not os.path.exists(static_dir):
    static_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "out")

if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")

