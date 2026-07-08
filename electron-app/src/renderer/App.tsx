/**
 * TREDO — Electron Shell
 * 3 pages: Dashboard, Events, Settings.
 * No charts. No AI visualization. Just backend verification.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import './index.css';

import { StatusBar } from './components/StatusBar';
import { ConnectionCard } from './components/ConnectionCard';
import { EventConsole } from './components/EventConsole';
import { Controls } from './components/Controls';

import { getHealth, getServices, publishEvent } from './services/api';
import { wsService } from './services/websocket';
import type { ServiceInfo } from './services/api';
import type { WsEvent } from './services/websocket';

type Page = 'dashboard' | 'events' | 'settings';
const MAX_EVENTS = 100;

export default function App() {
  // ── State ───────────────────────────────────────────────
  const [page, setPage] = useState<Page>('dashboard');
  const [connected, setConnected] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [uptime, setUptime] = useState(0);
  const [services, setServices] = useState<ServiceInfo[]>([]);
  const [events, setEvents] = useState<WsEvent[]>([]);
  const [loading, setLoading] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Connect / Disconnect ────────────────────────────────
  const doConnect = useCallback(async () => {
    setLoading(true);
    const health = await getHealth();
    if (health.ok && health.data) {
      setConnected(true);
      setUptime((health.data as any).uptime_s || 0);

      const svcResult = await getServices();
      if (svcResult.ok && svcResult.data) {
        setServices((svcResult.data as any).services || []);
      }

      // Start WebSocket
      wsService.connect();

      // Start polling health every 5s
      pollRef.current = setInterval(async () => {
        const h = await getHealth();
        if (h.ok && h.data) {
          setUptime((h.data as any).uptime_s || 0);
        } else {
          setConnected(false);
          wsService.disconnect();
          if (pollRef.current) clearInterval(pollRef.current);
        }
      }, 5000);
    }
    setLoading(false);
  }, []);

  const doDisconnect = useCallback(() => {
    setConnected(false);
    wsService.disconnect();
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    setServices([]);
    setUptime(0);
  }, []);

  // ── WebSocket Events ────────────────────────────────────
  useEffect(() => {
    const unsub = wsService.onEvent((event: WsEvent) => {
      if (event.type === 'ConnectionStatus') {
        setWsConnected(event.status === 'connected');
        return;
      }
      setEvents((prev) => [event, ...prev].slice(0, MAX_EVENTS));
    });
    return () => { unsub(); };
  }, []);

  // ── Cleanup on unmount ──────────────────────────────────
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      wsService.disconnect();
    };
  }, []);

  // ── Actions ─────────────────────────────────────────────
  const handleHealthCheck = async () => {
    const result = await getHealth();
    if (result.ok && result.data) {
      setUptime((result.data as any).uptime_s || 0);
      setEvents((prev) => [{
        type: 'HealthCheck',
        source: 'ui',
        timestamp: new Date().toISOString(),
        message: `OK — ${(result.data as any).services} services, uptime ${(result.data as any).uptime_s}s`,
      }, ...prev].slice(0, MAX_EVENTS));
    }
  };

  const handlePublishEvent = async () => {
    await publishEvent({
      event_type: 'system',
      message: 'Test event from Electron UI',
      severity: 'info',
      details: { source: 'electron' },
    });
  };

  // ── Render Pages ────────────────────────────────────────
  const renderPage = () => {
    switch (page) {
      case 'dashboard':
        return (
          <div className="dashboard-grid">
            <Controls
              connected={connected}
              onConnect={doConnect}
              onDisconnect={doDisconnect}
              onHealthCheck={handleHealthCheck}
              onPublishEvent={handlePublishEvent}
            />
            <ConnectionCard services={services} loading={loading} />
            <EventConsole events={events} />
          </div>
        );

      case 'events':
        return (
          <div className="dashboard-grid">
            <div className="card">
              <div className="card-header">
                <span className="card-title">All Events</span>
                <button
                  className="btn"
                  onClick={() => setEvents([])}
                  style={{ padding: '4px 12px', fontSize: '12px' }}
                >
                  Clear
                </button>
              </div>
              <div className="event-console" style={{ maxHeight: 'calc(100vh - 200px)' }}>
                {events.length === 0 ? (
                  <div className="empty-state">No events captured yet.</div>
                ) : (
                  events.map((event, i) => (
                    <div className="event-row" key={`${event.timestamp}-${i}`}>
                      <span className="event-time">
                        {new Date(event.timestamp).toLocaleTimeString('en-US', { hour12: false })}
                      </span>
                      <span className={`event-type ${getEventCategory(event.type)}`}>
                        {event.type}
                      </span>
                      <span className="event-message">
                        {event.message?.toString() || event.type}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        );

      case 'settings':
        return (
          <div className="dashboard-grid">
            <div className="card">
              <div className="card-header">
                <span className="card-title">Settings</span>
              </div>
              <div className="settings-group">
                <div className="settings-label">Backend URL</div>
                <div className="settings-value">http://localhost:8000</div>
              </div>
              <div className="settings-group">
                <div className="settings-label">WebSocket URL</div>
                <div className="settings-value">ws://localhost:8000/ws</div>
              </div>
              <div className="settings-group">
                <div className="settings-label">Version</div>
                <div className="settings-value">TREDO v0.1.0</div>
              </div>
              <div className="settings-group">
                <div className="settings-label">Status</div>
                <div className="settings-value">
                  Backend: {connected ? '🟢 Connected' : '🔴 Offline'} | 
                  WebSocket: {wsConnected ? '🟢 Live' : '🔴 Disconnected'}
                </div>
              </div>
            </div>
          </div>
        );
    }
  };

  return (
    <div className="app-layout">
      <header className="app-header">
        <h1>TREDO</h1>
        <nav className="app-nav">
          <button className={page === 'dashboard' ? 'active' : ''} onClick={() => setPage('dashboard')}>
            Dashboard
          </button>
          <button className={page === 'events' ? 'active' : ''} onClick={() => setPage('events')}>
            Events
          </button>
          <button className={page === 'settings' ? 'active' : ''} onClick={() => setPage('settings')}>
            Settings
          </button>
        </nav>
      </header>

      <main className="app-content">{renderPage()}</main>

      <StatusBar connected={connected} uptime={uptime} wsConnected={wsConnected} />
    </div>
  );
}

function getEventCategory(type: string): string {
  if (type.includes('Risk')) return 'risk';
  if (type.includes('Trade')) return 'trade';
  if (type.includes('Agent')) return 'agent';
  if (type.includes('Error') || type.includes('Kill')) return 'error';
  return 'system';
}
