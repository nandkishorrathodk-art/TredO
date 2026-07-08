/**
 * TREDO — WebSocket Service
 * Connects to backend WebSocket for live event streaming.
 * Auto-reconnects on disconnect.
 */

export interface WsEvent {
  type: string;
  source: string;
  timestamp: string;
  [key: string]: unknown;
}

type EventHandler = (event: WsEvent) => void;

const WS_URL = 'ws://localhost:8000/ws';
const RECONNECT_DELAY = 3000;
const PING_INTERVAL = 30000;

export class WebSocketService {
  private ws: WebSocket | null = null;
  private handlers: EventHandler[] = [];
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private _connected = false;
  private _shouldReconnect = true;

  get connected(): boolean {
    return this._connected;
  }

  connect(): void {
    this._shouldReconnect = true;
    this.doConnect();
  }

  disconnect(): void {
    this._shouldReconnect = false;
    this.cleanup();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this._connected = false;
    this.notifyHandlers({
      type: 'ConnectionStatus',
      source: 'websocket',
      timestamp: new Date().toISOString(),
      status: 'disconnected',
    });
  }

  onEvent(handler: EventHandler): () => void {
    this.handlers.push(handler);
    return () => {
      this.handlers = this.handlers.filter((h) => h !== handler);
    };
  }

  private doConnect(): void {
    try {
      this.ws = new WebSocket(WS_URL);

      this.ws.onopen = () => {
        this._connected = true;
        this.startPing();
        this.notifyHandlers({
          type: 'ConnectionStatus',
          source: 'websocket',
          timestamp: new Date().toISOString(),
          status: 'connected',
        });
      };

      this.ws.onmessage = (event) => {
        try {
          const data: WsEvent = JSON.parse(event.data);
          if (data.type !== 'pong') {
            this.notifyHandlers(data);
          }
        } catch {
          // Ignore malformed messages
        }
      };

      this.ws.onclose = () => {
        this._connected = false;
        this.cleanup();
        this.notifyHandlers({
          type: 'ConnectionStatus',
          source: 'websocket',
          timestamp: new Date().toISOString(),
          status: 'disconnected',
        });
        if (this._shouldReconnect) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = () => {
        // onclose will fire after this
      };
    } catch {
      if (this._shouldReconnect) {
        this.scheduleReconnect();
      }
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.doConnect();
    }, RECONNECT_DELAY);
  }

  private startPing(): void {
    this.pingTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send('ping');
      }
    }, PING_INTERVAL);
  }

  private cleanup(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private notifyHandlers(event: WsEvent): void {
    this.handlers.forEach((h) => h(event));
  }
}

// Singleton instance
export const wsService = new WebSocketService();
