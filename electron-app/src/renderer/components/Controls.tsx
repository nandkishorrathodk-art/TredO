import React from 'react';

interface ControlsProps {
  connected: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
  onHealthCheck: () => void;
  onPublishEvent: () => void;
}

export function Controls({
  connected,
  onConnect,
  onDisconnect,
  onHealthCheck,
  onPublishEvent,
}: ControlsProps) {
  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Controls</span>
      </div>
      <div className="controls">
        {!connected ? (
          <button className="btn btn-primary" onClick={onConnect}>
            ▶ Connect
          </button>
        ) : (
          <button className="btn btn-danger" onClick={onDisconnect}>
            ■ Disconnect
          </button>
        )}
        <button className="btn" onClick={onHealthCheck} disabled={!connected}>
          ♥ Health Check
        </button>
        <button className="btn" onClick={onPublishEvent} disabled={!connected}>
          ⚡ Publish Event
        </button>
      </div>
    </div>
  );
}
