import React from 'react';

interface StatusBarProps {
  connected: boolean;
  uptime: number;
  wsConnected: boolean;
}

export function StatusBar({ connected, uptime, wsConnected }: StatusBarProps) {
  const formatUptime = (seconds: number): string => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}h ${m}m ${s}s`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  };

  return (
    <div className="status-bar">
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <span>
          <span className={`status-dot ${connected ? 'connected' : 'disconnected'}`} />
          {connected ? 'Backend Connected' : 'Backend Offline'}
        </span>
        <span>
          <span className={`status-dot ${wsConnected ? 'connected' : 'disconnected'}`} />
          {wsConnected ? 'WS Live' : 'WS Disconnected'}
        </span>
      </div>
      <span className="uptime">
        {connected ? `Uptime: ${formatUptime(uptime)}` : '—'}
      </span>
    </div>
  );
}
