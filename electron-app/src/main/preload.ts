/**
 * TREDO — Preload Script
 * Exposes a safe API to the renderer process via contextBridge.
 * Renderer never has direct access to Node.js or Electron APIs.
 */

import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('tredo', {
  // REST API calls via IPC
  api: {
    health: () => ipcRenderer.invoke('api:health'),
    status: () => ipcRenderer.invoke('api:status'),
    services: () => ipcRenderer.invoke('api:services'),
    event: (body: object) => ipcRenderer.invoke('api:event', body),
    shutdown: (reason: string) => ipcRenderer.invoke('api:shutdown', reason),
    backendUrl: () => ipcRenderer.invoke('api:backendUrl'),
  },
});
