"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Volume2, VolumeX, Settings, Download } from "lucide-react";
import { useSessionValidator, SessionExpiredOverlay } from "@/lib/sessionValidator";

const playTone = (freq, duration, type = "sine", volume = 0.04) => {
  if (typeof window === "undefined") return;
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;
    const ctx = new AudioContextClass();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, ctx.currentTime);
    gain.gain.setValueAtTime(volume, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.00001, ctx.currentTime + duration);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + duration);
  } catch (e) {}
};

export default function Dashboard() {
  const { isExpired: sessionExpired, checked: sessionChecked } = useSessionValidator();
  const router = useRouter();
  const [sessionToken, setSessionToken] = useState("");
  const [profile, setProfile] = useState(null);
  const [downloading, setDownloading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [cpuUsage, setCpuUsage] = useState(42.5);
  const [clockInfo, setClockInfo] = useState(null);
  const [apiUrl, setApiUrl] = useState("");

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL || window.location.origin;
    setApiUrl(base.includes("localhost:3000") ? "http://localhost:8000" : base);
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("session_token");
    if (!token) {
      router.push("/");
      return;
    }
    setSessionToken(token);
  }, []);

  useEffect(() => {
    if (!sessionToken || !apiUrl) return;

    const fetchStats = async () => {
      try {
        const res = await fetch(`${apiUrl}/api/v1/dashboard`, {
          headers: { Authorization: `Bearer ${sessionToken}` },
        });
        if (res.ok) {
          const data = await res.json();
          setProfile(data);
          if (soundEnabled) {
            playTone(880, 0.08, "sine", 0.03);
            setTimeout(() => playTone(1200, 0.12, "sine", 0.03), 80);
          }
        } else {
          localStorage.removeItem("session_token");
          router.push("/");
        }
      } catch (err) {
        setErrorMsg("Failed to verify credentials.");
      }
    };

    fetchStats();
  }, [sessionToken, apiUrl]);

  // Fetch Clock Info
  useEffect(() => {
    if (!apiUrl) return;
    const fetchClock = async () => {
      try {
        const res = await fetch(`${apiUrl}/api/v1/meta/hydra-clock`);
        if (res.ok) {
          const data = await res.json();
          setClockInfo(data);
        }
      } catch (err) {}
    };

    fetchClock();
    const interval = setInterval(fetchClock, 5000);
    return () => clearInterval(interval);
  }, [apiUrl]);

  // CPU usage fluctuation
  useEffect(() => {
    const telemetryInterval = setInterval(() => {
      setCpuUsage((prev) => Math.max(10, Math.min(99, prev + (Math.random() - 0.5) * 8)));
    }, 2000);
    return () => clearInterval(telemetryInterval);
  }, []);

  // Download PCAP Artifact
  const handleDownloadPcap = async () => {
    setDownloading(true);
    setErrorMsg("");
    if (soundEnabled) playTone(500, 0.1, "sine", 0.05);
    try {
      const res = await fetch(`${apiUrl}/api/v1/artifacts/hydra-capture`, {
        headers: { Authorization: `Bearer ${sessionToken}` },
      });
      if (res.ok) {
        const pcapToken = res.headers.get("X-PCAP-Token");
        if (pcapToken) {
          localStorage.setItem("pcap_token", pcapToken);
        }

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "HYDRA_CAPTURE.pcapng";
        document.body.appendChild(a);
        a.click();
        a.remove();
        if (soundEnabled) playTone(880, 0.2, "sine", 0.05);
      } else {
        const errData = await res.json();
        setErrorMsg(errData.error || "Failed to download PCAP.");
        if (soundEnabled) playTone(150, 0.35, "sawtooth", 0.08);
      }
    } catch (err) {
      setErrorMsg("Network error.");
      if (soundEnabled) playTone(150, 0.35, "sawtooth", 0.08);
    } finally {
      setDownloading(false);
    }
  };

  const handleLogout = () => {
    if (soundEnabled) playTone(300, 0.15, "triangle", 0.05);
    localStorage.removeItem("session_token");
    localStorage.removeItem("pcap_token");
    router.push("/");
  };

  if (sessionExpired && sessionChecked) {
    return <SessionExpiredOverlay />;
  }

  if (!profile) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#02050c] via-[#050a15] to-[#02050c] flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-cyan-400/70 text-sm uppercase tracking-widest font-mono">Loading session...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#02050c] via-[#050a15] to-[#02050c] text-white overflow-hidden">
      {/* Background effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
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

      {/* Content */}
      <div className="relative z-10">
        {/* Header */}
        <header className="border-b border-cyan-500/10 backdrop-blur-xl bg-black/20">
          <div className="max-w-7xl mx-auto px-6 py-6 flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-black text-white tracking-tight" style={{ fontFamily: "'Orbitron', sans-serif" }}>
                Employee Portal
              </h1>
              <p className="text-xs text-gray-500 mt-1 font-mono tracking-widest uppercase">
                {profile?.username} • Clearance: {profile?.clearance}
              </p>
            </div>
            <button
              onClick={handleLogout}
              className="px-6 py-2 bg-red-500/10 border border-red-500/30 text-red-400 hover:text-red-300 hover:border-red-500/50 rounded-lg text-sm uppercase tracking-widest font-mono transition-all"
            >
              Logout
            </button>
          </div>
        </header>

        {/* Main grid */}
        <main className="max-w-7xl mx-auto px-6 py-12">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            {/* Welcome card */}
            <div className="lg:col-span-2 backdrop-blur-xl bg-white/5 border border-cyan-500/20 rounded-xl p-8">
              <h2 className="text-xl font-bold text-cyan-300 mb-3">Welcome, {profile?.username}</h2>
              <p className="text-gray-400 text-sm leading-relaxed mb-6">
                {profile?.message}
              </p>
              <div className="grid grid-cols-2 gap-4 text-sm font-mono">
                <div>
                  <p className="text-gray-500 uppercase text-xs tracking-widest mb-1">Status</p>
                  <p className="text-cyan-300">{profile?.portal_status}</p>
                </div>
                <div>
                  <p className="text-gray-500 uppercase text-xs tracking-widest mb-1">Notice</p>
                  <p className="text-amber-300 text-xs">{profile?.notice}</p>
                </div>
              </div>
            </div>

            {/* System status card */}
            <div className="backdrop-blur-xl bg-white/5 border border-cyan-500/20 rounded-xl p-6">
              <h3 className="text-sm font-bold text-cyan-300 uppercase tracking-widest mb-4">System Status</h3>
              <div className="space-y-3 text-sm">
                <div>
                  <p className="text-gray-500 text-xs mb-1">CPU Load</p>
                  <div className="h-2 bg-black/50 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-cyan-600 to-cyan-400" style={{ width: `${cpuUsage}%` }}></div>
                  </div>
                  <p className="text-cyan-400 text-xs mt-1">{cpuUsage.toFixed(1)}%</p>
                </div>
                <div>
                  <p className="text-gray-500 text-xs mb-1">HYDRA Rekey</p>
                  <p className="text-amber-300">{clockInfo?.next_tick_in}s</p>
                </div>
              </div>
            </div>
          </div>

          {/* Calibration Gate */}
          <div className="backdrop-blur-xl bg-white/5 border border-cyan-500/20 rounded-xl p-8 mb-8">
            <h2 className="text-lg font-bold text-cyan-300 mb-4">System Calibration Required</h2>
            <p className="text-gray-400 text-sm mb-6">
              Before proceeding to artifact analysis, you must complete a resonance calibration check. This ensures system integrity.
            </p>

            <button
              onClick={() => {
                if (soundEnabled) playTone(500, 0.1, "sine", 0.05);
                router.push("/calibrate");
              }}
              className="w-full md:w-auto px-8 py-3 bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-white font-bold text-sm uppercase tracking-widest rounded-lg transition-all duration-300 shadow-lg hover:shadow-amber-500/20 flex items-center justify-center gap-2"
            >
              <Settings size={16} />
              <span>Proceed to Calibration</span>
            </button>
          </div>

          {/* PCAP Section */}
          <div className="backdrop-blur-xl bg-white/5 border border-cyan-500/20 rounded-xl p-8 mb-8">
            <h2 className="text-lg font-bold text-cyan-300 mb-4">Challenge Artifacts</h2>
            <p className="text-gray-400 text-sm mb-6">
              Download the HYDRA network capture file for cryptographic analysis. Contains encrypted session data from the recent incident.
            </p>

            <button
              onClick={handleDownloadPcap}
              disabled={downloading}
              className="w-full md:w-auto px-8 py-3 bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold text-sm uppercase tracking-widest rounded-lg transition-all duration-300 shadow-lg hover:shadow-cyan-500/20 flex items-center justify-center gap-2"
            >
              {downloading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>Downloading...</span>
                </>
              ) : (
                <>
                  <Download size={16} />
                  <span>Download HYDRA_CAPTURE.pcapng</span>
                </>
              )}
            </button>

            {errorMsg && (
              <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                <p className="text-red-300 text-sm">{errorMsg}</p>
              </div>
            )}
          </div>

          {/* Flow guide */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            {[
              { num: "1", label: "Dashboard", desc: "You are here" },
              { num: "2", label: "Calibrate", desc: "Resonance tuning" },
              { num: "3", label: "PCAP Analysis", desc: "Crypto recovery" },
              { num: "4", label: "Director ZKP", desc: "Cryptographic proof" },
              { num: "5", label: "Flag Decrypt", desc: "Final decryption" }
            ].map((step, i) => (
              <div key={i} className="backdrop-blur-xl bg-white/5 border border-cyan-500/10 rounded-lg p-4 text-center">
                <div className="w-8 h-8 bg-gradient-to-br from-cyan-600 to-cyan-500 rounded-full flex items-center justify-center font-bold text-sm mx-auto mb-2">
                  {step.num}
                </div>
                <p className="text-sm font-mono font-bold text-cyan-300">{step.label}</p>
                <p className="text-xs text-gray-500 mt-1">{step.desc}</p>
              </div>
            ))}
          </div>
        </main>
      </div>

      {/* Footer */}
      <footer className="border-t border-cyan-500/10 backdrop-blur-xl bg-black/20 mt-12">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between text-xs text-gray-500 font-mono">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSoundEnabled(!soundEnabled)}
              className="hover:text-cyan-400 transition flex items-center gap-1"
            >
              {soundEnabled ? (
                <>
                  <Volume2 size={14} />
                  <span>Audio</span>
                </>
              ) : (
                <>
                  <VolumeX size={14} />
                  <span>Muted</span>
                </>
              )}
            </button>
          </div>
          <div>Stark Industries — Employee Portal v5.0.0</div>
        </div>
      </footer>

      {/* CRT effect */}
      <div className="fixed inset-0 pointer-events-none opacity-5 z-20"
        style={{
          backgroundImage: `linear-gradient(0deg, transparent 24%, rgba(255, 0, 0, 0.05) 25%, rgba(255, 0, 0, 0.05) 26%, transparent 27%, transparent 74%, rgba(255, 0, 0, 0.05) 75%, rgba(255, 0, 0, 0.05) 76%, transparent 77%, transparent)`,
          backgroundSize: "100% 4px"
        }}>
      </div>
    </div>
  );
}
