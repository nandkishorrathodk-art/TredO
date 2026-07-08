import React from 'react';
import type { ServiceInfo } from '../services/api';

const SERVICE_ICONS: Record<string, string> = {
  event_bus: '⚡',
  scheduler: '⏰',
  memory: '💾',
  risk: '🛡️',
  ai_gateway: '🤖',
  agent_manager: '🧠',
  ws_manager: '📡',
};

interface ConnectionCardProps {
  services: ServiceInfo[];
  loading: boolean;
}

export function ConnectionCard({ services, loading }: ConnectionCardProps) {
  if (loading) {
    return (
      <div className="card">
        <div className="card-header">
          <span className="card-title">Services</span>
        </div>
        <div className="empty-state">Loading...</div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Services</span>
        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          {services.length} registered
        </span>
      </div>
      <div className="connection-card">
        {services.map((svc) => (
          <div className="service-item" key={svc.name}>
            <span className="icon">{SERVICE_ICONS[svc.name] || '✔'}</span>
            <div>
              <div className="name">{svc.name}</div>
              <div className="type">{svc.type}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
