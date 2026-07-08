import React from 'react';
import type { WsEvent } from '../services/websocket';

function getEventCategory(type: string): string {
  if (type.includes('Risk')) return 'risk';
  if (type.includes('Trade')) return 'trade';
  if (type.includes('Agent')) return 'agent';
  if (type.includes('Error') || type.includes('Kill')) return 'error';
  return 'system';
}

function formatTime(timestamp: string): string {
  try {
    const d = new Date(timestamp);
    return d.toLocaleTimeString('en-US', { hour12: false });
  } catch {
    return '--:--:--';
  }
}

function getEventMessage(event: WsEvent): string {
  if (event.message) return String(event.message);
  if (event.content) return String(event.content);
  if (event.decision) return String(event.decision);
  if (event.status) return `Status: ${event.status}`;
  return event.type;
}

interface EventConsoleProps {
  events: WsEvent[];
}

export function EventConsole({ events }: EventConsoleProps) {
  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Recent Events</span>
        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          {events.length} events
        </span>
      </div>
      <div className="event-console">
        {events.length === 0 ? (
          <div className="empty-state">No events yet. Waiting for backend...</div>
        ) : (
          events.map((event, i) => (
            <div className="event-row" key={`${event.timestamp}-${i}`}>
              <span className="event-time">{formatTime(event.timestamp)}</span>
              <span className={`event-type ${getEventCategory(event.type)}`}>
                {event.type}
              </span>
              <span className="event-message">{getEventMessage(event)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
