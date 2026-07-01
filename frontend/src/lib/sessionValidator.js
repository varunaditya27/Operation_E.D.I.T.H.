/**
 * Session validation utility for protecting authenticated pages.
 * Detects expired/invalid sessions and displays a themed warning.
 */

import { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';

export function SessionExpiredOverlay() {
  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        <div className="backdrop-blur-xl bg-red-950/30 border border-red-500/50 rounded-2xl p-8">
          <div className="flex items-center gap-3 mb-4">
            <AlertTriangle size={28} className="text-red-400 flex-shrink-0" />
            <h2 className="text-xl font-black text-red-300" style={{ fontFamily: "'Orbitron', sans-serif" }}>
              Session Expired
            </h2>
          </div>

          <p className="text-sm text-red-200/80 mb-6 leading-relaxed font-mono">
            Your authentication session has expired. For security purposes, you must restart the challenge from the beginning.
          </p>

          <div className="space-y-2 mb-6 p-4 bg-black/40 rounded-lg border border-red-500/20">
            <p className="text-xs text-red-300/70 font-mono uppercase tracking-widest">Required Actions:</p>
            <ul className="text-xs text-red-200/70 font-mono space-y-1 ml-3">
              <li>• Request a new challenge</li>
              <li>• Recompute HMAC-SHA256 response</li>
              <li>• Transcribe blink sequence</li>
              <li>• Complete full authentication flow</li>
            </ul>
          </div>

          <button
            onClick={() => {
              localStorage.removeItem('session_token');
              window.location.href = '/';
            }}
            className="w-full px-6 py-3 bg-gradient-to-r from-red-600 to-red-500 hover:from-red-500 hover:to-red-400 text-white font-bold text-sm uppercase tracking-widest rounded-lg transition-all duration-300 shadow-lg hover:shadow-red-500/20"
          >
            Return to Login
          </button>

          <p className="text-xs text-red-300/50 mt-4 text-center font-mono">
            Session TTL: 30 minutes from authentication
          </p>
        </div>
      </div>
    </div>
  );
}

export function useSessionValidator() {
  const [isExpired, setIsExpired] = useState(false);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const validateSession = async () => {
      const token = localStorage.getItem('session_token');

      if (!token) {
        setIsExpired(true);
        setChecked(true);
        return;
      }

      try {
        const resp = await fetch('/api/v1/dashboard', {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!resp.ok) {
          // 401 or any error means session is invalid
          setIsExpired(true);
        }
      } catch (err) {
        // Network error - assume session might be expired
        setIsExpired(true);
      }

      setChecked(true);
    };

    validateSession();

    // Re-validate every 30 seconds
    const interval = setInterval(validateSession, 30000);
    return () => clearInterval(interval);
  }, []);

  return { isExpired, checked };
}
