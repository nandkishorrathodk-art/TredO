/**
 * TREDO — API Service
 * Communicates with Python backend via REST.
 * Works both in Electron (via IPC) and browser (direct fetch).
 */

// Type for the IPC bridge exposed by preload
declare global {
  interface Window {
    tredo?: {
      api: {
        health: () => Promise<ApiResult>;
        status: () => Promise<ApiResult>;
        services: () => Promise<ApiResult>;
        event: (body: object) => Promise<ApiResult>;
        shutdown: (reason: string) => Promise<ApiResult>;
        backendUrl: () => Promise<string>;
      };
    };
  }
}

export interface ApiResult {
  ok: boolean;
  data?: any;
  error?: string;
}

export interface HealthData {
  status: string;
  uptime_s: number;
  services: number;
  agents: number;
}

export interface ServiceInfo {
  name: string;
  type: string;
  status: string;
}

export interface StatusData {
  status: string;
  services: ServiceInfo[];
  event_bus: { total_subscriptions: number; message_types: number; history_size: number };
  scheduler: Record<string, unknown>;
}

// Default backend URL for browser-mode dev
const BACKEND_URL = 'http://localhost:8000';

function isElectron(): boolean {
  return !!window.tredo;
}

export async function getHealth(): Promise<ApiResult> {
  if (isElectron()) return window.tredo!.api.health();
  return directFetch('/health');
}

export async function getStatus(): Promise<ApiResult> {
  if (isElectron()) return window.tredo!.api.status();
  return directFetch('/status');
}

export async function getServices(): Promise<ApiResult> {
  if (isElectron()) return window.tredo!.api.services();
  return directFetch('/services');
}

export async function publishEvent(body: {
  event_type: string;
  message: string;
  severity?: string;
  details?: Record<string, unknown>;
}): Promise<ApiResult> {
  if (isElectron()) return window.tredo!.api.event(body);
  return directFetch('/event', 'POST', body);
}

export async function requestShutdown(reason: string = 'user_request'): Promise<ApiResult> {
  if (isElectron()) return window.tredo!.api.shutdown(reason);
  return directFetch('/shutdown', 'POST', { reason });
}

async function directFetch(
  endpoint: string,
  method: string = 'GET',
  body?: object
): Promise<ApiResult> {
  try {
    const options: RequestInit = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (body) options.body = JSON.stringify(body);

    const response = await fetch(`${BACKEND_URL}${endpoint}`, options);
    const data = await response.json();
    return { ok: response.ok, data };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Connection failed';
    return { ok: false, error: message };
  }
}
