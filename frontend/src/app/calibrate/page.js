'use client';

import { useState, useEffect, useRef } from 'react';

export default function CalibratePage() {
  const [session, setSession] = useState(null);
  const [target, setTarget] = useState(null);
  const [freq, setFreq] = useState(0.5);
  const [phase, setPhase] = useState(0);
  const [amp, setAmp] = useState(0.5);
  const [skew, setSkew] = useState(0);
  const [message, setMessage] = useState('Loading calibration target...');
  const [loading, setLoading] = useState(true);
  const [attempting, setAttempting] = useState(false);
  const [passed, setPassed] = useState(false);
  const canvasRef = useRef(null);

  // Check authentication
  useEffect(() => {
    const auth = localStorage.getItem('session_token');
    if (!auth) {
      setMessage('Authentication required. Redirecting...');
      setTimeout(() => window.location.href = '/login', 2000);
      return;
    }
    setSession(auth);
  }, []);

  // Load calibration target
  useEffect(() => {
    if (!session) return;

    const fetchTarget = async () => {
      try {
        const resp = await fetch('/api/v1/calibrate/target', {
          headers: { Authorization: `Bearer ${session}` },
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        setTarget(data);
        setMessage('');
        setLoading(false);
      } catch (err) {
        setMessage(`Failed to load target: ${err.message}`);
      }
    };

    fetchTarget();
  }, [session]);

  // Draw canvas
  useEffect(() => {
    if (!target || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    const padding = 40;

    // Clear
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(0, 0, w, h);

    // Grid
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 10; i++) {
      const x = padding + (i * (w - 2 * padding)) / 10;
      const y = padding + (i * (h - 2 * padding)) / 10;
      ctx.beginPath();
      ctx.moveTo(x, padding);
      ctx.lineTo(x, h - padding);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(padding, y);
      ctx.lineTo(w - padding, y);
      ctx.stroke();
    }

    // Axes
    ctx.strokeStyle = '#666';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding, h - padding);
    ctx.lineTo(w - padding, h - padding);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, h - padding);
    ctx.stroke();

    // Draw target (blue)
    ctx.strokeStyle = '#0099ff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    let first = true;
    for (const pt of target.target) {
      const xNorm = pt.x / (2 * Math.PI);
      const yNorm = (pt.y - (-1.5)) / 3.0;
      const x = padding + xNorm * (w - 2 * padding);
      const y = h - padding - yNorm * (h - 2 * padding);
      if (first) {
        ctx.moveTo(x, y);
        first = false;
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();

    // Draw user wave (green)
    ctx.strokeStyle = '#00ff00';
    ctx.lineWidth = 2;
    ctx.beginPath();
    first = true;
    for (let i = 0; i < 300; i++) {
      const x_val = (i / 300) * 2 * Math.PI;
      const y_val = amp * Math.sin(freq * x_val + phase) + skew;
      const xNorm = x_val / (2 * Math.PI);
      const yNorm = (y_val - (-1.5)) / 3.0;
      const x = padding + xNorm * (w - 2 * padding);
      const y = h - padding - yNorm * (h - 2 * padding);
      if (first) {
        ctx.moveTo(x, y);
        first = false;
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();

    // Labels
    ctx.fillStyle = '#ccc';
    ctx.font = '12px monospace';
    ctx.fillText('Time →', w - 60, h - 10);
    ctx.fillText('Amplitude ↑', 5, 20);
  }, [target, freq, phase, amp, skew]);

  const handleSubmit = async () => {
    if (attempting) return;
    setAttempting(true);

    try {
      const resp = await fetch('/api/v1/calibrate/submit', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${session}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ freq, phase, amp, skew }),
      });

      const data = await resp.json();
      if (data.pass) {
        setPassed(true);
        setMessage('Calibration successful! Proceeding to Director authentication...');
        setTimeout(() => window.location.href = '/director', 3000);
      } else {
        setMessage(data.message || 'Calibration failed. Adjust parameters and retry.');
      }
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setAttempting(false);
    }
  };

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.card}>
          <h1>Resonance Calibration</h1>
          <p style={{ textAlign: 'center', color: '#aaa' }}>{message}</p>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1>SHIELD — Resonance Calibration Gate</h1>
        <p style={{ color: '#888', marginBottom: '20px' }}>
          Adjust the Reference Wave parameters until your Calibration Wave matches the target (blue line).
        </p>

        <div style={{ marginBottom: '30px' }}>
          <canvas
            ref={canvasRef}
            width={800}
            height={400}
            style={{ border: '1px solid #444', width: '100%', maxWidth: '800px' }}
          />
          <p style={{ fontSize: '11px', color: '#666', marginTop: '8px' }}>
            Blue = Reference Wave (target) | Green = Your Calibration Wave
          </p>
        </div>

        <div style={styles.controls}>
          <div style={styles.slider}>
            <label>Frequency: {freq.toFixed(3)}</label>
            <input
              type="range"
              min="0.1"
              max="2.0"
              step="0.01"
              value={freq}
              onChange={(e) => setFreq(parseFloat(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>

          <div style={styles.slider}>
            <label>Phase: {phase.toFixed(3)}</label>
            <input
              type="range"
              min="0"
              max={2 * Math.PI}
              step="0.01"
              value={phase}
              onChange={(e) => setPhase(parseFloat(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>

          <div style={styles.slider}>
            <label>Amplitude: {amp.toFixed(3)}</label>
            <input
              type="range"
              min="0.1"
              max="1.5"
              step="0.01"
              value={amp}
              onChange={(e) => setAmp(parseFloat(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>

          <div style={styles.slider}>
            <label>Skew: {skew.toFixed(3)}</label>
            <input
              type="range"
              min="-0.5"
              max="0.5"
              step="0.01"
              value={skew}
              onChange={(e) => setSkew(parseFloat(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>
        </div>

        <button
          onClick={handleSubmit}
          disabled={attempting || passed}
          style={{
            ...styles.button,
            opacity: attempting || passed ? 0.5 : 1,
            cursor: attempting || passed ? 'not-allowed' : 'pointer',
          }}
        >
          {attempting ? 'Verifying...' : passed ? 'Calibration Complete' : 'Submit Calibration'}
        </button>

        {message && (
          <p style={{ marginTop: '15px', color: passed ? '#0f0' : '#ff9900', textAlign: 'center' }}>
            {message}
          </p>
        )}
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: '100vh',
    backgroundColor: '#0a0a0a',
    padding: '20px',
  },
  card: {
    backgroundColor: '#1a1a1a',
    border: '1px solid #333',
    borderRadius: '4px',
    padding: '30px',
    maxWidth: '900px',
    width: '100%',
    color: '#ccc',
  },
  controls: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '20px',
    marginBottom: '20px',
  },
  slider: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  button: {
    backgroundColor: '#004f99',
    color: '#fff',
    padding: '12px 24px',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: 'bold',
    width: '100%',
  },
};
