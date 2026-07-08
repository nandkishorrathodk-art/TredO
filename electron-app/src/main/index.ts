/**
 * TREDO — Electron Main Process
 * Creates the browser window and manages app lifecycle.
 * Never imports Python logic — communicates via REST/WebSocket.
 */

import { app, BrowserWindow } from 'electron';
import path from 'path';
import { setupIPC } from './ipc';

let mainWindow: BrowserWindow | null = null;

const isDev = process.env.NODE_ENV !== 'production';
const BACKEND_URL = process.env.TREDO_BACKEND_URL || 'http://localhost:8000';

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'TREDO',
    backgroundColor: '#0a0a0f',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  setupIPC(BACKEND_URL);
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
