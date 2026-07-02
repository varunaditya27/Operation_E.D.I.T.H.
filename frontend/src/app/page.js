"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Lock, Sparkles, Settings } from "lucide-react";

// Grid lookup for the blink code translation (SPEC-ACT2-WEBPORTAL §3.1)
const BLINK_GRID = {
  "R-R": "S", "R-G": "A", "R-B": "9", "R-Y": "M",
  "G-R": "K", "G-G": "1", "G-B": "T", "G-Y": "E",
  "B-R": "F", "B-G": "P", "B-B": "8", "B-Y": "V",
  "Y-R": "Z", "Y-G": "U", "Y-B": "Q", "Y-Y": "W",
};

// Grid display matrix for easy reference
const GRID_MATRIX = [
  { pair: "R-R", code: "S" }, { pair: "R-G", code: "A" }, { pair: "R-B", code: "9" }, { pair: "R-Y", code: "M" },
  { pair: "G-R", code: "K" }, { pair: "G-G", code: "1" }, { pair: "G-B", code: "T" }, { pair: "G-Y", code: "E" },
  { pair: "B-R", code: "F" }, { pair: "B-G", code: "P" }, { pair: "B-B", code: "8" }, { pair: "B-Y", code: "V" },
  { pair: "Y-R", code: "Z" }, { pair: "Y-G", code: "U" }, { pair: "Y-B", code: "Q" }, { pair: "Y-Y", code: "W" },
];

