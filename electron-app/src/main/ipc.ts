/**
 * TREDO — IPC Handlers
 * Bridge between Electron main process and renderer.
 * Main process proxies REST calls to the Python backend.
 */

import { ipcMain, net } from 'electron';

export function setupIPC(backendUrl: string): void {
  // Health check
  ipcMain.handle('api:health', async () => {
    return fetchBackend(backendUrl, '/health');
  });

  // Get status
  ipcMain.handle('api:status', async () => {
    return fetchBackend(backendUrl, '/status');
  });

  // Get services
  ipcMain.handle('api:services', async () => {
    return fetchBackend(backendUrl, '/services');
  });

  // Publish event
  ipcMain.handle('api:event', async (_event, body: object) => {
    return fetchBackend(backendUrl, '/event', 'POST', body);
  });

  // Shutdown
  ipcMain.handle('api:shutdown', async (_event, reason: string) => {
    return fetchBackend(backendUrl, '/shutdown', 'POST', { reason });
  });

  // Backend URL
  ipcMain.handle('api:backendUrl', async () => {
    return backendUrl;
  });
}

async function fetchBackend(
  baseUrl: string,
  endpoint: string,
  method: string = 'GET',
  body?: object
): Promise<{ ok: boolean; data?: unknown; error?: string }> {
  try {
    const url = `${baseUrl}${endpoint}`;
    const options: RequestInit = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (body) {
      options.body = JSON.stringify(body);
    }

    const response = await fetch(url, options);
    const data = await response.json();
    return { ok: response.ok, data };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return { ok: false, error: message };
  }
}