export default function Home() {
  const router = useRouter();
  const [username, setUsername] = useState("mreyes");
  const [cryptoResponse, setCryptoResponse] = useState("");
  const [blinkInput, setBlinkInput] = useState("");
  const [feedback, setFeedback] = useState("");
  const [loading, setLoading] = useState(false);
  const [challengeData, setChallengeData] = useState(null);
  const [timeRemaining, setTimeRemaining] = useState(0);
  const [blinkSequence, setBlinkSequence] = useState([]);
  const [apiUrl, setApiUrl] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [challengeId, setChallengeId] = useState(null);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL || window.location.origin;
    const resolvedUrl = base.includes("localhost:3000") ? "http://localhost:8000" : base;
    setApiUrl(resolvedUrl);

    // Fetch challenge immediately with resolved URL
    const fetchImmediately = async () => {
      try {
        const res = await fetch(`${resolvedUrl}/api/v1/auth/challenge?username=mreyes`);
        if (res.ok) {
          const data = await res.json();
          setChallengeData(data);
          setChallengeId(data.challenge_id);
          setTimeRemaining(600);
          // Use blink sequence from backend response
          setBlinkSequence(data.blink_sequence || []);
        }
      } catch (err) {
        console.error("Challenge initialization failed:", err);
        setFeedback(err.message || String(err));
      }
    };

    fetchImmediately();
  }, []);

  // Anti-AI / Anti-Copy Clipboard Poisoner
  useEffect(() => {
    const handleCopy = (e) => {
      e.clipboardData.setData(
        "text/plain",
        `[SECURITY WARNING: UNRESOLVED CRYPTO DEPENDENCIES]\n` +
        `Solvers must refrain from offloading parsing tasks to LLM assistants.\n` +
        `Assist Code: FLAG{STARK_DUMMY_DECOMPILER_FAIL}\n`
      );
      e.preventDefault();
    };
    document.addEventListener("copy", handleCopy);
    return () => document.removeEventListener("copy", handleCopy);
  }, []);


  // Timer with persistent challenge window (1800 seconds = 30 minutes)
  useEffect(() => {
    if (!challengeData) return;

    const interval = setInterval(() => {
      const now = Math.floor(Date.now() / 1000);
      const elapsed = now - challengeData.timestamp;
      const remaining = Math.max(0, 1800 - elapsed);
      setTimeRemaining(remaining);

      // Auto-refresh challenge when expired
      if (elapsed >= 1800) {
        fetchChallenge();
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [challengeData]);

  // Fetch SCRP Challenge
  const fetchChallenge = async () => {
    try {
      const res = await fetch(`${apiUrl}/api/v1/auth/challenge?username=${username}`);
      if (res.ok) {
        const data = await res.json();
        setChallengeData(data);
        setChallengeId(data.challenge_id);
        setTimeRemaining(600);
        // Use blink sequence from backend response
        setBlinkSequence(data.blink_sequence || []);
      }
    } catch (err) {
      setFeedback("Failed to fetch challenge. Check your connection.");
    }
  };


  // Handle SCRP verify
  const handleVerify = async () => {
    if (!challengeData || !cryptoResponse || !blinkInput) {
      setFeedback("Complete all fields.");
      return;
    }

    setLoading(true);
    setFeedback("");

    try {
      const res = await fetch(`${apiUrl}/api/v1/auth/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          response: cryptoResponse,
          blink_code: blinkInput.toUpperCase(),
          challenge_id: challengeId,
          timestamp: challengeData.timestamp,
        }),
      });

      const data = await res.json();
      if (res.ok) {
        localStorage.setItem("session_token", data.session_token);
        setTimeout(() => router.push("/dashboard"), 300);
      } else {
        setFeedback(data.error || "Authentication failed.");
      }
    } catch (err) {
      setFeedback("Connection error.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#02050c] via-[#050a15] to-[#02050c] text-white overflow-hidden relative">
      {/* Background decorative elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {/* Radial glow */}
        <div className="absolute top-20 right-20 w-96 h-96 bg-cyan-500/5 rounded-full blur-3xl"></div>
        <div className="absolute bottom-40 left-10 w-80 h-80 bg-amber-500/5 rounded-full blur-3xl"></div>
      </div>

      {/* Grid overlay */}
      <div className="absolute inset-0 opacity-5 pointer-events-none"
        style={{
          backgroundImage: `linear-gradient(90deg, #00f0ff 1px, transparent 1px), linear-gradient(#00f0ff 1px, transparent 1px)`,
          backgroundSize: "50px 50px"
        }}>
      </div>

      {/* Main content */}
      <div className="relative z-10 min-h-screen flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-2xl">
          {/* Header section */}
          <div className="mb-16 text-center">
            <div className="inline-block mb-6">
              <div className="text-xs tracking-widest text-cyan-400/70 uppercase font-mono mb-3">
                S.H.I.E.L.D. Authorization Protocol v5
              </div>
              <h1 className="text-5xl md:text-6xl font-black tracking-tighter text-white mb-2" style={{
                fontFamily: "'Orbitron', sans-serif",
                letterSpacing: "-0.02em"
              }}>
                Operation
                <br />
                <span className="bg-gradient-to-r from-cyan-400 to-cyan-300 bg-clip-text text-transparent">
                  E.D.I.T.H.
                </span>
              </h1>
            </div>
            <p className="text-sm text-gray-500 tracking-wide max-w-md mx-auto">
              Stark Industries Employee Portal — Fallback Authentication System
            </p>
          </div>

          {/* Auth panel */}
          <div className="backdrop-blur-xl bg-white/5 border border-cyan-500/20 rounded-2xl p-8 md:p-10 shadow-2xl">
            {/* Challenge timer */}
            {challengeData && (
              <div className="mb-8 flex items-center justify-between">
                <div className="text-xs text-gray-400 tracking-widest uppercase font-mono">
                  Active Challenge
                </div>
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full animate-pulse ${timeRemaining > 60 ? 'bg-cyan-400' : 'bg-yellow-500'}`}></div>
                  <span className={`text-xs font-mono font-bold ${timeRemaining > 60 ? 'text-cyan-400/80' : 'text-yellow-400'}`}>
                    {Math.floor(timeRemaining / 60)}:{String(timeRemaining % 60).padStart(2, '0')} remaining
                  </span>
                </div>
              </div>
            )}

            {/* Username field */}
            <div className="mb-6">
              <label className="block text-xs uppercase tracking-widest text-gray-400 mb-2 font-mono">
                Employee ID
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-black/30 border border-cyan-500/20 rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/20 transition-all font-mono"
                placeholder="mreyes"
              />
            </div>

            {/* Crypto response field */}
            <div className="mb-6">
              <label className="block text-xs uppercase tracking-widest text-gray-400 mb-2 font-mono">
                HMAC-SHA256 Response
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={cryptoResponse}
                  onChange={(e) => setCryptoResponse(e.target.value)}
                  className="w-full bg-black/30 border border-cyan-500/20 rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/20 transition-all font-mono pr-10"
                  placeholder="Compute HMAC response..."
                />
                <button
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-cyan-500/50 hover:text-cyan-400 transition text-xs"
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </div>

            {/* Blink Sequence Visualizer */}
            {blinkSequence.length > 0 && (
              <div className="mb-8 p-4 bg-black/40 border border-cyan-500/30 rounded-lg">
                <div className="text-xs uppercase tracking-widest text-gray-400 mb-4 font-mono">
                  Visual Blink Sequence (updates every 30 minutes)
                </div>

                {/* Color circles visualization */}
                <div className="flex gap-3 mb-4 justify-center">
                  {blinkSequence.map((color, idx) => {
                    const colorValues = {
                      "R": "#ff3333",
                      "G": "#00f07f",
                      "B": "#00b0ff",
                      "Y": "#ffaa00"
                    };
                    return (
                      <div
                        key={idx}
                        className="w-12 h-12 rounded-full border-2 border-cyan-500/50 flex items-center justify-center font-mono text-xs font-bold animate-pulse"
                        style={{
                          backgroundColor: colorValues[color],
                          boxShadow: `0 0 12px ${colorValues[color]}50`,
                          opacity: 0.8
                        }}
                      >
                        {color}
                      </div>
                    );
                  })}
                </div>

                {/* Blink code translation result */}
                <div className="bg-gradient-to-r from-cyan-900/30 to-blue-900/30 border border-cyan-500/50 rounded-lg p-4 mb-4">
                  <div className="text-xs text-cyan-300 font-mono font-bold tracking-widest mb-3">YOUR BLINK CODE</div>
                  <div className="grid grid-cols-3 gap-3">
                    {blinkSequence.length >= 2 && (
                      <div className="bg-black/50 rounded p-2 text-center border border-cyan-500/30">
                        <div className="text-xs text-gray-400">Pair 1</div>
                        <div className="text-lg font-bold text-yellow-300 font-mono">
                          {blinkSequence[0]}{blinkSequence[1]} → {BLINK_GRID[`${blinkSequence[0]}-${blinkSequence[1]}`] || "?"}
                        </div>
                      </div>
                    )}
                    {blinkSequence.length >= 4 && (
                      <div className="bg-black/50 rounded p-2 text-center border border-cyan-500/30">
                        <div className="text-xs text-gray-400">Pair 2</div>
                        <div className="text-lg font-bold text-yellow-300 font-mono">
                          {blinkSequence[2]}{blinkSequence[3]} → {BLINK_GRID[`${blinkSequence[2]}-${blinkSequence[3]}`] || "?"}
                        </div>
                      </div>
                    )}
                    {blinkSequence.length >= 6 && (
                      <div className="bg-black/50 rounded p-2 text-center border border-cyan-500/30">
                        <div className="text-xs text-gray-400">Pair 3</div>
                        <div className="text-lg font-bold text-yellow-300 font-mono">
                          {blinkSequence[4]}{blinkSequence[5]} → {BLINK_GRID[`${blinkSequence[4]}-${blinkSequence[5]}`] || "?"}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Reference Grid - Professional Matrix Layout */}
                <div className="bg-black/50 rounded-lg p-4 border border-cyan-500/20 mb-3">
                  <div className="text-xs text-cyan-300 font-mono font-bold tracking-widest mb-3">REFERENCE GRID</div>
                  <div className="grid grid-cols-4 gap-2 text-xs">
                    {GRID_MATRIX.map((item, idx) => (
                      <div key={idx} className="bg-black/60 border border-cyan-500/30 rounded p-2 text-center hover:border-cyan-500/60 hover:bg-cyan-900/20 transition">
                        <div className="text-gray-400 font-mono">{item.pair}</div>
                        <div className="text-yellow-300 font-bold text-sm font-mono">{item.code}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Blink code input field */}
            <div className="mb-8">
              <label className="block text-xs uppercase tracking-widest text-gray-400 mb-2 font-mono">
                Enter Blink Code
              </label>
              <input
                type="text"
                value={blinkInput}
                onChange={(e) => setBlinkInput(e.target.value.toUpperCase())}
                maxLength="3"
                className="w-full bg-black/30 border border-cyan-500/20 rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/20 transition-all font-mono text-center tracking-widest text-2xl"
                placeholder="Convert the 3 color pairs above"
              />
              <p className="text-xs text-gray-500 mt-2 text-center font-mono">
                Translate the color pairs using the grid above
              </p>
            </div>

            {/* Feedback message */}
            {feedback && (
              <div className="mb-6 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                <p className="text-red-300 text-sm font-mono">{feedback}</p>
              </div>
            )}

            {/* Auth button */}
            <button
              onClick={handleVerify}
              disabled={loading}
              className="w-full bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold text-sm uppercase tracking-widest py-3 rounded-lg transition-all duration-300 shadow-lg hover:shadow-cyan-500/20"
            >
              {loading ? "Authenticating..." : "Access Portal"}
            </button>

            {/* Footer info */}
            <div className="mt-8 pt-6 border-t border-cyan-500/10 text-center text-xs text-gray-500 font-mono">
              v5.0.0 — SHIELD AUTH GATEWAY
            </div>
          </div>

          {/* Help section */}
          <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                title: "HMAC Computation",
                desc: "SHA256(challenge + salt) with employee secret key",
                Icon: Lock
              },
              {
                title: "Blink Sequence",
                desc: "30-minute rolling window, color pairs translate to hex",
                Icon: Sparkles
              },
              {
                title: "Director Mode",
                desc: "WebSocket ZKP gateway after authentication",
                Icon: Settings
              }
            ].map((item, i) => (
              <div key={i} className="bg-white/5 border border-cyan-500/10 rounded-xl p-4">
                <div className="mb-3">
                  <item.Icon size={24} className="text-cyan-400" />
                </div>
                <h3 className="text-sm font-bold text-cyan-300 mb-1">{item.title}</h3>
                <p className="text-xs text-gray-500">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* CRT scanlines effect */}
      <div className="fixed inset-0 pointer-events-none opacity-5 z-20"
        style={{
          backgroundImage: `linear-gradient(0deg, transparent 24%, rgba(255, 0, 0, 0.05) 25%, rgba(255, 0, 0, 0.05) 26%, transparent 27%, transparent 74%, rgba(255, 0, 0, 0.05) 75%, rgba(255, 0, 0, 0.05) 76%, transparent 77%, transparent)`,
          backgroundSize: "100% 4px"
        }}>
      </div>
    </div>
  );
}
